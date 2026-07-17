"""Validate a LoRA training configuration without loading model weights."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from training.trainer import LoRATrainingConfig  # noqa: E402


def gpu_snapshot() -> list[dict]:
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.used,memory.total,utilization.gpu,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=10,
        )
    except Exception:
        return []
    rows = []
    for line in output.splitlines():
        values = [value.strip() for value in line.split(",")]
        if len(values) == 6:
            rows.append(
                {
                    "index": int(values[0]),
                    "name": values[1],
                    "memory_used_mb": int(values[2]),
                    "memory_total_mb": int(values[3]),
                    "utilization_percent": int(values[4]),
                    "temperature_c": int(values[5]),
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="LoRA训练只读预检")
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()

    config = LoRATrainingConfig.load(args.config)
    errors = list(config.validate())
    warnings = []
    base_model = Path(config.base_model_path)
    train_data = Path(config.train_data_path)
    output_dir = Path(config.output_dir)

    model_config = {}
    model_config_path = base_model / "config.json"
    if model_config_path.exists():
        model_config = json.loads(model_config_path.read_text(encoding="utf-8"))
        if model_config.get("quantization_config"):
            errors.append("基础模型包含quantization_config；不要使用AWQ/GPTQ推理模型训练LoRA")

    sample_count = 0
    if train_data.exists():
        try:
            rows = json.loads(train_data.read_text(encoding="utf-8"))
            if not isinstance(rows, list) or not rows:
                errors.append("训练数据必须是非空JSON数组")
            else:
                sample_count = len(rows)
                for index, row in enumerate(rows):
                    conversations = row.get("conversations") if isinstance(row, dict) else None
                    if not isinstance(conversations, list) or len(conversations) < 2:
                        errors.append(f"第{index + 1}条缺少至少两轮conversations")
                        break
                    for message in conversations:
                        if not str(message.get("value", "")).strip():
                            errors.append(f"第{index + 1}条包含空消息")
                            break
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"训练数据无法解析: {exc}")

    parent = output_dir.parent
    if not parent.exists():
        warnings.append(f"输出父目录尚不存在，训练时将创建: {parent}")
    else:
        if not os.access(parent, os.W_OK):
            errors.append(f"输出父目录不可写: {parent}")
    if output_dir.exists() and any(output_dir.iterdir()):
        warnings.append(f"输出目录非空，确认是否需要恢复训练: {output_dir}")

    report = {
        "ok": not errors,
        "config": str(args.config.resolve()),
        "base_model": str(base_model),
        "model_type": model_config.get("model_type"),
        "prequantized": bool(model_config.get("quantization_config")),
        "train_data": str(train_data),
        "sample_count": sample_count,
        "output_dir": str(output_dir),
        "lora": {
            "r": config.lora_r,
            "alpha": config.lora_alpha,
            "use_dora": config.use_dora,
            "use_rslora": config.use_rslora,
            "load_in_4bit": config.load_in_4bit,
            "packing": config.packing,
            "neftune_noise_alpha": config.neftune_noise_alpha,
        },
        "gpus": gpu_snapshot(),
        "warnings": warnings,
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
