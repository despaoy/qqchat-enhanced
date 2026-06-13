"""
LoRA训练器兼容层
桥接main.py的API调用到优化版train_lora.py，提供与旧版SimpleLoRATrainer相同的接口。
负责任务队列管理、异步训练调度和状态跟踪。
"""

import logging
import os
import json
import asyncio
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class RTX4060Config:
    """RTX 4060 (8GB) 优化的训练超参数配置。"""
    model_name_or_path: str = ""
    per_device_train_batch_size: int = 2
    gradient_accumulation_steps: int = 4
    max_seq_length: int = 512
    lora_rank: int = 16
    lora_alpha: int = 32
    learning_rate: float = 3e-4
    num_train_epochs: float = 3.0
    fp16: bool = True
    load_in_4bit: bool = True
    use_gradient_checkpointing: bool = True
    lora_dropout: float = 0.1
    warmup_ratio: float = 0.05
    weight_decay: float = 0.01
    max_grad_norm: float = 0.5
    early_stopping_patience: int = 3


@dataclass
class RTX3090Config:
    """RTX 3090 (24GB) 优化的训练超参数配置。

    相比 RTX 4060 (8GB) 的改进：
    - batch_size: 1→4（显存充裕，更大batch训练更稳定）
    - gradient_accumulation: 8→4（等效batch=16，足够收敛）
    - max_seq_length: 512→2048（支持更长多轮对话）
    - lora_rank: 16→32（更高秩，更强的表达能力）
    - lora_alpha: 32→64（与rank等比缩放）
    - load_in_4bit: True→False（显存足够，用FP16精度更高）
    - learning_rate: 3e-4→2e-4（更大batch用更小学习率）
    - lora_dropout: 0.1→0.05（数据量足够，降低正则化）
    - 新增 bf16 支持（Ampere架构原生支持）
    """
    model_name_or_path: str = ""
    per_device_train_batch_size: int = 4
    gradient_accumulation_steps: int = 4
    max_seq_length: int = 2048
    lora_rank: int = 32
    lora_alpha: int = 64
    learning_rate: float = 2e-4
    num_train_epochs: float = 3.0
    fp16: bool = False
    bf16: bool = True
    load_in_4bit: bool = False
    use_gradient_checkpointing: bool = True
    lora_dropout: float = 0.05
    warmup_ratio: float = 0.05
    weight_decay: float = 0.01
    max_grad_norm: float = 0.5
    early_stopping_patience: int = 3


def _resolve_model_path(env_var: str, default_rel: str) -> str:
    p = os.getenv(env_var, default_rel)
    if not os.path.isabs(p):
        p = str(Path(__file__).parent / p)
    return p

RTX_4060_CONFIGS = {
    "qwen2.5-7b": RTX4060Config(
        model_name_or_path=_resolve_model_path("BASE_MODEL_PATH", "models/Qwen2.5-7B-Instruct"),
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        max_seq_length=512,
        lora_rank=16,
        lora_alpha=32,
        learning_rate=3e-4,
        num_train_epochs=3.0,
    ),
}

RTX_3090_CONFIGS = {
    "qwen2.5-7b-3090": RTX3090Config(
        model_name_or_path=_resolve_model_path("BASE_MODEL_PATH", "models/Qwen2.5-7B-Instruct"),
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        max_seq_length=2048,
        lora_rank=32,
        lora_alpha=64,
        learning_rate=2e-4,
        num_train_epochs=3.0,
    ),
}

# 合并所有 GPU 配置，供前端选择
ALL_GPU_CONFIGS = {**RTX_4060_CONFIGS, **RTX_3090_CONFIGS}


class SimpleLoRATrainer:
    """LoRA训练器兼容层，负责训练任务的创建、调度和状态管理。

    内部桥接到train_lora.py的LoRATrainer执行实际训练，通过线程池实现异步训练。
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """初始化训练器兼容层。

        Args:
            base_dir: 基础目录路径，默认为当前文件所在目录
        """
        self.base_dir = base_dir or Path(__file__).parent
        self.loras_dir = self.base_dir / "loras"
        self.loras_dir.mkdir(exist_ok=True)
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self._cancel_events: Dict[str, threading.Event] = {}
        self._lock = asyncio.Lock()

    async def start_training(self, lora_name: str, dataset_path: Path, config: Dict[str, Any]) -> str:
        """启动异步LoRA训练任务。

        Args:
            lora_name: LoRA模型名称
            dataset_path: 训练数据集文件或目录路径
            config: 训练超参数字典

        Returns:
            str: 训练任务ID，用于后续状态查询
        """
        task_id = str(uuid.uuid4())[:8]

        task = {
            "task_id": task_id,
            "lora_name": lora_name,
            "dataset_path": str(dataset_path),
            "config": config,
            "status": "pending",
            "progress": 0.0,
            "current_step": 0,
            "total_steps": 0,
            "loss": None,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "started_at": None,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": None,
            "error_message": None,
            "output_dir": str(self.loras_dir / lora_name),
        }

        async with self._lock:
            self.tasks[task_id] = task
            self._cancel_events[task_id] = threading.Event()

        asyncio.create_task(self._run_training(task_id, lora_name, dataset_path, config))

        logger.info(f"训练任务已创建: {task_id}, LoRA: {lora_name}")
        return task_id

    async def _run_training(self, task_id: str, lora_name: str, dataset_path: Path, config: Dict[str, Any]):
        cancel_event = self._cancel_events.get(task_id)

        async with self._lock:
            self.tasks[task_id]["status"] = "training"
            self.tasks[task_id]["started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            self.tasks[task_id]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            from train_lora import LoRATrainingConfig, LoRATrainer

            train_config = self._build_config(lora_name, dataset_path, config)
            errors = train_config.validate()
            if errors:
                raise ValueError(f"训练配置错误: {'; '.join(errors)}")

            # 检查是否在配置阶段已被取消
            if cancel_event and cancel_event.is_set():
                async with self._lock:
                    if self.tasks[task_id]["status"] != "cancelled":
                        self.tasks[task_id]["status"] = "cancelled"
                        self.tasks[task_id]["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"训练任务在配置阶段被取消: {task_id}")
                return

            config_path = Path(train_config.output_dir) / "training_config_auto.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            train_config.save(config_path)

            trainer = LoRATrainer(train_config)

            async with self._lock:
                if cancel_event and cancel_event.is_set():
                    if self.tasks[task_id]["status"] != "cancelled":
                        self.tasks[task_id]["status"] = "cancelled"
                        self.tasks[task_id]["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    logger.info(f"训练任务在启动前被取消: {task_id}")
                    return
                self.tasks[task_id]["progress"] = 0.1
                self.tasks[task_id]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

            # 在线程中执行阻塞的训练操作，传入取消事件供训练循环检查
            def _train_with_cancel_check():
                if cancel_event and hasattr(trainer, 'cancel_event'):
                    trainer.cancel_event = cancel_event
                return trainer.train()

            output_path = await asyncio.to_thread(_train_with_cancel_check)

            # 检查取消事件
            if cancel_event and cancel_event.is_set():
                async with self._lock:
                    if self.tasks[task_id]["status"] != "cancelled":
                        self.tasks[task_id]["status"] = "cancelled"
                        self.tasks[task_id]["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"训练任务完成后发现已被取消: {task_id}")
                return

            async with self._lock:
                if self.tasks[task_id]["status"] == "cancelled":
                    logger.info(f"训练任务完成后发现已被取消: {task_id}")
                    return
                self.tasks[task_id]["status"] = "completed"
                self.tasks[task_id]["progress"] = 1.0
                self.tasks[task_id]["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                self.tasks[task_id]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                self.tasks[task_id]["output_dir"] = str(output_path)

            logger.info(f"训练任务完成: {task_id}")

        except Exception as e:
            logger.error(f"训练任务失败: {task_id}, 错误: {e}")
            import traceback
            logger.error(traceback.format_exc())
            async with self._lock:
                # 如果已被取消，不覆盖cancelled状态
                if self.tasks[task_id]["status"] == "cancelled":
                    return
                self.tasks[task_id]["status"] = "failed"
                self.tasks[task_id]["error_message"] = str(e)
                self.tasks[task_id]["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                self.tasks[task_id]["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    def _build_config(self, lora_name: str, dataset_path: Path, config: Dict[str, Any]) -> "LoRATrainingConfig":
        from train_lora import LoRATrainingConfig

        dataset_file = self._find_dataset_file(dataset_path)

        train_config = LoRATrainingConfig(
            base_model_path=config.get("model_name_or_path", _resolve_model_path("BASE_MODEL_PATH", "models/Qwen2.5-7B-Instruct")),
            train_data_path=str(dataset_file),
            output_dir=str(self.loras_dir / lora_name),
            lora_r=config.get("lora_rank", 16),
            lora_alpha=config.get("lora_alpha", 32),
            lora_dropout=config.get("lora_dropout", 0.1),
            learning_rate=config.get("learning_rate", 3e-4),
            num_train_epochs=int(config.get("num_train_epochs", 3)),
            per_device_train_batch_size=config.get("per_device_train_batch_size", 2),
            gradient_accumulation_steps=config.get("gradient_accumulation_steps", 4),
            max_seq_length=config.get("max_seq_length", 512),
            warmup_ratio=config.get("warmup_ratio", 0.05),
            weight_decay=config.get("weight_decay", 0.01),
            max_grad_norm=config.get("max_grad_norm", 0.5),
            early_stopping_patience=config.get("early_stopping_patience", 3),
            fp16=config.get("fp16", True),
            bf16=config.get("bf16", False),
            gradient_checkpointing=config.get("use_gradient_checkpointing", True),
        )

        return train_config

    def _find_dataset_file(self, dataset_path: Path) -> Path:
        if dataset_path.is_file():
            return dataset_path

        for name in ["train.json", "data.json", "dataset.json"]:
            candidate = dataset_path / name
            if candidate.exists():
                return candidate

        json_files = list(dataset_path.glob("*.json"))
        if json_files:
            return json_files[0]

        raise FileNotFoundError(f"数据集目录中没有找到JSON文件: {dataset_path}")

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """查询单个训练任务的状态。

        Args:
            task_id: 任务ID

        Returns:
            任务状态字典，包含status、progress等字段，不存在则返回None
        """
        async with self._lock:
            return self.tasks.get(task_id)

    async def get_all_tasks(self) -> List[Dict[str, Any]]:
        async with self._lock:
            self._cleanup_old_tasks()
            return list(self.tasks.values())

    def _cleanup_old_tasks(self, max_completed: int = 50):
        """清理过多的已完成/失败/取消任务，防止tasks字典无限增长。

        保留最新的 max_completed 个已完成任务，删除更早的。
        注意：调用方需持有 self._lock。
        """
        completed = [
            tid for tid, t in self.tasks.items()
            if t.get("status") in ("completed", "failed", "cancelled")
        ]
        if len(completed) > max_completed:
            # 按创建时间排序，删除最旧的
            completed.sort(key=lambda tid: self.tasks[tid].get("created_at", ""))
            for tid in completed[max_completed:]:
                del self.tasks[tid]
                self._cancel_events.pop(tid, None)

    async def cancel_task(self, task_id: str) -> bool:
        async with self._lock:
            task = self.tasks.get(task_id)
            if task and task["status"] in ("pending", "training"):
                task["status"] = "cancelled"
                task["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                task["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                # 设置取消事件，通知训练线程停止
                cancel_event = self._cancel_events.get(task_id)
                if cancel_event:
                    cancel_event.set()
                return True
        return False


_simple_lora_trainer: Optional[SimpleLoRATrainer] = None


def get_simple_lora_trainer() -> SimpleLoRATrainer:
    global _simple_lora_trainer
    if _simple_lora_trainer is None:
        _simple_lora_trainer = SimpleLoRATrainer()
    return _simple_lora_trainer
