#!/usr/bin/env python3
"""Evaluate manual, rule and intent routing without invoking the language model."""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from inference.lora_router import (
    DEFAULT_PERSONA_ADAPTERS, DEFAULT_PERSONA_KEYWORDS, LoRARouter, RoutingDecision
)


def evaluate(cases: list[dict], mode: str, available_adapters: set[str]) -> dict:
    router = LoRARouter({"enabled": True, "mode": mode, "default_adapter": "default", "persona_keywords": DEFAULT_PERSONA_KEYWORDS, "persona_adapters": DEFAULT_PERSONA_ADAPTERS, "rag_confidence_threshold": 0.5})
    correct = fallback = compatible = 0
    for row in cases:
        trace_id = uuid.uuid4().hex
        if mode == "manual":
            target = row["expected_target"]
            adapter = row["expected_adapter"]
            is_fallback = False
            router.log_routing(RoutingDecision(target=target, adapter_name=adapter, confidence=1.0, reason="manual operator selection"), trace_id)
        else:
            intent = tuple(row.get("intent_result", [])) or None
            decision = router.route(row["query"], intent_result=intent)
            router.log_routing(decision, trace_id)
            target, adapter, is_fallback = decision.target, decision.adapter_name, decision.fallback
        correct += int(target == row["expected_target"] and adapter == row["expected_adapter"])
        fallback += int(is_fallback)
        compatible += int(adapter == "default" or adapter in available_adapters)
    total = len(cases)
    logs = router.get_routing_logs(total)
    return {"mode": mode, "total": total, "routing_accuracy": round(correct / total, 4), "fallback_rate": round(fallback / total, 4), "adapter_compatibility_rate": round(compatible / total, 4), "trace_coverage": round(sum(bool(row["trace_id"]) for row in logs) / total, 4), "manual_is_operator_oracle": mode == "manual"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--available-adapter", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.dataset.read_text(encoding="utf-8"))
    results = [evaluate(data["cases"], mode, set(args.available_adapter)) for mode in ("manual", "rule", "intent")]
    payload = {"schema_version": 1, "experiment_id": "S1-ROUTING", "mock": False, "dataset_status": data.get("status"), "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if all(row["adapter_compatibility_rate"] == 1.0 for row in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())