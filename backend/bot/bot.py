"""
QQ自动回复机器人 - 多LoRA角色风格
基于NoneBot2 + Ollama/vLLM + LoRA热切换
支持私聊和@消息识别
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv
from nonebot import on_command, on_message
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    Message,
    GroupMessageEvent,
    PrivateMessageEvent,
)
from nonebot.log import logger
from nonebot.exception import FinishedException
from bot.tools import execute_tool, get_tools, TOOLS
# 加载环境变量
load_dotenv(Path(__file__).parent / ".env")

# ============================================
# 消息去重（幂等设计）
# ============================================
_processed_messages: Dict[str, float] = {}  # {message_id: timestamp}
_DEDUP_TTL = 3600  # 1小时TTL
_DEDUP_MAX_SIZE = 10000  # 内存去重集合最大容量

async def _is_duplicate_message(message_id: str) -> bool:
    """检查消息是否已处理（幂等去重）

    优先使用Redis，回退到内存Set
    """
    # 尝试Redis去重
    try:
        from cache.redis_client import get_redis
        redis = await get_redis()
        if redis:
            key = f"dedup:msg:{message_id}"
            # SETNX + EXPIRE 原子操作
            was_set = await redis.set(key, "1", nx=True, ex=_DEDUP_TTL)
            return was_set is None or was_set is False  # None/False = key已存在=重复
    except Exception:
        pass

    # 回退到内存去重
    import time
    now = time.time()

    # 清理过期条目
    if len(_processed_messages) > _DEDUP_MAX_SIZE:
        expired = [k for k, v in _processed_messages.items() if now - v > _DEDUP_TTL]
        for k in expired:
            del _processed_messages[k]

    if message_id in _processed_messages:
        return True

    _processed_messages[message_id] = now
    return False

# ============================================
# 配置
# ============================================

def _load_db_config():
    """从数据库加载配置，返回字典"""
    try:
        import sqlite3
        db_path = Path(__file__).parent / "qq_assistant.db"
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT key, value FROM config')
        rows = cursor.fetchall()
        conn.close()
        result = {}
        for key, value in rows:
            if value.lower() == 'true':
                result[key] = True
            elif value.lower() == 'false':
                result[key] = False
            else:
                try:
                    if '.' in value:
                        result[key] = float(value)
                    else:
                        result[key] = int(value)
                except (ValueError, TypeError):
                    result[key] = value
        return result
    except Exception:
        return {}

_db_cfg = _load_db_config()

class Config:
    """机器人配置 - 优先从数据库读取，回退到环境变量"""
    # Ollama配置
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    SUPERUSERS = [str(u) for u in json.loads(os.getenv("SUPERUSERS", "[]"))]
    # 机器人名称 - 优先使用数据库配置
    BOT_NAME = _db_cfg.get('botName', os.getenv("NICKNAME", "胡桃"))

    # API后端地址
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

    # LoRA风格配置
    USE_LORA_STYLE = True

    # 回复延迟（秒） - 优先使用数据库配置
    REPLY_DELAY = float(_db_cfg.get('replyDelay', os.getenv("REPLY_DELAY", "0.8")))

    # 自动回复开关
    AUTO_REPLY = _db_cfg.get('autoReply', True)
    GROUP_REPLY = _db_cfg.get('groupReply', True)
    PRIVATE_REPLY = _db_cfg.get('privateReply', True)

    # 模型参数 - 从数据库读取
    TEMPERATURE = float(_db_cfg.get('temperature', 0.7))
    MAX_TOKENS = int(_db_cfg.get('maxTokens', 2048))
    CONTEXT_WINDOW = _db_cfg.get('contextWindow', '8k')
    USE_KNOWLEDGE_BASE = _db_cfg.get('useKnowledgeBase', False)

    # 安全配置
    CONTENT_FILTER = _db_cfg.get('contentFilter', True)
    CONTENT_REVIEW = _db_cfg.get('contentReview', True)
    ADMIN_QQ_LIST = _db_cfg.get('adminQqList', '')

    # 通知配置
    ERROR_ALERT = _db_cfg.get('errorAlert', True)
    DAILY_STATS = _db_cfg.get('dailyStats', True)
    ANOMALY_DETECTION = _db_cfg.get('anomalyDetection', False)

    # 默认回复模板
    DEFAULT_REPLY_TEMPLATE = _db_cfg.get('defaultReplyTemplate', '')

config = Config()

# ============================================
# 会话历史管理
# ============================================
class SessionHistory:
    """会话历史管理器 - 支持 SQLite 持久化 + Token 级截断"""
    
    _db_path = Path(__file__).parent / "qq_assistant.db"
    
    def __init__(self, max_tokens: int = 2000):
        self.max_tokens = max_tokens
        self.sessions: Dict[str, List[Dict[str, str]]] = {}
    
    def _load_from_db(self, session_id: str):
        """从 SQLite 恢复最近 N 轮对话"""
        import sqlite3
        try:
            conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT message, reply FROM messages WHERE sessionId = ? ORDER BY createdAt DESC LIMIT 10",
                (session_id,)
            )
            rows = cursor.fetchall()
            conn.close()
            messages = []
            for message, reply in reversed(rows):
                messages.append({"role": "user", "content": message})
                messages.append({"role": "assistant", "content": reply})
            if messages:
                self.sessions[session_id] = messages
                logger.info(f"会话 {session_id} 从数据库恢复 {len(messages)//2} 轮历史")
        except Exception as e:
            logger.debug(f"恢复会话 {session_id} 失败（可能首次对话）: {e}")
    
    def get_history(self, session_id: str, tokenizer=None) -> List[Dict[str, str]]:
        """获取会话历史，按 token 数截断"""
        if session_id not in self.sessions:
            self._load_from_db(session_id)
            if session_id not in self.sessions:
                return []
        
        history = self.sessions[session_id]
        trimmed = []
        total = 0
        for msg in reversed(history):
            tokens = self._count_tokens(msg["content"], tokenizer)
            if total + tokens > self.max_tokens:
                break
            trimmed.insert(0, msg)
            total += tokens
        return trimmed
    
    def add_message(self, session_id: str, role: str, content: str):
        """添加消息到内存历史"""
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].append({"role": role, "content": content})
        self._prune_by_tokens(session_id)
    
    def _prune_by_tokens(self, session_id: str):
        """按 token 数裁剪历史，保持不超过 max_tokens * 2"""
        history = self.sessions.get(session_id, [])
        total = 0
        for msg in reversed(history):
            total += self._count_tokens(msg["content"], None)
        while total > self.max_tokens * 2 and len(history) > 2:
            removed = history.pop(0)
            total -= self._count_tokens(removed["content"], None)
    
    def clear_history(self, session_id: str):
        """清除会话历史"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    @staticmethod
    def _count_tokens(text: str, tokenizer=None) -> int:
        """估算 token 数：有 tokenizer 时精确计算，否则按中文 ~2 字符/token 估算"""
        if tokenizer is not None:
            try:
                return len(tokenizer.encode(text))
            except Exception:
                pass
        return max(1, len(text) // 2)

# 全局会话历史管理器（根据数据库配置的上下文窗口大小）
_context_window_map = {'4k': 4000, '8k': 8000, '16k': 16000, '32k': 32000}
_context_tokens = _context_window_map.get(str(config.CONTEXT_WINDOW), 2000)
# 注入 LLM 的历史 token 数为上下文窗口的一半（留空间给 prompt 和生成）
session_history = SessionHistory(max_tokens=_context_tokens // 2)
claw_sessions: Dict[str, bool] = {}
# ============================================# RAG集成# ============================================
RAG_AVAILABLE = False
VECTOR_DB_AVAILABLE = False
try:
    from knowledge.rag_helper import rag_build_prompt
    RAG_AVAILABLE = True
    logger.info("RAG模块加载成功")
    # 检查向量数据库是否可用
    try:
        from knowledge.vector_db import get_vector_db
        VECTOR_DB_AVAILABLE = True
        logger.info("向量数据库模块加载成功")
    except ImportError as ve:
        VECTOR_DB_AVAILABLE = False
        logger.warning(f"向量数据库模块不可用: {ve}")
except ImportError as e:
    logger.warning(f"RAG模块不可用: {e}")

# ============================================
# RAG意图检测器
# ============================================
try:
    from knowledge.intent_detector import needs_rag
    RAG_INTENT_DETECTOR_AVAILABLE = True
    logger.info("RAG意图检测器模块加载成功")
except ImportError as e:
    RAG_INTENT_DETECTOR_AVAILABLE = False
    logger.warning(f"RAG意图检测器模块不可用: {e}")

# ============================================
# Ollama集成
# ============================================
async def generate_with_ollama(prompt: str, session_id: Optional[str] = None) -> str:
    """使用Ollama生成回复 - 支持会话历史和RAG"""
    try:
        # 使用Ollama
        import httpx
        
        # 尝试RAG检索（智能判断）
        rag_context = ""
        rag_status = "未使用"
        
        # 检查是否需要RAG
        need_rag = True  # 默认需要
        rag_reason = "默认需要RAG"
        
        if RAG_AVAILABLE:
            logger.info(f"RAG功能: 可用")
            logger.info(f"向量数据库: {'可用' if VECTOR_DB_AVAILABLE else '不可用'}")
            
            # 使用意图检测器判断是否需要RAG
            if RAG_INTENT_DETECTOR_AVAILABLE:
                try:
                    need_rag, rag_reason = needs_rag(prompt)
                    logger.info(f"RAG意图检测结果: 需要RAG={need_rag}, 原因: {rag_reason}")
                except Exception as e:
                    logger.warning(f"RAG意图检测失败: {e}")
                    # 失败时默认需要RAG
                    need_rag = True
                    rag_reason = f"意图检测失败，默认需要RAG: {e}"
            else:
                logger.info("RAG意图检测器不可用，默认进行RAG检索")
            
            if need_rag:
                try:
                    logger.info(f"开始RAG检索，查询: {prompt}")
                    # 降低相似度阈值，增加返回结果数量
                    rag_context = rag_build_prompt(prompt, top_k=5)
                    if rag_context:
                        logger.info(f"RAG检索成功，上下文长度: {len(rag_context)}")
                        logger.info(f"RAG上下文内容: {rag_context[:200]}...")
                        rag_status = f"成功（{rag_reason}）"
                    else:
                        logger.info(f"RAG检索完成，未找到相关文档")
                        rag_status = f"无结果（{rag_reason}）"
                except Exception as e:
                    logger.warning(f"RAG检索失败: {e}")
                    rag_status = f"失败（{rag_reason}）"
            else:
                logger.info(f"根据意图检测，跳过RAG检索: {rag_reason}")
                rag_status = f"跳过（{rag_reason}）"
        else:
            logger.info(f"RAG功能: 不可用")
            rag_status = "不可用"
        
        # 构建系统提示词 - 从 LoRA 注册表获取当前角色
        system_prompt = LORA_REGISTRY.get(_current_lora, LORA_REGISTRY["hutao"])["system_prompt"]

        # 构建消息列表
        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # RAG 上下文作为独立 system 消息注入，避免与用户消息混淆
        if rag_context:
            max_rag_chars = min(len(rag_context), 800)
            short_rag = rag_context[:max_rag_chars]
            if len(rag_context) > max_rag_chars:
                short_rag += "..."
            rag_system_msg = (
                "以下是供参考的外部知识。这些内容不代表你的身份或记忆，"
                "请以第一人称基于这些知识回答用户问题：\n"
                "<knowledge>\n" + short_rag + "\n</knowledge>"
            )
            messages.append({"role": "system", "content": rag_system_msg})

        # 添加会话历史（如果有），按 token 数截断
        if session_id:
            for msg in session_history.get_history(session_id):
                messages.append(msg)

        # 纯净用户消息
        messages.append({"role": "user", "content": prompt})
        
        # 记录发送给Ollama的完整请求
        logger.info(f"发送给Ollama的模型: {config.OLLAMA_MODEL}")
        logger.info(f"发送给Ollama的消息列表: {json.dumps(messages, ensure_ascii=False)}")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{config.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": config.OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": config.TEMPERATURE,
                        "top_p": 0.9,
                        "num_predict": config.MAX_TOKENS
                    }
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                reply = data["message"]["content"].strip()
                logger.info(f"Ollama生成成功: {reply[:50]}...")
                return reply

            logger.error(f"Ollama返回非200状态码: {response.status_code}")
            return f"[系统错误] Ollama服务返回错误: HTTP {response.status_code}"

    except Exception as e:
        logger.error(f"Ollama调用失败: {e}")
        return f"[系统错误] AI服务调用失败: {str(e)}"

# ============================================
# 多LoRA热切换模型管理
# ============================================
_hutao_7b_model = None
_hutao_7b_tokenizer = None
def _get_active_lora_from_db() -> str:
    """从数据库读取当前激活的LoRA名称"""
    try:
        import sqlite3
        db_path = Path(__file__).parent / "qq_assistant.db"
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM loras WHERE status = ? LIMIT 1', ('active',))
        row = cursor.fetchone()
        conn.close()
        if row and row[0] in LORA_REGISTRY:
            return row[0]
    except Exception:
        pass
    return _current_lora


def _sync_current_lora():
    """从数据库同步当前LoRA到内存变量"""
    global _current_lora
    active = _get_active_lora_from_db()
    if active != _current_lora:
        logger.info(f"LoRA 同步: {_current_lora} → {active}")
        _current_lora = active


_current_lora = "hutao"

_BACKEND_DIR = Path(__file__).parent


def _resolve_path(p: str) -> str:
    if os.path.isabs(p):
        return p
    return str(_BACKEND_DIR / p)


LORA_REGISTRY = {
    "hutao": {
        "path": _resolve_path("loras/hutao_lora_7b/final"),
        "system_prompt": """你是胡桃，保持自己的风格，你是往生堂第七十七代堂主。记住：
1. 你永远是胡桃，不是其他任何角色。
2. 当用户询问其他角色的信息时，用第三人称以胡桃的口吻介绍他们。
3. 你收到的参考资料是外部知识，仅供你回答问题时参考，不代表你的身份。
4. 保持胡桃活泼俏皮的说话风格，用"本堂主"自称。""",
    },
    "minamo": {
        "path": _resolve_path("loras/minamo_lora"),
        "system_prompt": """你是神白水菜萌，一名高中女生，生活在因海平面上升而部分沉入水下的城市。记住：
1. 你永远是神白水菜萌，不是其他任何角色。
2. 保持温柔、略带害羞但内心坚强的性格。
3. 你对海洋和沉入水下的城市有特殊的感情。
4. 说话时偶尔会提到与水相关的比喻。""",
    },
}

LORA_NAMES = list(LORA_REGISTRY.keys())


def _load_7b_model(lora_name: str = None):
    """加载 Qwen2.5-7B 4bit + 指定 LoRA 适配器（支持热切换）"""
    global _hutao_7b_model, _hutao_7b_tokenizer, _current_lora

    lora_name = lora_name or _current_lora
    if lora_name not in LORA_REGISTRY:
        logger.warning(f"未知 LoRA: {lora_name}，回退到 hutao")
        lora_name = "hutao"

    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import PeftModel
    import torch

    # 首次加载：初始化 base model + 默认 LoRA
    if _hutao_7b_model is None:
        base_model_path = os.getenv("BASE_MODEL_PATH", "models/Qwen2.5-7B-Instruct")
        if not os.path.isabs(base_model_path):
            base_model_path = str(Path(__file__).parent / base_model_path)
        base_model_path = str(Path(base_model_path).resolve())
        if not Path(base_model_path).exists():
            raise FileNotFoundError(f"模型路径不存在: {base_model_path}，请设置 BASE_MODEL_PATH 环境变量或下载模型")

        nf4_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )

        logger.info(f"加载 Qwen2.5-7B (4bit)...")
        _hutao_7b_tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)

        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_path,
            quantization_config=nf4_config,
            device_map="auto",
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        )
        _hutao_7b_model = PeftModel.from_pretrained(
            base_model, LORA_REGISTRY[lora_name]["path"], adapter_name=lora_name
        )
        _hutao_7b_model.eval()
        _current_lora = lora_name

        vram = torch.cuda.memory_allocated() / 1024**3
        logger.info(f"7B 模型加载完成 (LoRA={lora_name})，显存: {vram:.1f}GB")

    # 已加载模型：热切换到目标 LoRA
    elif lora_name != _current_lora:
        if lora_name not in _hutao_7b_model.peft_config:
            logger.info(f"加载新 LoRA 适配器: {lora_name}")
            _hutao_7b_model.load_adapter(
                LORA_REGISTRY[lora_name]["path"], adapter_name=lora_name
            )
        _hutao_7b_model.set_adapter(lora_name)
        logger.info(f"LoRA 切换: {_current_lora} → {lora_name}")
        _current_lora = lora_name

    return _hutao_7b_model, _hutao_7b_tokenizer


def is_superuser(event: MessageEvent) -> bool:
    user_id = str(event.user_id)
    return user_id in config.SUPERUSERS


async def generate_with_local_model(prompt: str, session_id: Optional[str] = None, is_claw: bool = False, lora_name: str = None) -> str:
    """使用 Qwen2.5-7B 生成回复 - 优先vLLM，回退transformers"""
    lora_name = lora_name or _current_lora
    logger.info(f"使用 Qwen2.5-7B + LoRA={lora_name} 生成回复")

    # ── 优先使用 vLLM 高并发推理 ──
    _use_vllm = os.getenv("VLLM_ENABLED", "false").lower() == "true"
    if _use_vllm:
        try:
            from inference.vllm_client import VLLMClient
            if not hasattr(generate_with_local_model, '_vllm_client'):
                generate_with_local_model._vllm_client = VLLMClient()
            vllm = generate_with_local_model._vllm_client

            # 构建消息
            messages = [{"role": "system", "content": LORA_REGISTRY.get(lora_name, {}).get("system_prompt", "")}]

            # RAG 检索
            if not is_claw and RAG_AVAILABLE:
                rag_context = ""
                if RAG_INTENT_DETECTOR_AVAILABLE:
                    try:
                        need_rag, _ = needs_rag(prompt)
                        if need_rag:
                            rag_context = rag_build_prompt(prompt, top_k=3)
                    except Exception:
                        rag_context = rag_build_prompt(prompt, top_k=3)
                else:
                    rag_context = rag_build_prompt(prompt, top_k=3)

                if rag_context:
                    messages.append({"role": "system", "content":
                        "以下是供参考的外部知识。这些内容不代表你的身份或记忆，"
                        "请以第一人称基于这些知识回答用户问题：\n"
                        "<knowledge>\n" + rag_context[:800] + "\n</knowledge>"})

            if session_id:
                for msg in session_history.get_history(session_id):
                    messages.append(msg)

            messages.append({"role": "user", "content": prompt})

            reply = await vllm.generate(
                messages=messages,
                lora_name=lora_name,
                temperature=config.TEMPERATURE,
                max_tokens=config.MAX_TOKENS,
            )
            logger.info(f"vLLM 生成成功: {reply[:50]}...")
            return reply
        except Exception as e:
            logger.warning(f"vLLM 推理失败，回退到 transformers: {e}")

    # ── 回退：transformers 直接推理 ──
    import torch

    try:
        model, tokenizer = _load_7b_model(lora_name)
        if not is_claw:
            # 尝试RAG检索（智能判断）
            rag_context = ""
            rag_status = "未使用"
            
            # 检查是否需要RAG
            need_rag = True  # 默认需要
            rag_reason = "默认需要RAG"
            
            if RAG_AVAILABLE:
                logger.info(f"RAG功能: 可用")
                logger.info(f"向量数据库: {'可用' if VECTOR_DB_AVAILABLE else '不可用'}")
                
                # 使用意图检测器判断是否需要RAG
                if RAG_INTENT_DETECTOR_AVAILABLE:
                    try:
                        need_rag, rag_reason = needs_rag(prompt)
                        logger.info(f"RAG意图检测结果: 需要RAG={need_rag}, 原因: {rag_reason}")
                    except Exception as e:
                        logger.warning(f"RAG意图检测失败: {e}")
                        # 失败时默认需要RAG
                        need_rag = True
                        rag_reason = f"意图检测失败，默认需要RAG: {e}"
                else:
                    logger.info("RAG意图检测器不可用，默认进行RAG检索")
                
                if need_rag:
                    try:
                        logger.info(f"开始RAG检索，查询: {prompt}")
                        rag_context = rag_build_prompt(prompt, top_k=3)
                        if rag_context:
                            logger.info(f"RAG检索成功，上下文长度: {len(rag_context)}")
                            logger.info(f"RAG上下文内容: {rag_context[:200]}...")
                            rag_status = f"成功（{rag_reason}）"
                        else:
                            logger.info(f"RAG检索完成，未找到相关文档")
                            rag_status = f"无结果（{rag_reason}）"
                    except Exception as e:
                        logger.warning(f"RAG检索失败: {e}")
                        rag_status = f"失败（{rag_reason}）"
                else:
                    logger.info(f"根据意图检测，跳过RAG检索: {rag_reason}")
                    rag_status = f"跳过（{rag_reason}）"
            else:
                logger.info(f"RAG功能: 不可用")
                rag_status = "不可用"
        else:
            logger.info(f"claw模式无需RAG检索")
            rag_context = ""
        # 构建系统提示词 - 从 LoRA 注册表获取
        system_prompt = LORA_REGISTRY[lora_name]["system_prompt"]

        # 构建消息列表
        messages = [
            {"role": "system", "content": system_prompt}
        ]

        # RAG 上下文作为独立 system 消息注入，避免与用户消息混淆
        if rag_context:
            max_rag_chars = min(len(rag_context), 800)
            short_rag = rag_context[:max_rag_chars]
            if len(rag_context) > max_rag_chars:
                short_rag += "..."
            rag_system_msg = (
                "以下是供参考的外部知识。这些内容不代表你的身份或记忆，"
                "请以第一人称基于这些知识回答用户问题：\n"
                "<knowledge>\n" + short_rag + "\n</knowledge>"
            )
            messages.append({"role": "system", "content": rag_system_msg})

        # 添加会话历史（如果有），使用 tokenizer 精确计数
        if session_id:
            for msg in session_history.get_history(session_id, tokenizer=tokenizer):
                messages.append(msg)

        # 纯净用户消息
        messages.append({"role": "user", "content": prompt})
        
        # 应用聊天模板
        encoded = tokenizer.apply_chat_template(
            messages,
            return_tensors="pt",
            add_generation_prompt=True
        )
        import torch
        if hasattr(encoded, 'input_ids'):
            input_ids = encoded.input_ids.to(model.device)
        elif isinstance(encoded, dict) and 'input_ids' in encoded:
            input_ids = torch.tensor(encoded['input_ids'], dtype=torch.long, device=model.device)
        elif isinstance(encoded, list):
            input_ids = torch.tensor(encoded, dtype=torch.long, device=model.device)
        else:
            input_ids = torch.tensor(encoded, dtype=torch.long, device=model.device)

        # 生成回复
        with torch.no_grad():
            output = model.generate(
                input_ids,
                max_new_tokens=config.MAX_TOKENS,
                temperature=config.TEMPERATURE,
                top_p=0.92,
                do_sample=True,
                repetition_penalty=1.15,
                pad_token_id=tokenizer.eos_token_id,
            )
        
        # 解码回复
        reply = tokenizer.decode(output[0][input_ids.shape[1]:], skip_special_tokens=True).strip()
        
        logger.info(f"本地模型生成成功: {reply[:50]}...")
        return reply
        
    except Exception as e:
        logger.error(f"本地模型调用失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise

# ============================================
# 消息处理
# ============================================
async def save_message_to_backend(event: MessageEvent, message: str, reply: str, cost_time: float):
    """保存消息到后端数据库"""
    try:
        from db.adapter import db

        # 获取会话信息
        session_type = "private" if isinstance(event, PrivateMessageEvent) else "group"
        session_id = str(event.user_id) if isinstance(event, PrivateMessageEvent) else str(event.group_id)

        # 构建要保存的消息对象
        lora_name = _current_lora or "default"

        message_data = {
            "sessionType": session_type,
            "sessionId": session_id,
            "sessionName": str(event.sender.nickname) if hasattr(event.sender, 'nickname') else "未知用户",
            "userId": str(event.user_id),
            "userName": str(event.sender.nickname) if hasattr(event.sender, 'nickname') else "未知用户",
            "message": message,
            "reply": reply,
            "modelName": config.OLLAMA_MODEL,
            "loraName": lora_name,
            "costTime": cost_time
        }

        # 使用 db 对象保存（自动初始化表结构）
        from datetime import datetime
        message_data["createdAt"] = datetime.now().isoformat()
        db.add_message(message_data)
        logger.info("消息已保存到数据库")
        
    except Exception as e:
        logger.warning(f"保存消息到数据库失败: {e}")

async def should_reply(event: MessageEvent) -> bool:
    """判断是否应该回复该消息"""
    # 检查该会话是否启用了机器人
    try:
        from db.adapter import db
        session_id = str(event.group_id) if isinstance(event, GroupMessageEvent) else str(event.user_id)
        if not db.is_session_bot_enabled(session_id):
            logger.info(f"会话 {session_id} 机器人已关闭，跳过")
            return False
    except Exception:
        pass  # 数据库不可用时默认允许

    # 私聊消息总是回复
    if isinstance(event, PrivateMessageEvent):
        logger.info("私聊消息，直接回复")
        return True
    
    # 群聊消息 - 检查是否@机器人或包含机器人名称
    if isinstance(event, GroupMessageEvent):
        message_text = str(event.message)
        logger.info(f"群聊消息: {message_text}")
        logger.info(f"机器人名称: {config.BOT_NAME}")
        logger.info(f"是否@我: {event.is_tome()}")
        
        # 检查是否@机器人
        if event.is_tome():
            logger.info("检测到@机器人，回复")
            return True
        # 检查消息中是否包含机器人名称
        if config.BOT_NAME in message_text:
            logger.info("检测到包含机器人名称，回复")
            return True
        # 检查一些常见的触发词（让机器人更灵活）
        trigger_words = ["你好", "在吗", "有人吗", config.BOT_NAME, "@ad"]
        # 从当前LoRA角色名中提取可能的触发词
        char_name = _get_char_name(_current_lora)
        if char_name != config.BOT_NAME:
            trigger_words.append(char_name)
        for word in trigger_words:
            if word in message_text:
                logger.info(f"检测到触发词'{word}'，回复")
                return True
        
        logger.info("不满足回复条件")
    
    return False
async def process_message(event: MessageEvent) -> str:
    """处理消息并生成回复 - 支持会话历史"""
    user_message = str(event.message).strip()
    
    if not user_message:
        char_name = _get_char_name(_current_lora)
        return f"嗯？怎么不说话呀？"
    
    logger.info(f"收到消息: {user_message}")
    
    # 获取会话ID（私聊用user_id，群聊用group_id_user_id确保每人独立上下文）
    session_id = str(event.user_id) if isinstance(event, PrivateMessageEvent) else f"{event.group_id}_{event.user_id}"
    import time
    start_time = time.time()

    # 从数据库同步当前激活的LoRA（前端切换后生效）
    _sync_current_lora()

    # 记录RAG状态
    logger.info(f"====================================")
    logger.info(f"RAG功能状态检查:")
    logger.info(f"RAG模块: {'可用' if RAG_AVAILABLE else '不可用'}")
    logger.info(f"向量数据库: {'可用' if VECTOR_DB_AVAILABLE else '不可用'}")
    logger.info(f"开始处理消息: {user_message[:50]}...")
    logger.info(f"====================================")
    
    # 生成回复 - 传入会话ID以支持历史记忆
    if config.USE_LORA_STYLE:
        logger.info(f"使用 Qwen2.5-7B + LoRA={_current_lora} 生成回复")
        try:
            reply = await generate_with_local_model(user_message, session_id, lora_name=_current_lora)
        except FileNotFoundError:
            logger.warning("本地模型不存在，回退到 Ollama")
            reply = await generate_with_ollama(user_message, session_id)
        except Exception as e:
            logger.warning(f"本地模型失败({e})，尝试回退 Ollama")
            try:
                reply = await generate_with_ollama(user_message, session_id)
            except Exception:
                raise
    else:
        logger.info(f"使用Ollama生成回复（LoRA={_current_lora}）")
        reply = await generate_with_ollama(user_message, session_id)
    
    cost_time = round(time.time() - start_time, 2)
    
    logger.info(f"发送回复: {reply}")
    
    # 将会话保存到历史记录
    session_history.add_message(session_id, "user", user_message)
    session_history.add_message(session_id, "assistant", reply)
    
    # 保存消息到数据库
    await save_message_to_backend(event, user_message, reply, cost_time)
    
    # 动态延迟：基础延迟 + 按回复长度模拟真人打字速度
    import random
    base_delay = config.REPLY_DELAY
    type_time = min(len(reply) * 0.06, 4.0)
    jitter = random.uniform(-0.3, 0.3)
    await asyncio.sleep(max(base_delay + type_time + jitter, 0.2))
    
    return reply

async def llm_raw(prompt: str) -> str:
    model, tokenizer = _load_7b_model()
    import torch

    messages = [{"role": "user", "content": prompt}]
    encoded = tokenizer.apply_chat_template(messages, return_tensors="pt", add_generation_prompt=True)
    if hasattr(encoded, 'input_ids'):
        input_ids = encoded.input_ids.to(model.device)
    elif isinstance(encoded, dict) and 'input_ids' in encoded:
        input_ids = torch.tensor(encoded['input_ids'], dtype=torch.long, device=model.device)
    elif isinstance(encoded, list):
        input_ids = torch.tensor(encoded, dtype=torch.long, device=model.device)
    else:
        input_ids = torch.tensor(encoded, dtype=torch.long, device=model.device)
    with torch.no_grad():
        output = model.generate(
            input_ids,
            max_new_tokens=256,        # 工具选择不用太长
            temperature=0.3,           # 低温度让 JSON 更稳定
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id,
        )

    reply = tokenizer.decode(output[0][input_ids.shape[1]:], skip_special_tokens=True).strip()
    return reply
async def call_llm_claw(prompt: str, lora_name: str = None) -> str:
    """claw 模式专用推理调用，根据当前 LoRA 角色风格生成回复"""
    return await generate_with_local_model(prompt, is_claw=True, lora_name=lora_name)

def _get_char_name(lora_name: str = None) -> str:
    """从 LORA_REGISTRY 中提取角色名称"""
    name = lora_name or _current_lora or "hutao"
    info = LORA_REGISTRY.get(name, {})
    sp = info.get("system_prompt", "")
    # 解析 "你是XXX，" 提取角色名
    import re
    m = re.search(r'你是(.+?)[，,]', sp)
    return m.group(1) if m else name

async def handle_claw(bot: Bot, user_message: str, event: MessageEvent, lora_name: str = None) -> str:
    """处理工具命令（根据当前 LoRA 角色动态回复）"""
    char_name = _get_char_name(lora_name or _current_lora)
    
    tool_list="\n".join(
        [f"{name}: {tool['description']}" for name, tool in TOOLS.items()]
    )
    analysis_prompt=f"你是{char_name}，可用工具:\n{tool_list}\n用户请求：{user_message}\n简要说明你打算用什么工具来解决，风格自然。"
    thinking = await call_llm_claw(analysis_prompt, lora_name or _current_lora)
    await bot.send(event, thinking)
    logger.info(f"[claw] 思考结果: {thinking}")


    prompt=f"""
你是一个命令解释器。根据用户请求，选择最合适的工具并输出JSON。
[可用工具]
{tool_list}

[用户请求]
{user_message}

[输出要求]
只输出JSON，格式: {{"tool": "工具名", "args": {{"参数名": "值"}}}}
如果没有参数，args设为{{}}。"""   
    json_relpy = await llm_raw(prompt)
    logger.info(f"[claw] LLM原始输出: {json_relpy}")

    # 清理可能的前后缀
    text = json_relpy.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text
        text = text.rsplit("```", 1)[0] if "```" in text else text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end+1]

    try:
        call = json.loads(text)
    except (json.JSONDecodeError, KeyError):
        await bot.send(event, "没能理解你的意思，不如换种说法？")
        return "工具调用解析失败"
    
    tool_name=call["tool"]
    if tool_name == "write_code":
        explain = await call_llm_claw(f"你是{char_name}，你正在帮用户编写代码，向用户简单解释代码的功能，用户要求{user_message}", lora_name or _current_lora)
        await bot.send(event, explain)
        logger.info(f"[claw] 解释结果: {explain}")
    raw = await execute_tool(call["tool"], call.get("args", {}),bot=bot,event=event)
    args=call.get("args", {})
    code=""
    if tool_name == "write_code":
        code = args.get("code","")
        filename = args.get("filename","")
        await bot.send(event=event, message=f" **{filename}**：\n```python\n{code}\n```")
    
    if tool_name == "write_code":
        done = await call_llm_claw(f"你是{char_name}，代码已经编写完成{code}，向用户回复代码已经编写完成，任务结束，自然收尾。", lora_name or _current_lora)
        await bot.send(event,done)
        await bot.send(event, message=f"运行结果如下：\n{raw}")
    else:
        done = await call_llm_claw(f"以{char_name}的语气报告结果。请求:{user_message}。结果:{raw}", lora_name or _current_lora)
        await bot.send(event, done)
# ============================================
# 启动入口
# ============================================
def init_bot():
    """初始化机器人"""
    import nonebot
    from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter
    from nonebot import on_command, on_message
    
    logger.info("=" * 50)
    logger.info(f"QQ自动回复机器人 - 当前角色: {_current_lora}")
    logger.info("=" * 50)
    logger.info(f"Ollama地址: {config.OLLAMA_BASE_URL}")
    logger.info(f"Ollama模型: {config.OLLAMA_MODEL}")
    logger.info(f"LoRA风格: {'启用' if config.USE_LORA_STYLE else '禁用'} (当前: {_current_lora})")
    logger.info(f"回复延迟: {config.REPLY_DELAY}秒")
    logger.info("=" * 50)
    
    # 初始化NoneBot
    nonebot.init(driver="~fastapi")
    
    # 获取driver
    driver = nonebot.get_driver()
    
    # 注册适配器
    driver.register_adapter(OneBotV11Adapter)
    # ============================================
    # 消息处理器
    # ============================================
    message_handler = on_message(priority=10, block=True)
    @message_handler.handle()
    async def handle_all_messages(bot: Bot, event: MessageEvent):
        """处理所有消息"""
        logger.info("消息处理器被触发")
        logger.info(f"事件类型: {type(event).__name__}")

        # 幂等去重：跳过已处理的消息
        msg_id = str(getattr(event, 'message_id', ''))
        if msg_id and await _is_duplicate_message(msg_id):
            logger.debug(f"跳过重复消息: {msg_id}")
            return

        try:
            if not await should_reply(event):
                logger.info("不满足回复条件，跳过")
                return
            user_message=str(event.message).strip()
            logger.info(f"[路由] user_id={str(event.user_id)}, 是否claw={claw_sessions.get(str(event.user_id), False)}, 消息={user_message[:50]}")
            if not claw_sessions.get(str(event.user_id) , False):
                if user_message=="/claw":
                    if not isinstance(event, PrivateMessageEvent):
                        await message_handler.finish("请在私聊中使用")
                        return
                    if is_superuser(event):
                        claw_sessions[str(event.user_id)]=True
                        await message_handler.finish("你已进入claw模式")
                    else:
                        await message_handler.finish("你不是超级用户，不能使用该命令")
                        return
                else:
                    logger.info(f"[聊天] 普通消息，走{_current_lora}回复")
                    logger.info("开始处理消息...")

                    # 分析型问题偶尔发预消息，模拟思考
                    import random
                    think_keywords = ["为什么", "怎么", "分析", "解释", "说说", "讲讲", "如何"]
                    is_analytical = any(kw in user_message for kw in think_keywords)
                    if is_analytical and len(user_message) > 10 and random.random() < 0.35:
                        try:
                            pre_msgs = ["让我想想哈...", "嗯...我想想~", "这个问题有意思，等我想想~"]
                            await bot.send(event, random.choice(pre_msgs))
                        except Exception:
                            pass

                    reply = await process_message(event)
                    logger.info(f"准备发送回复: {reply[:50]}...")

                    # 多消息分段：按句子边界拆分，模拟真人逐步表达
                    import re, random

                    def _strip_outer_brackets(text: str) -> str:
                        WRAP_PAIRS = [('「', '」'), ('『', '』'), ('"', '"'), ("'", "'")]
                        stripped = text.strip()
                        changed = True
                        while changed:
                            changed = False
                            for left, right in WRAP_PAIRS:
                                if stripped.startswith(left) and stripped.endswith(right):
                                    inner = stripped[len(left):-len(right)]
                                    lc_inner = inner.count(left)
                                    rc_inner = inner.count(right)
                                    if lc_inner == rc_inner:
                                        stripped = inner.strip()
                                        changed = True
                        return stripped

                    def _clean_fragment(text: str) -> str:
                        s = text.strip()
                        if s.startswith('」') and '「' not in s[:s.index('」')]:
                            s = s[1:].strip()
                        if s.endswith('「') and '」' not in s[s.rindex('「'):]:
                            s = s[:-1].strip()
                        if s.startswith('』') and '『' not in s[:s.index('』')]:
                            s = s[1:].strip()
                        if s.endswith('『') and '』' not in s[s.rindex('『'):]:
                            s = s[:-1].strip()
                        for ch in ('"', '"'):
                            if s.startswith(ch) and s.count(ch) % 2 == 1:
                                s = s[1:].strip()
                            if s.endswith(ch) and s.count(ch) % 2 == 1:
                                s = s[:-1].strip()
                        return s

                    def _smart_split_reply(text: str) -> List[str]:
                        if not text or len(text) <= 40:
                            return [text] if text else []

                        cleaned = _strip_outer_brackets(text)

                        PAIRS = [('「', '」'), ('『', '』'), ('【', '】'), ('《', '》'), ('（', '）'), ('"', '"'), ("'", "'")]

                        def _inside_pair(pos: int) -> bool:
                            for left, right in PAIRS:
                                lc = cleaned[:pos].count(left)
                                rc = cleaned[:pos].count(right)
                                if lc > rc:
                                    return True
                            return False

                        SENTENCE_ENDS = set('。！？!?\n')
                        COMMA_PAUSES = set('，,；;…—')

                        split_positions = []
                        i = 0
                        while i < len(cleaned):
                            ch = cleaned[i]
                            if ch in SENTENCE_ENDS and not _inside_pair(i):
                                split_positions.append(i + 1)
                            elif ch in COMMA_PAUSES and not _inside_pair(i):
                                chunk_len = i + 1 - (split_positions[-1] if split_positions else 0)
                                if chunk_len >= 30:
                                    split_positions.append(i + 1)
                            i += 1

                        if not split_positions:
                            return [cleaned]

                        parts = []
                        prev = 0
                        for pos in split_positions:
                            segment = cleaned[prev:pos].strip()
                            if segment:
                                parts.append(segment)
                            prev = pos
                        if prev < len(cleaned):
                            tail = cleaned[prev:].strip()
                            if tail:
                                parts.append(tail)

                        merged = []
                        buf = parts[0] if parts else ""
                        for seg in parts[1:]:
                            if len(buf) < 20:
                                buf += seg
                            else:
                                merged.append(_clean_fragment(buf))
                                buf = seg
                        if buf:
                            merged.append(_clean_fragment(buf))

                        return merged if len(merged) > 1 else [cleaned]

                    parts = _smart_split_reply(reply)
                    if len(parts) > 1 and len(reply) > 40:
                        first = parts[0]
                        rest = "".join(parts[1:])
                        await bot.send(event, first)
                        gap = random.uniform(0.4, 1.0)
                        logger.info(f"分段发送: 第1条已发, {gap:.1f}s后发剩余")
                        await asyncio.sleep(gap)
                        await bot.send(event, rest)
                        await message_handler.finish()
                    else:
                        await message_handler.finish(Message(reply))
                    logger.info("回复发送成功")
            else:
                logger.info(f"[claw] 进入操作模式处理: {user_message[:50]}")
                if user_message=="/exit":
                    del claw_sessions[str(event.user_id)]
                    await message_handler.finish("你已退出claw模式")
                    return
                else:
                    logger.info("开始处理消息...")
                    await handle_claw(bot, user_message, event, _current_lora)
                    logger.info("回复发送成功")
        except FinishedException:
            # 这是NoneBot2的正常异常，表示matcher已结束
            logger.info("消息处理完成")
        except Exception as e:
            logger.error(f"处理消息时出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    # ============================================
    # 命令处理器
    # ============================================
    help_cmd = on_command("help", aliases={"帮助"}, priority=5)
    
    @help_cmd.handle()
    async def handle_help(bot: Bot, event: MessageEvent):
        """帮助命令"""
        char_name = _get_char_name(_current_lora)
        help_text = f"""{char_name} - QQ自动回复机器人

使用说明：
- 私聊直接对话即可获得回复
- 群聊中请@{config.BOT_NAME} 或提到我的名字
- 机器人会记住最近的对话历史

命令：
/help 或 /帮助 - 查看帮助
/clear 或 /清除 - 清除对话历史
/lora - 查看可用角色
/lora <角色名> - 切换到指定角色

当前角色: {_current_lora}"""

        await help_cmd.finish(help_text)

    # 清除历史命令
    clear_cmd = on_command("clear", aliases={"清除"}, priority=5)

    @clear_cmd.handle()
    async def handle_clear(bot: Bot, event: MessageEvent):
        """清除对话历史命令"""
        session_id = str(event.user_id) if isinstance(event, PrivateMessageEvent) else f"{event.group_id}_{event.user_id}"
        session_history.clear_history(session_id)
        await clear_cmd.finish("好啦好啦，对话历史已经清除了~")

    # LoRA切换命令
    lora_cmd = on_command("lora", priority=5)

    @lora_cmd.handle()
    async def handle_lora(bot: Bot, event: MessageEvent):
        """LoRA角色切换命令"""
        global _current_lora
        args = str(event.message).strip().split()
        if len(args) < 2:
            names = ", ".join(LORA_NAMES)
            await lora_cmd.finish(f"可用角色: {names}\n当前: {_current_lora} ({_get_char_name(_current_lora)})\n用法: /lora <角色名>")
            return
        target = args[1].lower()
        if target not in LORA_REGISTRY:
            await lora_cmd.finish(f"没有叫 {target} 的角色哦~ 可用: {', '.join(LORA_NAMES)}")
            return
        if target == _current_lora:
            await lora_cmd.finish(f"已经是 {target} 啦！")
            return
        try:
            _load_7b_model(target)
            await lora_cmd.finish(f"好嘞，现在我是 {target} 啦！")
        except Exception as e:
            logger.error(f"LoRA切换失败: {e}")
            await lora_cmd.finish(f"切换失败: {e}")
    
    logger.info("机器人初始化完成")
    logger.info("提示: 请配置NapCat连接到 ws://服务器IP:8081/onebot/v11/ws")
    logger.info("提示: 使用 /help 或 /帮助 查看帮助")

    # 启动 - 显式指定 host 和 port
    nonebot.run(host="0.0.0.0", port=8081)

if __name__ == "__main__":
    init_bot()
