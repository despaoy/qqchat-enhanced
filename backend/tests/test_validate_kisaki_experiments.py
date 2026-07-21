import json
import sys

from scripts import validate_kisaki_experiments as validator


def test_custom_registry_output_does_not_modify_tracked_registry(tmp_path, monkeypatch):
    tracked_before = validator.REGISTRY_PATH.read_bytes()
    output = tmp_path / "runtime" / "canonical_experiment_registry.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_kisaki_experiments.py",
            "--write-registry",
            "--registry-output",
            str(output),
        ],
    )

    assert validator.main() == 0
    assert validator.REGISTRY_PATH.read_bytes() == tracked_before
    registry = json.loads(output.read_text(encoding="utf-8"))
    assert registry["schema_version"] == 2
    assert registry["series_id"] == "KISAKI-CANONICAL-E1-E2"
