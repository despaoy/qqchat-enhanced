"""Lightweight, dependency-free artifacts for reproducible LoRA training evaluation."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


def _number(value: Any) -> float | None:
    """Return a finite numeric value, otherwise None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def _series(log_history: Iterable[Dict[str, Any]], key: str) -> List[float]:
    return [number for item in log_history if (number := _number(item.get(key))) is not None]


def _safe_perplexity(loss: float | None) -> float | None:
    if loss is None or loss > 20:
        return None
    return round(math.exp(loss), 6)


def build_training_evaluation(
    eval_results: Dict[str, Any],
    log_history: Iterable[Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a compact evaluation artifact from Trainer metrics and provenance."""
    history = list(log_history)
    train_losses = _series(history, "loss")
    eval_losses = _series(history, "eval_loss")
    final_eval_loss = _number(eval_results.get("eval_loss"))
    if final_eval_loss is None and eval_losses:
        final_eval_loss = eval_losses[-1]

    final_train_loss = train_losses[-1] if train_losses else None
    best_eval_loss = min(eval_losses + ([final_eval_loss] if final_eval_loss is not None else []), default=None)
    useful_config_keys = (
        "base_model_path", "train_data_path", "lora_r", "lora_alpha", "lora_dropout",
        "use_dora", "use_rslora", "neftune_noise_alpha", "packing", "max_seq_length",
        "learning_rate", "num_train_epochs", "seed", "load_in_4bit", "load_in_8bit",
    )
    provenance = {key: config.get(key) for key in useful_config_keys if key in config}

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provenance": provenance,
        "metrics": {
            "final_train_loss": final_train_loss,
            "final_eval_loss": final_eval_loss,
            "best_eval_loss": best_eval_loss,
            "eval_perplexity": _safe_perplexity(final_eval_loss),
            "best_eval_perplexity": _safe_perplexity(best_eval_loss),
            "train_log_points": len(train_losses),
            "eval_log_points": len(eval_losses),
        },
        "raw_eval_results": {
            key: value for key, value in eval_results.items()
            if _number(value) is not None or isinstance(value, str)
        },
        "notes": [
            "This artifact reports training-time metrics only.",
            "Use a held-out prompt suite for qualitative character and safety evaluation.",
        ],
    }


def write_training_evaluation_report(
    output_dir: Path,
    eval_results: Dict[str, Any],
    log_history: Iterable[Dict[str, Any]],
    config: Dict[str, Any],
) -> Path:
    """Persist the evaluation artifact next to the adapter and training config."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "training_evaluation.json"
    report = build_training_evaluation(eval_results, log_history, config)
    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    return report_path
