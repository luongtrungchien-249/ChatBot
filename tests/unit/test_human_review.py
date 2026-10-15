import hashlib
import json
from pathlib import Path

import pytest

from evals.human_review import (
    CANDIDATE_CATEGORIES,
    DIMENSIONS,
    RUBRIC,
    agreement,
    calibration_report,
    prepare_round,
    reviewer_identity,
    spearman,
    validate_judgments,
)


def test_review_phai_du_bai_va_du_sau_chieu() -> None:
    row = {"id": "a", "scores": dict.fromkeys(DIMENSIONS, 3)}
    assert validate_judgments([row], {"a"})["a"]["cam_xuc"] == 3
    with pytest.raises(ValueError, match="incomplete"):
        validate_judgments([row], {"a", "b"})
    with pytest.raises(ValueError, match="duplicate"):
        validate_judgments([row, row], {"a"})


def test_khong_chap_nhan_nan_va_do_bat_dong() -> None:
    scores = dict.fromkeys(DIMENSIONS, 3.0)
    with pytest.raises(ValueError, match="finite"):
        validate_judgments([{"id": "a", "scores": {**scores, "cam_xuc": float("nan")}}], {"a"})
    assert agreement({"a": scores}, {"a": dict.fromkeys(DIMENSIONS, 5.0)})["cam_xuc"] == 2


@pytest.mark.parametrize(
    "first,second,expected",
    [
        ([1.0, 2.0, 3.0], [3.0, 2.0, 1.0], -1.0),
        ([1.0, 1.0, 3.0], [2.0, 2.0, 4.0], 1.0),
        ([1.0, 1.0, 1.0], [2.0, 3.0, 4.0], None),
        ([1.0, 2.0], [2.0, 3.0], None),
    ],
)
def test_spearman_ties_constants_and_small_samples(
    first: list[float],
    second: list[float],
    expected: float | None,
) -> None:
    assert spearman(first, second) == expected


@pytest.mark.parametrize("repeat", [False, True])
def test_calibration_missing_scores_do_not_authorize_gate(repeat: bool) -> None:
    human = {str(i): dict.fromkeys(DIMENSIONS, float(i)) for i in range(1, 6)}
    machine = {str(i): {"ngon_ngu": i * 2, "y_nghia": 6 - i} for i in range(1, 6)}
    report = calibration_report(human, human, machine, machine if repeat else None)
    assert not report["hard_gate_authorized"]
    assert report["machine_incomplete_or_invalid_rate"] == 1.0
    dimensions = report["dimensions"]
    assert dimensions["ngon_ngu"]["spearman_machine_human_mean"] == 1.0
    assert dimensions["y_nghia"]["decision"] == "exclude"
    assert dimensions["san_sang"]["n"] == 0
    assert dimensions["san_sang"]["spearman_machine_human_mean"] is None
    assert dimensions["ngon_ngu"]["decision"] == "reference_only"


def test_calibration_requires_same_ids_and_numeric_scores() -> None:
    human = {"a": dict.fromkeys(DIMENSIONS, 3.0)}
    with pytest.raises(ValueError, match="exactly"):
        calibration_report(human, human, {})
    with pytest.raises(ValueError, match="booleans"):
        validate_judgments([{"id": "a", "scores": dict.fromkeys(DIMENSIONS, True)}], {"a"})
    machine = {"a": {"ngon_ngu": float("nan"), "y_nghia": True}}
    assert calibration_report(human, human, machine)["dimensions"]["ngon_ngu"]["n"] == 0


def test_rubric_has_five_concrete_anchors_for_every_dimension() -> None:
    assert set(RUBRIC) == set(DIMENSIONS)
    assert all(
        len(anchors) == 5 and all(len(anchor) > 20 for anchor in anchors)
        for anchors in RUBRIC.values()
    )


def test_balanced_metadata_only_checked_when_requested(tmp_path: Path) -> None:
    source = tmp_path / "pool.jsonl"
    source.write_text(
        "\n".join(json.dumps({"tho": f"Distinct fixture {index}"}) for index in range(60)),
        encoding="utf-8",
    )
    assert prepare_round(source, tmp_path / "unbalanced", "fixture") == 60
    with pytest.raises(ValueError, match="category metadata"):
        prepare_round(
            source,
            tmp_path / "balanced",
            "fixture",
            category_minimums=dict.fromkeys(CANDIDATE_CATEGORIES, 10),
        )
    assert not (tmp_path / "balanced").exists()


def test_whitespace_variants_do_not_increase_distinct_poem_count(tmp_path: Path) -> None:
    source = tmp_path / "pool.jsonl"
    rows = [{"tho": f"Distinct fixture {index}"} for index in range(59)]
    rows.append({"tho": "  Distinct   fixture  0  "})
    source.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    with pytest.raises(ValueError, match="59"):
        prepare_round(source, tmp_path / "round", "fixture")


@pytest.mark.parametrize("kind", [None, "agent"])
def test_agent_or_missing_identity_kind_is_not_a_human(kind: str | None) -> None:
    row = {"reviewer_kind": kind, "reviewer_id": hashlib.sha256(b"test-reviewer").hexdigest()}
    with pytest.raises(ValueError, match="human reviewer"):
        reviewer_identity([row])
    row["reviewer_kind"] = "human"
    assert reviewer_identity([row]) == row["reviewer_id"]


def test_soft_guard_candidate_requires_complete_repeat_and_config_attestation() -> None:
    human = {str(index): dict.fromkeys(DIMENSIONS, float(index % 5 + 1)) for index in range(60)}
    base = {
        key: {name: score * 2 for name, score in values.items()} for key, values in human.items()
    }
    report = calibration_report(human, human, base, base, same_judge_config_attested=True)
    assert (
        report["dimensions"]["ngon_ngu"]["decision"]
        == "soft_guard_candidate_requires_stability_review"
    )
    assert not report["hard_gate_authorized"]
    assert (
        calibration_report(human, human, base, base)["dimensions"]["ngon_ngu"]["decision"]
        == "reference_only"
    )
    missing = {key: dict(scores) for key, scores in base.items()}
    missing["0"].pop("ngon_ngu")
    partial = calibration_report(human, human, base, missing, same_judge_config_attested=True)
    assert partial["dimensions"]["ngon_ngu"]["repeat_missing_or_invalid"] == 1
    assert partial["dimensions"]["ngon_ngu"]["decision"] == "reference_only"
    grouped = calibration_report(
        human, human, base, base, categories={key: "lawful_incoherent_candidate" for key in human}
    )
    assert not grouped["category_labels_human_reviewed"]
    assert (
        grouped["proposed_category_analysis"]["lawful_incoherent_candidate"]["reviewed_poems"] == 60
    )
