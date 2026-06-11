"""配置与模型状态API"""
import logging

from fastapi import APIRouter, Request, HTTPException

from db.database import db
from app.config import (
    INPUT_VALIDATOR_AVAILABLE,
    CONFIG_SCHEMA,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================
# 系统配置
# ============================================

@router.get("/api/config")
async def get_config():
    """获取系统配置"""
    return {
        "config": db.config
    }


@router.put("/api/config")
async def update_config(request: Request):
    """更新系统配置"""
    new_config = await request.json()
    # 输入验证 - 逐字段验证键值对
    if INPUT_VALIDATOR_AVAILABLE:
        from infra.input_validator import InputValidator
        for key, value in new_config.items():
            # 验证每个键值对
            entry = {"key": str(key), "value": str(value)}
            is_valid, errors = InputValidator.validate(entry, CONFIG_SCHEMA)
            if not is_valid:
                raise HTTPException(status_code=422, detail={"message": f"配置项 '{key}' 验证失败", "errors": errors})
    db.update_config(new_config)
    # 同步OpenAI兼容提供商配置
    compat_keys = {'openaiCompatBaseUrl', 'openaiCompatApiKey', 'openaiCompatModel'}
    if compat_keys & set(new_config.keys()):
        try:
            from inference.model_manager import get_model_manager
            manager = get_model_manager()
            from inference.model_manager import ModelProvider
            provider = manager._providers.get(ModelProvider.OPENAI_COMPAT)
            if provider:
                if 'openaiCompatBaseUrl' in new_config:
                    provider.base_url = new_config['openaiCompatBaseUrl']
                if 'openaiCompatApiKey' in new_config:
                    provider.api_key = new_config['openaiCompatApiKey']
                if 'openaiCompatModel' in new_config:
                    provider.model = new_config['openaiCompatModel']
                    provider._model_name = new_config['openaiCompatModel']
        except Exception as e:
            logger.warning(f"同步OpenAI兼容配置失败: {e}")
    return {"success": True, "message": "配置已更新", "config": db.config}


# ============================================
# 模型状态与提供商
# ============================================

@router.get("/api/model/status")
async def get_model_status():
    """获取模型状态"""
    try:
        from inference.model_manager import get_model_manager
        model_manager = get_model_manager()
        return {
            "success": True,
            "status": model_manager.get_status()
        }
    except Exception as e:
        logger.error(f"获取模型状态失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.put("/api/model/provider")
async def set_model_provider(request: Request):
    """设置模型提供商"""
    try:
        from inference.model_manager import get_model_manager, ModelProvider
        model_manager = get_model_manager()

        body = await request.json()
        provider_name = body.get("provider", "ollama")

        provider_map = {
            "ollama": ModelProvider.OLLAMA,
            "llama_cpp": ModelProvider.LLAMA_CPP,
            "openai_compat": ModelProvider.OPENAI_COMPAT,
            "transformers_peft": ModelProvider.TRANSFORMERS_PEFT,
            "vllm": ModelProvider.VLLM,
            "mock": ModelProvider.MOCK
        }

        if provider_name not in provider_map:
            raise HTTPException(status_code=400, detail="无效的提供商名称")

        success = model_manager.set_provider(provider_map[provider_name])

        if success:
            # 同步更新数据库中的modelProvider配置
            db.update_config({"modelProvider": provider_name})
            # 如果切换到openai_compat，同步API配置
            if provider_name == "openai_compat":
                compat_provider = model_manager.get_current_provider()
                cfg = db.config
                if hasattr(compat_provider, 'api_key') and cfg.get('openaiCompatApiKey'):
                    compat_provider.api_key = cfg['openaiCompatApiKey']
                if hasattr(compat_provider, 'base_url') and cfg.get('openaiCompatBaseUrl'):
                    compat_provider.base_url = cfg['openaiCompatBaseUrl']
                if hasattr(compat_provider, 'model') and cfg.get('openaiCompatModel'):
                    compat_provider.model = cfg['openaiCompatModel']
                    compat_provider._model_name = cfg['openaiCompatModel']
            return {
                "success": True,
                "message": f"已切换到提供商: {provider_name}",
                "status": model_manager.get_status()
            }
        else:
            raise HTTPException(status_code=400, detail="提供商切换失败")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设置提供商失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
