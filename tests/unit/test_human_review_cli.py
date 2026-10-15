import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from evals.human_review import prepare_round


def cli() -> Any:
    spec = importlib.util.spec_from_file_location(
        "human_review_cli_test",
        Path(__file__).resolve().parents[2] / "ops" / "cham_tay.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def round_fixture(tmp_path: Path) -> Path:
    source = tmp_path / "synthetic.jsonl"
    source.write_text(
        "\n".join(json.dumps({"tho": f"Synthetic poem {i}"}) for i in range(60)), encoding="utf-8"
    )
    target = tmp_path / "round"
    assert prepare_round(source, target, "synthetic-round") == 60
    return target


def test_interactive_judgments_resume_and_no_partial_record(
    tmp_path: Path, monkeypatch: Any
) -> None:
    target, output = round_fixture(tmp_path), tmp_path / "judgments.jsonl"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "review",
            "--score-round",
            str(target),
            "--reviewer-id",
            "opaque-one",
            "--reviewer-kind",
            "human",
            "--judgments-output",
            str(output),
        ],
    )
    for answers in (["nan", "6"] + ["3"] * 6 + ["q"], ["4"] * 6 + ["q"]):
        iterator = iter(answers)
        monkeypatch.setattr("builtins.input", lambda _, iterator=iterator: next(iterator))
        assert cli().main() == 0
    records = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2 and records[0]["id"] != records[1]["id"]
    assert set(records[0]["scores"].values()) == {3.0}
    assert set(records[1]["scores"].values()) == {4.0}
    assert len(records[0]["reviewer_id"]) == 64
    assert "may" not in records[0]


@pytest.mark.parametrize("same_reviewer", [True, False])
def test_empty_or_another_reviewer_output_is_not_overwritten(
    tmp_path: Path,
    monkeypatch: Any,
    same_reviewer: bool,
) -> None:
    target, output = round_fixture(tmp_path), tmp_path / "judgments.jsonl"
    output.write_text(
        json.dumps({"id": "foreign", "reviewer_id": "different", "scores": {}}) + "\n",
        encoding="utf-8",
    )
    previous = output.read_bytes()
    args = ["review", "--score-round", str(target), "--judgments-output", str(output)]
    if same_reviewer:
        args += ["--reviewer-id", "opaque-one"]
    monkeypatch.setattr(sys, "argv", args)
    assert cli().main() == 2
    assert output.read_bytes() == previous


def test_interactive_agent_cannot_write_human_judgments(tmp_path: Path, monkeypatch: Any) -> None:
    target, output = round_fixture(tmp_path), tmp_path / "agent.jsonl"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "review",
            "--score-round",
            str(target),
            "--reviewer-id",
            "agent-opaque",
            "--reviewer-kind",
            "agent",
            "--judgments-output",
            str(output),
        ],
    )
    assert cli().main() == 2
    assert not output.exists()


def test_changed_rubric_cannot_resume_previous_judgments(tmp_path: Path, monkeypatch: Any) -> None:
    target, output = round_fixture(tmp_path), tmp_path / "judgments.jsonl"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "review",
            "--score-round",
            str(target),
            "--reviewer-id",
            "opaque-human",
            "--reviewer-kind",
            "human",
            "--judgments-output",
            str(output),
        ],
    )
    answers = iter(["3"] * 6 + ["q"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert cli().main() == 0
    original = output.read_bytes()
    rubric_path = target / "rubric.json"
    rubric = json.loads(rubric_path.read_text(encoding="utf-8"))
    rubric["anchors"]["ngon_ngu"][0] += " changed"
    rubric_path.write_text(json.dumps(rubric), encoding="utf-8")
    assert cli().main() == 2
    assert output.read_bytes() == original


@pytest.mark.parametrize(
    "kind,same_identity,expected_code",
    [
        ("human", False, 0),
        ("human", True, 2),
        ("agent", False, 2),
    ],
)
def test_two_files_are_not_automatically_two_humans(
    tmp_path: Path,
    monkeypatch: Any,
    kind: str,
    same_identity: bool,
    expected_code: int,
) -> None:
    target = round_fixture(tmp_path)
    blind = json.loads((target / "blind.json").read_text(encoding="utf-8"))
    public_hashes = {
        "blind_sha256": hashlib.sha256((target / "blind.json").read_bytes()).hexdigest(),
        "rubric_sha256": hashlib.sha256((target / "rubric.json").read_bytes()).hexdigest(),
    }
    files = [tmp_path / "one.jsonl", tmp_path / "two.jsonl"]
    for index, output in enumerate(files):
        identity = "same" if same_identity else f"opaque-{index}"
        rows = [
            {
                "id": row["id"],
                "scores": dict.fromkeys(
                    ("ngon_ngu", "y_nghia", "hinh_anh", "cam_xuc", "sang_tao", "san_sang"), 3
                ),
                "reviewer_id": hashlib.sha256(identity.encode()).hexdigest(),
                "reviewer_kind": kind,
                **public_hashes,
            }
            for row in blind
        ]
        output.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    report = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "review",
            "--review-round",
            str(target),
            "--reviewer-one",
            str(files[0]),
            "--reviewer-two",
            str(files[1]),
            "--report-output",
            str(report),
        ],
    )
    assert cli().main() == expected_code
    if expected_code == 0:
        recorded = json.loads(report.read_text(encoding="utf-8"))
        assert recorded["human_review_declared"]
        assert not recorded["independent_human_reviewers_attested"]
        assert not recorded["identity_or_independence_verified_by_tool"]
        assert not recorded["e7_accepted"] and not recorded["hard_gate_authorized"]
    else:
        assert not report.exists()
