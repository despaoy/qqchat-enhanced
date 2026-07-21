"""Separate structured-citation RAG benchmark for character conversations."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluation.character_benchmark_v3 import _call
from evaluation.experiment_contracts import canonical_json_hash, environment_snapshot, sha256_file, validate_frozen_gold
from evaluation.retrieval_metrics import RetrievalMetrics
from knowledge.rag_helper import get_rag_helper

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _result_id(result: dict[str, Any]) -> str:
    return str(
        result.get("id")
        or result.get("document_id")
        or result.get("doc_id")
        or result.get("chunk_id")
        or ""
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Structured RAG benchmark")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--model", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--formal", action="store_true")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    if args.formal:
        errors = validate_frozen_gold(dataset)
        if errors:
            print(json.dumps({"formal_evaluation_refused": True, "errors": errors}, ensure_ascii=False))
            return 2
    prompts = [
        item for item in dataset.get("prompts", [])
        if item.get("benchmark_suite") == "rag"
    ]
    helper = None if args.mock else get_rag_helper()
    metric = RetrievalMetrics()
    samples: list[dict[str, Any]] = []
    for index, item in enumerate(prompts, 1):
        started = time.perf_counter()
        if args.mock:
            expected = list(item.get("expected_refs", []))
            results = [
                {"id": ref, "title": ref, "content": item.get("gold_answer", ""), "score": 1.0}
                for ref in expected
            ]
            citations = [
                {
                    "source_title": result["title"],
                    "evidence_excerpt": result["content"],
                    "score": 1.0,
                    "content_hash": canonical_json_hash(result["content"]),
                    "kb_revision": "mock",
                    "section": "rag_grounded",
                    "version": "1.0",
                }
                for result in results
            ]
            confidence, abstained = 1.0, False
        else:
            retrieved = helper.retrieve_with_citations(item["prompt"], top_k=args.top_k)
            results = retrieved["results"]
            citations = retrieved["citations"]
            confidence = retrieved["confidence"]
            abstained = retrieved["abstained"]
        retrieval_ms = (time.perf_counter() - started) * 1000
        retrieved_ids = [_result_id(result) for result in results]
        expected_ids = [str(value) for value in item.get("expected_refs", [])]
        evidence = "\n".join(str(result.get("content", "")) for result in results)
        messages = [
            {
                "role": "system",
                "content": (
                    "你是月社妃。只能依据随后提供的证据自然回答；正文不要输出文档ID，"
                    "证据不足时明确拒答。"
                ),
            },
            {"role": "user", "content": f"【证据】\n{evidence}\n\n{item['prompt']}"},
        ]
        if args.mock:
            answer, generation_ms, error = item.get("gold_answer", ""), 10.0, ""
        elif abstained:
            answer, generation_ms, error = "", 0.0, ""
        else:
            answer, generation_ms, error = _call(
                args.base_url,
                args.model,
                messages,
                {
                    "temperature": 0.0,
                    "max_tokens": 256,
                    "enable_thinking": False,
                    "repetition_penalty": 1.0,
                    "frequency_penalty": 0.0,
                },
                args.timeout,
            )
        samples.append(
            {
                "id": item["id"],
                "prompt": item["prompt"],
                "expected_refs": expected_ids,
                "retrieved_ids": retrieved_ids,
                "citations": citations,
                "confidence": confidence,
                "abstained": abstained,
                "recall_at_k": metric.recall_at_k(retrieved_ids, expected_ids, args.top_k),
                "mrr": metric.mrr(retrieved_ids, expected_ids),
                "citation_hit": bool(set(retrieved_ids) & set(expected_ids)),
                "answer": answer,
                "faithfulness": metric.faithfulness(answer, citations) if answer else 0.0,
                "answer_correctness": metric.answer_correctness(answer, item.get("gold_answer", "")) if answer else 0.0,
                "retrieval_latency_ms": round(retrieval_ms, 2),
                "generation_latency_ms": round(generation_ms, 2),
                "error": error,
            }
        )
        print(f"[{index}/{len(prompts)}] {item['id']}")

    def avg(key: str) -> float:
        return round(statistics.mean(float(item[key]) for item in samples), 4) if samples else 0.0

    report = {
        "schema_version": 2,
        "evaluation_status": "formal" if args.formal else "diagnostic",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mock": args.mock,
        "suite": "rag",
        "model": args.model,
        "provenance": {
            **environment_snapshot(PROJECT_ROOT),
            "dataset_sha256": sha256_file(args.dataset),
            "top_k": args.top_k,
            "citation_contract": [
                "source_title",
                "evidence_excerpt",
                "score",
                "content_hash",
                "kb_revision",
                "section",
                "version",
            ],
        },
        "metrics": {
            "total": len(samples),
            "recall_at_k": avg("recall_at_k"),
            "mrr": avg("mrr"),
            "citation_hit_rate": round(sum(item["citation_hit"] for item in samples) / max(len(samples), 1), 4),
            "faithfulness": avg("faithfulness"),
            "answer_correctness": avg("answer_correctness"),
            "abstention_rate": round(sum(item["abstained"] for item in samples) / max(len(samples), 1), 4),
            "average_retrieval_latency_ms": avg("retrieval_latency_ms"),
            "average_generation_latency_ms": avg("generation_latency_ms"),
        },
        "samples": samples,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["metrics"], ensure_ascii=False, indent=2))
    return 0 if not any(item["error"] for item in samples) else 2


if __name__ == "__main__":
    raise SystemExit(main())
