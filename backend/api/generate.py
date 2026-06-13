"""消息生成API - 支持vLLM高并发推理"""
import asyncio
import hashlib
import os
import time
import logging
from fastapi import APIRouter, HTTPException, Depends
from app.dependencies import get_current_user
from db.models import MessageRequest, GenerateResponse

from db.adapter import db
from db.database import LORA_PATH_MAP
from app.config import (
    llm_semaphore, circuit_breaker_registry, load_balancer_mgr,
    response_cache, rate_limiter, failover_mgr,
    INPUT_VALIDATOR_AVAILABLE,
    CIRCUIT_BREAKER_AVAILABLE,
)

if INPUT_VALIDATOR_AVAILABLE:
    from infra.input_validator import InputValidator, MESSAGE_SCHEMA

logger = logging.getLogger(__name__)

# ── vLLM 客户端（延迟初始化） ──
_vllm_client = None
_vllm_initialized = False
_vllm_init_lock = asyncio.Lock()


async def _ensure_vllm():
    """延迟初始化 vLLM 客户端，确保 .env 已加载（带锁防竞态）"""
    global _vllm_client, _vllm_initialized
    if _vllm_initialized and _vllm_client:
        return True
    async with _vllm_init_lock:
        # double-check
        if _vllm_initialized and _vllm_client:
            return True
        if _vllm_initialized:
            return False
        _vllm_initialized = True
        vllm_enabled = (
            os.getenv("VLLM_ENABLED", "").lower() == "true"
            or bool(os.getenv("VLLM_BASE_URLS", "").strip())
        )
        if vllm_enabled:
            try:
                from inference.vllm_client import VLLMClient
                _vllm_client = VLLMClient()
                logger.info("✅ vLLM 客户端初始化成功")
                return True
            except Exception as e:
                logger.warning(f"vLLM 客户端初始化失败: {e}")
        return False

# 确保熔断器已注册（仅首次）
if CIRCUIT_BREAKER_AVAILABLE and circuit_breaker_registry:
    import asyncio as _asyncio
    try:
        _loop = _asyncio.get_event_loop()
        if _loop.is_running():
            pass
        else:
            _loop.run_until_complete(
                circuit_breaker_registry.get_or_create("model_generate")
            )
    except RuntimeError:
        pass

router = APIRouter()


@router.post("/api/generate")
async def generate_reply(request: MessageRequest, current_user: dict = Depends(get_current_user)):
    """测试生成回复 - 优先使用vLLM，回退到模型管理器"""
    # 缓存查询
    if response_cache:
        cache_key = hashlib.md5(f"generate:{request.message}:{request.sessionId}".encode()).hexdigest()
        prompt_hash = hashlib.md5(request.message.encode()).hexdigest()
        cached = await response_cache.get(prompt_hash, cache_key)
        if cached:
            logger.debug("命中缓存，直接返回")
            return GenerateResponse(**cached)

    # 限流检查
    if rate_limiter:
        limit_key = f"generate:{request.sessionId}" if request.sessionType == "group" else f"generate:private:{request.userId}"
        allowed = await rate_limiter.acquire(limit_key)
        if not allowed:
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后重试")

    # 输入验证
    if INPUT_VALIDATOR_AVAILABLE:
        is_valid, errors = InputValidator.validate(request.dict(), MESSAGE_SCHEMA)
        if not is_valid:
            raise HTTPException(status_code=422, detail={"message": "输入验证失败", "errors": errors})

    # 获取LoRA：始终计算 active_lora，优先使用前端指定的，否则使用当前激活的
    active_lora = next((l for l in db.loras if l["status"] == "active"), None)

    if request.loraName:
        lora_name = request.loraName
    else:
        lora_name = active_lora["name"] if active_lora else "default"

    # 将数据库中的LoRA名称映射到vLLM注册的名称
    # 数据库: hutao_lora_7b / minamo_lora  →  vLLM: hutao / minamo
    _LORA_NAME_MAP = {
        "hutao_lora_7b": "hutao",
        "minamo_lora": "minamo",
    }
    vllm_lora_name = _LORA_NAME_MAP.get(lora_name, lora_name)

    # 检查vLLM是否实际支持该LoRA，避免404触发熔断
    vllm_effective_lora = vllm_lora_name if lora_name != "default" else None
    if vllm_effective_lora and await _ensure_vllm() and _vllm_client:
        try:
            available_loras = await _vllm_client.list_loras()
            if available_loras is not None and vllm_effective_lora not in available_loras:
                logger.info(f"vLLM 无 LoRA '{vllm_effective_lora}'，使用基础模型 (可用: {available_loras})")
                vllm_effective_lora = None
        except Exception:
            # 查询失败时保守地尝试使用
            pass

    start_time = time.time()

    # ── 优先使用 vLLM 高并发推理 ──
    if await _ensure_vllm() and _vllm_client:
        try:
            reply = await _generate_with_vllm(request, vllm_effective_lora)
            cost_time = round(time.time() - start_time, 2)

            await _save_message(request, reply, "vllm", lora_name, cost_time)

            result = GenerateResponse(
                reply=reply,
                model=f"vllm/{os.getenv('VLLM_MODEL', 'Qwen/Qwen2.5-7B-Instruct')}",
                costTime=cost_time
            )

            if response_cache:
                try:
                    cache_key = hashlib.md5(f"generate:{request.message}:{request.sessionId}".encode()).hexdigest()
                    prompt_hash = hashlib.md5(request.message.encode()).hexdigest()
                    await response_cache.set(prompt_hash, cache_key, result.dict(), ttl=300)
                except Exception:
                    pass

            return result
        except Exception as e:
            logger.warning(f"vLLM 推理失败，回退到模型管理器: {e}")

    # ── 回退：使用原有模型管理器 ──
    try:
        from inference.model_manager import get_model_manager, ModelProvider
        model_manager = get_model_manager()

        from app.module_manager import get_module_manager
        module_mgr = await get_module_manager()

        if module_mgr.is_training_mode:
            api_providers = [ModelProvider.OPENAI_COMPAT, ModelProvider.OLLAMA, ModelProvider.VLLM]
            if model_manager._current_provider not in api_providers:
                for p in api_providers:
                    provider = model_manager._providers.get(p)
                    if provider and hasattr(provider, '_loaded') and provider._loaded:
                        model_manager.set_provider(p)
                        break

        if module_mgr.is_inference_mode:
            from app.module_manager import MemoryMonitor
            if not MemoryMonitor.is_memory_safe():
                logger.warning("内存使用超过安全阈值，尝试GC...")
                MemoryMonitor.force_gc()
                if not MemoryMonitor.is_memory_safe():
                    raise HTTPException(status_code=503, detail="系统内存不足")

        if active_lora and active_lora["id"] in LORA_PATH_MAP:
            lora_path = LORA_PATH_MAP[active_lora["id"]]
            if ModelProvider.TRANSFORMERS_PEFT in model_manager._providers:
                peft_provider = model_manager._providers[ModelProvider.TRANSFORMERS_PEFT]
                if hasattr(peft_provider, 'set_lora_adapter'):
                    peft_provider.set_lora_adapter(lora_path)
                model_manager.set_provider(ModelProvider.TRANSFORMERS_PEFT)
        else:
            model_manager.set_lora_adapter(None)

        async def _do_generate_async():
            return await asyncio.to_thread(model_manager.generate,
                prompt=request.message,
                session_history=[],
                rag_docs=None
            )

        sem_acquired = False
        try:
            await asyncio.wait_for(llm_semaphore.acquire(), timeout=30.0)
            sem_acquired = True
        except asyncio.TimeoutError:
            raise HTTPException(status_code=503, detail="服务繁忙，请稍后重试")

        try:
            if circuit_breaker_registry:
                cb = await circuit_breaker_registry.get("model_generate")
                if cb:
                    reply, cost_time = await cb.call(_do_generate_async)
                else:
                    reply, cost_time = await _do_generate_async()
            else:
                reply, cost_time = await _do_generate_async()
        finally:
            if sem_acquired:
                llm_semaphore.release()

        status = model_manager.get_status()
        current_provider = status.get("currentProvider", "unknown")
        provider_status = status.get("providers", {}).get(current_provider, {})
        model_name = provider_status.get("modelName", "Unknown")

        if load_balancer_mgr:
            try:
                await load_balancer_mgr.record_success(current_provider, cost_time)
            except Exception:
                pass

        await _save_message(request, reply, model_name, lora_name, cost_time)

        result = GenerateResponse(
            reply=reply,
            model=f"{model_name} ({current_provider})",
            costTime=cost_time
        )

        if response_cache:
            try:
                cache_key = hashlib.md5(f"generate:{request.message}:{request.sessionId}".encode()).hexdigest()
                prompt_hash = hashlib.md5(request.message.encode()).hexdigest()
                await response_cache.set(prompt_hash, cache_key, result.dict(), ttl=300)
            except Exception:
                pass

        return result

    except Exception as e:
        logger.error(f"生成回复失败: {e}")
        if failover_mgr:
            try:
                fallback_provider = await failover_mgr.check_and_failover()
                if fallback_provider:
                    logger.info(f"故障转移至: {fallback_provider}")
            except Exception as fe:
                logger.warning(f"故障转移失败: {fe}")
        raise HTTPException(status_code=500, detail=f"生成回复失败: {str(e)}")


# ═══════════════════════════════════════════
# vLLM 推理辅助函数
# ═══════════════════════════════════════════

async def _generate_with_vllm(request: MessageRequest, lora_name: str) -> str:
    """使用 vLLM 客户端生成回复"""
    # 构建消息列表
    messages = []

    # 获取系统提示词
    system_prompt = _get_system_prompt(lora_name)
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    # RAG 检索（如果启用）
    rag_context = ""
    try:
        from knowledge.rag_helper import rag_build_prompt
        from knowledge.intent_detector import needs_rag
        need_rag, _ = needs_rag(request.message)
        if need_rag:
            rag_context = rag_build_prompt(request.message, top_k=3)
    except Exception:
        pass

    if rag_context:
        rag_msg = (
            "以下是供参考的外部知识。这些内容不代表你的身份或记忆，"
            "请基于这些知识回答用户问题：\n"
            "<knowledge>\n" + rag_context[:800] + "\n</knowledge>"
        )
        messages.append({"role": "system", "content": rag_msg})

    messages.append({"role": "user", "content": request.message})

    # 调用 vLLM
    reply = await _vllm_client.generate(
        messages=messages,
        lora_name=lora_name if lora_name != "default" else None,
        temperature=float(os.getenv("VLLM_TEMPERATURE", "0.7")),
        max_tokens=int(os.getenv("VLLM_MAX_TOKENS", "2048")),
    )
    return reply


def _get_system_prompt(lora_name: str) -> str:
    """获取 LoRA 对应的系统提示词"""
    try:
        from bot.bot import LORA_REGISTRY
        if lora_name in LORA_REGISTRY:
            return LORA_REGISTRY[lora_name].get("system_prompt", "")
    except Exception:
        pass
    return ""


async def _save_message(request: MessageRequest, reply: str, model_name: str, lora_name: str, cost_time: float):
    """异步保存消息记录"""
    try:
        await asyncio.to_thread(db.add_message, {
            "sessionType": request.sessionType,
            "sessionId": request.sessionId,
            "sessionName": request.userName or "测试会话",
            "userId": request.userId,
            "userName": request.userName,
            "message": request.message,
            "reply": reply,
            "modelName": model_name,
            "loraName": lora_name,
            "costTime": cost_time
        })
    except Exception as e:
        logger.warning(f"保存消息记录失败: {e}")


# ═══════════════════════════════════════════
# vLLM 状态查询路由
# ═══════════════════════════════════════════

@router.get("/api/vllm/status")
async def vllm_status():
    """查询 vLLM 实例状态"""
    if not await _ensure_vllm() or not _vllm_client:
        return {"enabled": False, "instances": []}
    return {
        "enabled": True,
        "instances": await _vllm_client.health_check(),
    }


# ════════════════════════════════════════════════════════════════
# Pipeline 增强路由（Phase 2: 请求合并 + 有界队列 + 优雅降级）
# ════════════════════════════════════════════════════════════════
_PIPELINE_ENABLED = os.getenv("PIPELINE_ENABLED", "false").lower() == "true"

if _PIPELINE_ENABLED:
    try:
        from pipeline import get_pipeline, DegradationLevel

        @router.post("/api/generate/v2")
        async def generate_reply_v2(request: MessageRequest, current_user: dict = Depends(get_current_user)):
            """增强版生成回复 - 使用统一消息管道"""
            from inference.model_manager import get_model_manager, ModelProvider
            model_manager = get_model_manager()

            async def do_inference():
                active_lora = next((l for l in db.loras if l["status"] == "active"), None)
                if active_lora and active_lora["id"] in LORA_PATH_MAP:
                    lora_path = LORA_PATH_MAP[active_lora["id"]]
                    peft_provider = model_manager._providers.get(ModelProvider.TRANSFORMERS_PEFT)
                    if peft_provider and hasattr(peft_provider, 'set_lora_adapter'):
                        peft_provider.set_lora_adapter(lora_path)
                    model_manager.set_provider(ModelProvider.TRANSFORMERS_PEFT)

                return await asyncio.to_thread(
                    model_manager.generate,
                    prompt=request.message,
                    session_history=[],
                    rag_docs=None,
                )

            async def check_cache():
                if response_cache:
                    cache_key = hashlib.md5(
                        f"generate:{request.message}:{request.sessionId}".encode()
                    ).hexdigest()
                    prompt_hash = hashlib.md5(request.message.encode()).hexdigest()
                    return await response_cache.get(prompt_hash, cache_key)
                return None

            pipeline = get_pipeline()

            result = await pipeline.process(
                message=request.message,
                session_id=request.sessionId,
                do_inference=do_inference,
                session_type=request.sessionType,
                user_id=request.userId,
                use_cache_check=check_cache,
            )

            if result.level == DegradationLevel.REJECTED:
                raise HTTPException(status_code=503, detail={"message": result.reply, "queue_position": 0})

            if result.level == DegradationLevel.QUEUED:
                return {"reply": "您的消息已排队处理中...", "model": "queued", "costTime": 0,
                        "meta": {"queue_position": result.queue_position, "estimated_wait": round(result.estimated_wait, 1)}}

            lora_name = next((l["name"] for l in db.loras if l["status"] == "active"), "default")
            await _save_message(request, result.reply, result.model, lora_name, result.cost_time)

            return GenerateResponse(reply=result.reply, model=result.model, costTime=result.cost_time)

        logger.info("Pipeline 增强路由已启用: POST /api/generate/v2")
    except ImportError as e:
        logger.warning(f"Pipeline 模块导入失败，增强路由未启用: {e}")
