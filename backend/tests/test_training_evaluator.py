from pathlib import Path

from training.evaluator import build_training_evaluation, write_training_evaluation_report


def test_training_evaluation_summarizes_losses_and_provenance(tmp_path: Path):
    report = build_training_evaluation(
        eval_results={"eval_loss": 1.25, "eval_runtime": 2.0},
        log_history=[
            {"loss": 2.0},
            {"loss": 1.5, "eval_loss": 1.4},
            {"loss": 1.2, "eval_loss": 1.1},
        ],
        config={"lora_r": 32, "packing": True, "seed": 42, "ignored": "value"},
    )

    assert report["schema_version"] == 1
    assert report["metrics"]["final_train_loss"] == 1.2
    assert report["metrics"]["final_eval_loss"] == 1.25
    assert report["metrics"]["best_eval_loss"] == 1.1
    assert report["metrics"]["eval_perplexity"] is not None
    assert report["provenance"] == {"lora_r": 32, "packing": True, "seed": 42}

    report_path = write_training_evaluation_report(
        tmp_path,
        {"eval_loss": 1.25},
        [],
        {"lora_r": 32},
    )
    assert report_path == tmp_path / "training_evaluation.json"
    assert report_path.exists()


def test_training_evaluation_handles_invalid_or_extreme_losses():
    report = build_training_evaluation(
        eval_results={"eval_loss": 100.0},
        log_history=[{"loss": "not-a-number"}],
        config={},
    )

    assert report["metrics"]["final_train_loss"] is None
    assert report["metrics"]["eval_perplexity"] is None
