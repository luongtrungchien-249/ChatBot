import json
from pathlib import Path
from typing import Any

import pytest

from evals.run_artifact import (
    aggregate,
    build_artifact,
    config_hash,
    source_identity,
    write_artifact,
)


def artifact(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "selected": [
            {"id": "one", "category": "single_chunk"},
            {"id": "two", "category": "unanswerable"},
        ],
        "outcomes": [
            {
                "id": "one",
                "category": "single_chunk",
                "faithfulness": 0.95,
                "latency_ms": 250,
                "answer": "private-response",
                "question": "private-query",
            }
        ],
        "failures": [{"id": "two", "error_type": "TimeoutError", "message": "private-secret"}],
        "dataset_sha256": "dataset",
        "corpus_before": "same",
        "corpus_after": "same",
        "config": {"split": "development", "model": "synthetic"},
        "measured_gate_passed": True,
    }
    return build_artifact(**{**values, **overrides})


def test_artifact_keeps_failed_category_and_measurement_denominators(tmp_path: Path) -> None:
    report = artifact()
    assert report["totals"]["attempted"] == 2
    assert report["totals"]["failed"] == 1
    missing = report["categories"]["unanswerable"]
    assert missing["failed"] == 1 and missing["metrics"]["faithfulness"]["mean"] is None
    assert missing["latency_p95_ms"] is None
    assert report["totals"]["metrics"]["recall"]["unmeasured_completed"] == 1
    assert report["totals"]["mean_cost_usd"] is None
    assert not report["run_passed"] and not report["release_gate_b_accepted"]
    target = tmp_path / "artifact.json"
    write_artifact(target, report)
    rendered = target.read_text(encoding="utf-8")
    assert "private" not in rendered
    assert json.loads(rendered) == report
    with pytest.raises(FileExistsError):
        write_artifact(target, report)


@pytest.mark.parametrize("after,stable", [("changed", True), (None, True), ("same", False)])
def test_unstable_inputs_cannot_pass(after: str | None, stable: bool) -> None:
    report = artifact(corpus_after=after, dataset_stable=stable)
    assert not report["run_passed"]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), 1.5, True, "1"])
def test_invalid_score_cannot_serialize_a_green_report(value: Any) -> None:
    with pytest.raises(ValueError, match="metric"):
        aggregate([{"latency_ms": 10, "faithfulness": value}], 1)


def test_ids_categories_and_hash_are_consistent() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        artifact(failures=[{"id": "one", "error_type": "Error"}])
    with pytest.raises(ValueError, match="category"):
        artifact(outcomes=[{"id": "one", "category": "changed", "latency_ms": 1}])
    assert config_hash({"a": 1, "b": 2}) == config_hash({"b": 2, "a": 1})
    assert config_hash({"a": 1}) != config_hash({"a": 2})


def test_source_fingerprint_excludes_env_and_tracks_code(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    code = tmp_path / "src" / "module.py"
    code.write_text("value = 1\n", encoding="utf-8")
    before = source_identity(tmp_path)["source_sha256"]
    (tmp_path / ".env").write_text("PRIVATE_KEY=not-for-artifact", encoding="utf-8")
    assert before == source_identity(tmp_path)["source_sha256"]
    code.write_text("value = 2\n", encoding="utf-8")
    assert before != source_identity(tmp_path)["source_sha256"]


def test_invalid_json_does_not_create_empty_evidence(tmp_path: Path) -> None:
    target = tmp_path / "invalid.json"
    with pytest.raises(ValueError):
        write_artifact(target, {"value": float("nan")})
    assert not target.exists()
