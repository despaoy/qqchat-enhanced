"""Aggregate seed 42/43/44 reports without selecting only the best run."""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SEEDS = (42, 43, 44)
METRICS = (
    "format_correct_rate",
    "average_output_tokens",
    "distinct_1",
    "distinct_2",
    "avg_repetition_rate",
    "average_latency_ms",
    "p95_latency_ms",
)


def summarize(values: list[float]) -> dict[str, Any]:
    return {
        "values": values,
        "mean": round(statistics.mean(values), 6),
        "standard_deviation": round(statistics.stdev(values), 6) if len(values) > 1 else 0.0,
        "minimum": min(values),
        "maximum": max(values),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate canonical Kisaki repetitions")
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    experiments: dict[str, Any] = {}
    errors: list[str] = []
    for experiment in ("e1", "e2"):
        reports = []
        for seed in SEEDS:
            path = args.results_root / experiment / f"seed{seed}" / "character_eval.json"
            if not path.exists():
                errors.append(f"missing {path}")
                continue
            report = json.loads(path.read_text(encoding="utf-8"))
            reports.append((seed, report))
        experiments[experiment] = {
            "seeds": [seed for seed, _ in reports],
            "metrics": {
                metric: summarize([float(report["metrics"][metric]) for _, report in reports])
                for metric in METRICS
                if reports
            },
            "failures": [
                {"seed": seed, "errors": sum(bool(sample.get("error")) for sample in report.get("samples", []))}
                for seed, report in reports
            ],
        }
    comparison = {}
    if not errors:
        for metric in METRICS:
            e1 = experiments["e1"]["metrics"][metric]["mean"]
            e2 = experiments["e2"]["metrics"][metric]["mean"]
            comparison[metric] = {"e1_mean": e1, "e2_mean": e2, "e2_minus_e1": round(e2 - e1, 6)}
    output = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "required_seeds": list(SEEDS),
        "complete": not errors,
        "errors": errors,
        "experiments": experiments,
        "comparison": comparison,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
