"""
双模块架构管理器
================
将系统划分为两个独立且可灵活切换的核心模块：

1. 训练与预处理模块 (training)：
   - 快速模型训练、RAG构建、文档嵌入、知识库构建
   - LoRA参数训练与微调
   - 不加载完整本地模型，使用API生成对话

2. 推理与部署模块 (inference)：
   - 本地模型加载、推理执行
   - LoRA动态加载、RAG检索增强
   - 严格内存管理，防止OOM

技术指标：
- 模块切换时间 ≤ 5秒
- 推理模式内存 ≤ 系统可用内存的80%
- 模块切换过程数据与配置保持一致性
"""

import os
import time
import logging
import threading
import psutil
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 枚举与数据类
# ═══════════════════════════════════════════════════════════

class SystemMode(str, Enum):
    TRAINING = "training"       # 训练与预处理模式
    INFERENCE = "inference"     # 推理与部署模式


@dataclass
class MemoryInfo:
    """内存使用信息"""
    total_gb: float
    available_gb: float
    used_gb: float
    percent: float
    gpu_total_gb: float = 0.0
    gpu_used_gb: float = 0.0
    gpu_available_gb: float = 0.0
    gpu_percent: float = 0.0


@dataclass
class ModeSwitchResult:
    """模式切换结果"""
    success: bool
    from_mode: str
    to_mode: str
    switch_time_ms: float
    memory_freed_gb: float
    message: str
    errors: List[str] = field(default_factory=list)


@dataclass
class ModuleStatus:
    """模块状态"""
    mode: str
    memory: MemoryInfo
    inference_model_loaded: bool
    inference_model_name: str = ""
    active_lora: str = ""
    training_active: bool = False
    generation_active: bool = False
    uptime_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════
# 内存监控器
# ═══════════════════════════════════════════════════════════

class MemoryMonitor:
    """内存监控与管理"""

    # 推理模式内存安全阈值：不超过可用内存的80%
    MEMORY_SAFETY_RATIO = 0.80
    # 切换到推理模式前的最小可用内存（GB）
    MIN_AVAILABLE_FOR_INFERENCE = 2.0

    @staticmethod
    def get_memory_info() -> MemoryInfo:
        """获取系统内存信息"""
        mem = psutil.virtual_memory()
        info = MemoryInfo(
            total_gb=mem.total / (1024 ** 3),
            available_gb=mem.available / (1024 ** 3),
            used_gb=mem.used / (1024 ** 3),
            percent=mem.percent,
        )

        # GPU 内存
        try:
            import torch
            if torch.cuda.is_available():
                gpu_total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
                gpu_used = torch.cuda.memory_allocated(0) / (1024 ** 3)
                info.gpu_total_gb = round(gpu_total, 2)
                info.gpu_used_gb = round(gpu_used, 2)
                info.gpu_available_gb = round(gpu_total - gpu_used, 2)
                info.gpu_percent = round(gpu_used / gpu_total * 100, 1) if gpu_total > 0 else 0
        except (ImportError, RuntimeError):
            pass

        return info

    @staticmethod
    def can_load_inference_model() -> tuple[bool, str]:
        """检查是否有足够内存加载推理模型"""
        info = MemoryMonitor.get_memory_info()

        # 检查系统内存
        if info.available_gb < MemoryMonitor.MIN_AVAILABLE_FOR_INFERENCE:
            return False, f"系统可用内存不足: {info.available_gb:.1f}GB < {MemoryMonitor.MIN_AVAILABLE_FOR_INFERENCE}GB"

        # 检查GPU内存（如果有GPU）
        if info.gpu_total_gb > 0:
            # 7B模型4-bit量化约需5GB显存
            estimated_vram = 5.0
            if info.gpu_available_gb < estimated_vram:
                return False, f"GPU可用显存不足: {info.gpu_available_gb:.1f}GB < {estimated_vram}GB (7B 4-bit)"

        return True, "内存充足"

    @staticmethod
    def is_memory_safe() -> bool:
        """检查当前内存使用是否在安全范围内"""
        info = MemoryMonitor.get_memory_info()
        return info.percent <= MemoryMonitor.MEMORY_SAFETY_RATIO * 100

    @staticmethod
    def force_gc():
        """强制垃圾回收，释放内存"""
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except (ImportError, RuntimeError):
            pass


# ═══════════════════════════════════════════════════════════
# 模块管理器
# ═══════════════════════════════════════════════════════════

class ModuleManager:
    """双模块架构管理器

    管理训练/推理两种模式的切换，确保：
    - 切换时自动释放前一模式的资源
    - 推理模式加载模型前检查内存
    - 训练模式不加载本地模型
    - 切换过程数据一致性
    """

    def __init__(self):
        self._mode = SystemMode.TRAINING  # 默认训练模式（不加载模型）
        self._lock = threading.Lock()
        self._switching = False
        self._started_at = time.time()
        self._last_switch_time: Optional[float] = None
        self._switch_history: List[Dict[str, Any]] = []

        # 模式切换前后的回调钩子
        self._pre_switch_hooks: Dict[str, List[Callable]] = {
            "training": [],
            "inference": [],
        }
        self._post_switch_hooks: Dict[str, List[Callable]] = {
            "training": [],
            "inference": [],
        }

        logger.info(f"ModuleManager 初始化完成，默认模式: {self._mode.value}")

    @property
    def mode(self) -> SystemMode:
        return self._mode

    @property
    def is_training_mode(self) -> bool:
        return self._mode == SystemMode.TRAINING

    @property
    def is_inference_mode(self) -> bool:
        return self._mode == SystemMode.INFERENCE

    @property
    def is_switching(self) -> bool:
        return self._switching

    def register_pre_switch_hook(self, target_mode: str, hook: Callable):
        """注册模式切换前的回调"""
        if target_mode in self._pre_switch_hooks:
            self._pre_switch_hooks[target_mode].append(hook)

    def register_post_switch_hook(self, target_mode: str, hook: Callable):
        """注册模式切换后的回调"""
        if target_mode in self._post_switch_hooks:
            self._post_switch_hooks[target_mode].append(hook)

    def get_status(self) -> ModuleStatus:
        """获取当前模块状态"""
        memory = MemoryMonitor.get_memory_info()

        # 检查推理模型是否已加载
        inference_loaded = False
        inference_model_name = ""
        active_lora = ""
        try:
            from inference.model_manager import get_model_manager
            mm = get_model_manager()
            status = mm.get_status()
            current = status.get("currentProvider", "")
            provider_status = status.get("providers", {}).get(current, {})
            inference_loaded = provider_status.get("loaded", False)
            inference_model_name = provider_status.get("modelName", "")
            active_lora = provider_status.get("loraAdapter", "") or ""
        except Exception:
            pass

        # 检查训练/生成是否活跃
        training_active = False
        generation_active = False
        try:
            from app.config import generation_state
            generation_active = generation_state.get("is_generating", False)
        except Exception:
            pass

        return ModuleStatus(
            mode=self._mode.value,
            memory=memory,
            inference_model_loaded=inference_loaded,
            inference_model_name=inference_model_name,
            active_lora=active_lora,
            training_active=training_active,
            generation_active=generation_active,
            uptime_seconds=round(time.time() - self._started_at, 1),
        )

    def switch_to_training(self) -> ModeSwitchResult:
        """切换到训练模式

        释放推理模型占用的GPU/系统内存，确保训练资源充足。
        """
        return self._switch_mode(SystemMode.TRAINING)

    def switch_to_inference(self) -> ModeSwitchResult:
        """切换到推理模式

        加载本地模型，检查内存是否充足。
        """
        return self._switch_mode(SystemMode.INFERENCE)

    def _switch_mode(self, target: SystemMode) -> ModeSwitchResult:
        """执行模式切换"""
        with self._lock:
            if self._switching:
                return ModeSwitchResult(
                    success=False,
                    from_mode=self._mode.value,
                    to_mode=target.value,
                    switch_time_ms=0,
                    memory_freed_gb=0,
                    message="模式切换正在进行中，请稍后",
                )

            if self._mode == target:
                return ModeSwitchResult(
                    success=True,
                    from_mode=target.value,
                    to_mode=target.value,
                    switch_time_ms=0,
                    memory_freed_gb=0,
                    message=f"已在{target.value}模式",
                )

            self._switching = True
            start_time = time.time()
            from_mode = self._mode
            errors = []

        # 记录切换前内存
        mem_before = MemoryMonitor.get_memory_info()

        try:
            # 1. 执行目标模式的预切换钩子
            for hook in self._pre_switch_hooks.get(target.value, []):
                try:
                    hook(from_mode.value, target.value)
                except Exception as e:
                    logger.warning(f"预切换钩子执行失败: {e}")
                    errors.append(f"预切换钩子错误: {e}")

            # 2. 释放当前模式的资源
            if from_mode == SystemMode.INFERENCE:
                # 从推理模式切出 → 释放模型
                self._unload_inference_model()
            elif from_mode == SystemMode.TRAINING:
                # 从训练模式切出 → 确保生成任务已完成或取消
                self._ensure_training_idle()

            # 3. 强制GC释放内存
            MemoryMonitor.force_gc()
            time.sleep(0.5)  # 等待GC完成

            # 4. 检查目标模式的资源需求
            if target == SystemMode.INFERENCE:
                can_load, reason = MemoryMonitor.can_load_inference_model()
                if not can_load:
                    self._switching = False
                    return ModeSwitchResult(
                        success=False,
                        from_mode=from_mode.value,
                        to_mode=target.value,
                        switch_time_ms=round((time.time() - start_time) * 1000, 0),
                        memory_freed_gb=0,
                        message=f"无法切换到推理模式: {reason}",
                        errors=[reason],
                    )

            # 5. 更新模式
            with self._lock:
                self._mode = target
                self._last_switch_time = time.time()

            # 6. 执行目标模式的后切换钩子
            for hook in self._post_switch_hooks.get(target.value, []):
                try:
                    hook(from_mode.value, target.value)
                except Exception as e:
                    logger.warning(f"后切换钩子执行失败: {e}")
                    errors.append(f"后切换钩子错误: {e}")

            # 计算释放的内存
            mem_after = MemoryMonitor.get_memory_info()
            memory_freed = round(mem_before.used_gb - mem_after.used_gb, 2)
            if memory_freed < 0:
                memory_freed = 0

            switch_time_ms = round((time.time() - start_time) * 1000, 0)

            # 记录切换历史
            record = {
                "from": from_mode.value,
                "to": target.value,
                "time": datetime.now().isoformat(),
                "switch_ms": switch_time_ms,
                "freed_gb": memory_freed,
            }
            self._switch_history.append(record)
            if len(self._switch_history) > 50:
                self._switch_history = self._switch_history[-50:]

            mode_label = "训练与预处理" if target == SystemMode.TRAINING else "推理与部署"
            logger.info(f"✅ 模式切换完成: {from_mode.value} → {target.value} ({switch_time_ms:.0f}ms, 释放{memory_freed}GB)")

            return ModeSwitchResult(
                success=True,
                from_mode=from_mode.value,
                to_mode=target.value,
                switch_time_ms=switch_time_ms,
                memory_freed_gb=memory_freed,
                message=f"已切换到{mode_label}模式",
                errors=errors if errors else [],
            )

        except Exception as e:
            logger.error(f"模式切换异常: {e}")
            return ModeSwitchResult(
                success=False,
                from_mode=from_mode.value,
                to_mode=target.value,
                switch_time_ms=round((time.time() - start_time) * 1000, 0),
                memory_freed_gb=0,
                message=f"模式切换失败: {e}",
                errors=[str(e)],
            )
        finally:
            self._switching = False

    def _unload_inference_model(self):
        """卸载推理模型，释放GPU/系统内存"""
        try:
            from inference.model_manager import get_model_manager, ModelProvider
            mm = get_model_manager()

            # 获取TransformersPeftProvider并卸载模型
            peft_provider = mm._providers.get(ModelProvider.TRANSFORMERS_PEFT)
            if peft_provider and hasattr(peft_provider, '_model') and peft_provider._model is not None:
                logger.info("正在卸载本地推理模型...")
                import torch

                # 释放LoRA
                if hasattr(peft_provider, '_lora_path'):
                    peft_provider._lora_path = None

                # 释放模型
                del peft_provider._model
                peft_provider._model = None

                # 释放tokenizer
                if hasattr(peft_provider, '_tokenizer') and peft_provider._tokenizer is not None:
                    del peft_provider._tokenizer
                    peft_provider._tokenizer = None

                peft_provider._loaded = False

                # 清理GPU缓存
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    vram = torch.cuda.memory_allocated() / (1024 ** 3)
                    logger.info(f"GPU显存已释放，当前占用: {vram:.2f}GB")

                logger.info("✅ 推理模型已卸载")

            # 切换到Mock提供商（不加载任何模型）
            mm.set_provider(ModelProvider.MOCK)

        except Exception as e:
            logger.warning(f"卸载推理模型时出错: {e}")

    def _ensure_training_idle(self):
        """确保训练/生成任务已停止"""
        try:
            from app.config import generation_state, generation_state_lock
            with generation_state_lock:
                if generation_state.get("is_generating", False):
                    generation_state["cancel_requested"] = True
                    logger.info("已发送生成任务取消请求")
        except Exception:
            pass

    def get_switch_history(self) -> List[Dict[str, Any]]:
        """获取模式切换历史"""
        return self._switch_history.copy()

    def should_use_local_model(self) -> bool:
        """判断当前是否应该使用本地模型（仅推理模式）"""
        return self._mode == SystemMode.INFERENCE

    def should_use_api_generation(self) -> bool:
        """判断当前是否应该使用API生成对话（训练模式）"""
        return self._mode == SystemMode.TRAINING


# ═══════════════════════════════════════════════════════════
# 全局单例
# ═══════════════════════════════════════════════════════════

_module_manager: Optional[ModuleManager] = None
_manager_lock = threading.Lock()


def get_module_manager() -> ModuleManager:
    """获取全局ModuleManager实例（线程安全单例）"""
    global _module_manager
    if _module_manager is None:
        with _manager_lock:
            if _module_manager is None:
                _module_manager = ModuleManager()
    return _module_manager
