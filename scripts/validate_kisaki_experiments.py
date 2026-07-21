"""Validate and materialize the canonical KISAKI-E1/E2 experiment registry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND = PROJECT_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from evaluation.experiment_contracts import (  # noqa: E402
    canonical_json_hash,
    environment_snapshot,
    sha256_file,
    validate_e1_e2_pair,
    validate_frozen_gold,
)

EXPERIMENT_DIR = BACKEND / "data" / "character_dialogues" / "experiments"
CONFIG_DIR = EXPERIMENT_DIR / "configs"
E1_CONFIG = CONFIG_DIR / "kisaki_e1_canonical.json"
E2_CONFIG = CONFIG_DIR / "kisaki_e2_canonical.json"
DATASET_MANIFEST = EXPERIMENT_DIR / "canonical_dataset_manifest.json"
REGISTRY_PATH = EXPERIMENT_DIR / "canonical_experiment_registry.json"
GOLD_V2_PATH = BACKEND / "evaluation" / "kisaki_gold_set_v2.json"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def build_registry(*, require_model: bool, formal_eval: bool) -> tuple[dict[str, Any], list[str]]:
    e1 = _load(E1_CONFIG)
    e2 = _load(E2_CONFIG)
    dataset = _load(DATASET_MANIFEST)
    errors = validate_e1_e2_pair(e1, e2)

    for label, config in (("KISAKI-E1", e1), ("KISAKI-E2", e2)):
        for field, manifest_key in (("train_data_path", "train"), ("eval_data_path", "validation")):
            path = _resolve_project_path(config[field])
            expected = dataset[manifest_key]
            if not path.exists():
                errors.append(f"{label} {field} does not exist: {path}")
            elif sha256_file(path) != expected["sha256"]:
                errors.append(f"{label} {field} hash does not match canonical dataset manifest")
        model_path = Path(config["base_model_path"])
        if require_model and not model_path.exists():
            errors.append(f"{label} base model does not exist: {model_path}")
        if model_path.exists():
            model_config_path = model_path / "config.json"
            if not model_config_path.exists():
                errors.append(f"{label} base model has no config.json")
            elif _load(model_config_path).get("quantization_config"):
                errors.append(f"{label} base model is pre-quantized and cannot be used for canonical training")

    gold: dict[str, Any] = {
        "path": GOLD_V2_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "status": "draft_not_present" if not GOLD_V2_PATH.exists() else "unknown",
    }
    if GOLD_V2_PATH.exists():
        gold_data = _load(GOLD_V2_PATH)
        gold["status"] = gold_data.get("status")
        gold["sha256"] = sha256_file(GOLD_V2_PATH)
        if formal_eval:
            errors.extend(validate_frozen_gold(gold_data))
    elif formal_eval:
        errors.append("Frozen Gold v2 is required for formal evaluation")

    registry = {
        "schema_version": 2,
        "series_id": "KISAKI-CANONICAL-E1-E2",
        "status": "ready_for_training" if not errors else "blocked",
        "research_question": "NEFTune alpha=5.0 对月社妃 LoRA 质量、稳定性和成本有何影响？",
        "fixed_contract": {
            "dataset_manifest": DATASET_MANIFEST.relative_to(PROJECT_ROOT).as_posix(),
            "train_sha256": dataset["train"]["sha256"],
            "validation_sha256": dataset["validation"]["sha256"],
            "base_model": "Qwen3-8B-Instruct BF16",
            "seeds": [42, 43, 44],
            "pilot_seed": 42,
            "generation": {
                "temperature": 0.0,
                "max_tokens": 256,
                "enable_thinking": False,
                "repetition_penalty": 1.0,
                "frequency_penalty": 0.0,
            },
        },
        "experiments": [
            {
                "id": "KISAKI-E1",
                "config": E1_CONFIG.relative_to(PROJECT_ROOT).as_posix(),
                "config_sha256": sha256_file(E1_CONFIG),
                "config_contract_sha256": canonical_json_hash(e1),
                "variable": {"neftune_noise_alpha": 0.0},
            },
            {
                "id": "KISAKI-E2",
                "config": E2_CONFIG.relative_to(PROJECT_ROOT).as_posix(),
                "config_sha256": sha256_file(E2_CONFIG),
                "config_contract_sha256": canonical_json_hash(e2),
                "variable": {"neftune_noise_alpha": 5.0},
            },
        ],
        "gold_v2": gold,
        "legacy": {
            "status": "legacy_exploratory_non_comparable",
            "series": ["E1 historical", "E2 historical", "E2' Safety++", "E2'' RAG"],
            "reasons": [
                "training data and evaluation splits changed between runs",
                "Gold v1 prompts influenced supplemental data",
                "generation and safety metric implementations drifted",
            ],
        },
        "environment": environment_snapshot(PROJECT_ROOT),
        "errors": errors,
    }
    return registry, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate canonical Kisaki experiments")
    parser.add_argument("--require-model", action="store_true")
    parser.add_argument("--formal-eval", action="store_true")
    parser.add_argument("--write-registry", action="store_true")
    args = parser.parse_args()
    registry, errors = build_registry(require_model=args.require_model, formal_eval=args.formal_eval)
    if args.write_registry:
        REGISTRY_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(registry, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
