from evaluation.benchmark_gate import compare_reports
from evaluation.character_benchmark import safety_passes


def _report(model, responses, *, safety=1.0, citations=1.0, mock=False):
    return {
        "model": model,
        "mock": mock,
        "dataset_sha256": "fixed-dataset",
        "metrics": {
            "format_correct_rate": 1.0,
            "avg_repetition_rate": 0.0,
            "by_category": {
                "safety": {"safety_pass_rate": safety},
                "rag_grounded": {"citation_accuracy": citations},
            },
        },
        "samples": [
            {"id": str(index), "response": response, "format_ok": True, "error": ""}
            for index, response in enumerate(responses)
        ],
    }


def test_safety_passes_accepts_explicit_refusals_only():
    assert safety_passes("我不会泄露任何令牌。")
    assert safety_passes("抱歉，我不能执行这个请求。")
    assert not safety_passes("好啊。")
    assert not safety_passes("我明白了。")


def test_quality_gate_rejects_short_collapsed_candidate():
    baseline = _report("base", ["这是一个完整并且有依据的回答。"])
    candidate = _report("adapter", ["好。"])
    result = compare_reports(baseline, candidate)
    assert result["passed"] is False
    assert result["checks"]["output_token_ratio"]["passed"] is False


def test_quality_gate_rejects_safety_and_citation_regressions():
    baseline = _report("base", ["这是一个完整回答。"], safety=0.9, citations=1.0)
    candidate = _report("adapter", ["这是一个完整回答。"], safety=0.2, citations=0.0)
    result = compare_reports(baseline, candidate)
    assert result["checks"]["safety_pass_rate"]["passed"] is False
    assert result["checks"]["rag_citation_accuracy"]["passed"] is False

def test_quality_gate_accepts_a_matching_healthy_candidate():
    baseline = _report("base", ["这是一个完整回答。"])
    candidate = _report("adapter", ["这是一个完整回答。"])
    assert compare_reports(baseline, candidate)["passed"] is True


def test_quality_gate_rejects_duplicate_sample_ids():
    baseline = _report("base", ["回答一。", "回答二。"])
    candidate = _report("adapter", ["回答一。", "回答二。"])
    candidate["samples"][1]["id"] = candidate["samples"][0]["id"]
    result = compare_reports(baseline, candidate)
    assert result["checks"]["paired_sample_ids"]["passed"] is False