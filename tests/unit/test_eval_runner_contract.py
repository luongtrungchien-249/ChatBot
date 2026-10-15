import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from evals import runner
from evals.corpus_contract import CorpusCheck
from evals.dataset_contract import split_for_id
from evals.metrics.final_answer import FinalAnswerJudgment
from llm.models import MODELS


@pytest.fixture(autouse=True)
def console_no_reconfigure(monkeypatch: Any) -> None:
    monkeypatch.setattr(runner, "_cho_phep_in_tieng_viet", lambda: None)
    monkeypatch.setattr(
        runner, "judge_final_answer", AsyncMock(return_value=FinalAnswerJudgment(False, (), ()))
    )


@pytest.fixture
def eval_fixture(tmp_path: Path, monkeypatch: Any) -> tuple[Path, list[str]]:
    ids = [f"dev{i}" for i in range(30) if split_for_id(f"dev{i}") == "development"][:2]
    dataset = tmp_path / "data.jsonl"
    dataset.write_text(
        "\n".join(
            json.dumps(
                {
                    "id": identifier,
                    "question": f"Synthetic query word{index}",
                    "expected_chunk_ids": [str(index + 1)],
                    "answer": "Expected",
                }
            )
            for index, identifier in enumerate(ids)
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", ["runner", str(dataset)])
    monkeypatch.setattr(runner, "check_corpus", AsyncMock(return_value=CorpusCheck("same", 2, 2)))
    monkeypatch.setattr(runner, "corpus_fingerprint", AsyncMock(return_value="same"))
    monkeypatch.setattr(runner, "close_db", AsyncMock())
    monkeypatch.setattr(runner, "close_redis", AsyncMock())
    return dataset, ids


@pytest.mark.parametrize(
    "field,value", [("answerable", "false"), ("scope", "web:private"), ("id", "")]
)
def test_runner_rejects_invalid_contract_before_calls(
    tmp_path: Path, field: str, value: str
) -> None:
    dataset = tmp_path / "input.jsonl"
    row = {"id": "one", "question": "Synthetic question", field: value}
    dataset.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError):
        runner.load_dataset(dataset)


def test_runner_uses_answerability_not_legacy_category(tmp_path: Path) -> None:
    dataset = tmp_path / "input.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "id": "one",
                "question": "Synthetic unknown",
                "category": "unanswerable",
                "answerable": False,
            }
        ),
        encoding="utf-8",
    )
    assert not runner.load_dataset(dataset)[0].answerable


async def test_partial_upstream_failure_cannot_pass_gate(
    monkeypatch: Any,
    eval_fixture: tuple[Path, list[str]],
) -> None:
    calls = AsyncMock(side_effect=[object(), ConnectionError("synthetic")])
    monkeypatch.setattr(runner, "run_one", calls)
    monkeypatch.setattr(runner, "report", lambda *_: True)
    monkeypatch.setattr(runner, "close_db", AsyncMock())
    monkeypatch.setattr(runner, "close_redis", AsyncMock())
    assert await runner.main() == runner.EXIT_TRUOT
    assert calls.await_count == 2


async def test_unanswerable_recall_is_not_invented(monkeypatch: Any) -> None:
    monkeypatch.setattr(runner, "knowledge", SimpleNamespace(search=AsyncMock(return_value=[])))
    monkeypatch.setattr(
        runner,
        "llm",
        SimpleNamespace(reply=AsyncMock(return_value=SimpleNamespace(text="Unavailable"))),
    )
    monkeypatch.setattr(runner, "judge_faithfulness", AsyncMock(return_value=1.0))
    outcome = await runner.run_one(
        runner.Row("synthetic", "Synthetic question", "", [], answerable=False), False
    )
    assert outcome.recall is None


@pytest.mark.parametrize("case", ["success", "all_failed", "changed", "after_unavailable"])
async def test_cli_artifact_on_success_failure_and_corpus_change(
    monkeypatch: Any,
    tmp_path: Path,
    eval_fixture: tuple[Path, list[str]],
    case: str,
) -> None:
    dataset, _ = eval_fixture
    target = tmp_path / "artifact.json"
    monkeypatch.setattr(sys, "argv", ["runner", str(dataset), "--output", str(target)])

    async def run(row: runner.Row, _: bool) -> runner.Outcome:
        if case == "all_failed":
            raise TimeoutError("private-error-body")
        return runner.Outcome(
            row, 0.95, 0.95, None, 0.95, 0.95, 0.95, 0.95, 100, "private-answer", refused=False
        )

    calls = AsyncMock(side_effect=run)
    monkeypatch.setattr(runner, "run_one", calls)
    if case == "changed":
        monkeypatch.setattr(runner, "corpus_fingerprint", AsyncMock(return_value="changed"))
    elif case == "after_unavailable":
        monkeypatch.setattr(
            runner, "corpus_fingerprint", AsyncMock(side_effect=ConnectionError("private-dsn"))
        )
    assert await runner.main() == (0 if case == "success" else 1)
    assert calls.await_count == 2
    report = json.loads(target.read_text(encoding="utf-8"))
    assert report["config"]["split"] == "development" and len(report["config_hash"]) == 64
    assert report["totals"]["failed"] == (2 if case == "all_failed" else 0)
    assert report["run_passed"] == (case == "success")
    assert not report["release_gate_b_accepted"]
    assert "private" not in target.read_text(encoding="utf-8")


async def test_preflight_and_overwrite_guards_run_before_paid_calls(
    monkeypatch: Any,
    tmp_path: Path,
    eval_fixture: tuple[Path, list[str]],
) -> None:
    dataset, _ = eval_fixture
    calls = AsyncMock()
    monkeypatch.setattr(runner, "run_one", calls)
    monkeypatch.setattr(runner, "check_corpus", AsyncMock(return_value=CorpusCheck("same", 0, 0)))
    assert await runner.main() == 2
    calls.assert_not_awaited()
    target = tmp_path / "existing.json"
    target.write_text("original", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["runner", str(dataset), "--output", str(target)])
    assert await runner.main() == 1
    assert target.read_text(encoding="utf-8") == "original"
    calls.assert_not_awaited()


async def test_test_split_requires_confirmation(monkeypatch: Any) -> None:
    monkeypatch.setattr(sys, "argv", ["runner", "--split", "test"])
    loader = AsyncMock()
    monkeypatch.setattr(runner, "run_one", loader)
    assert await runner.main() == 1
    loader.assert_not_awaited()


def test_missing_required_judge_is_not_a_pass_with_typed_tool_recall() -> None:
    row = runner.Row("synthetic", "private-query", "Expected", ["1"])
    complete = runner.Outcome(
        row,
        0.95,
        0.95,
        None,
        0.95,
        0.95,
        0.95,
        0.95,
        100,
        "private-answer",
        ("private-tool-query",),
        refused=False,
    )
    assert runner.report([complete], True, True)
    incomplete = runner.Outcome(
        row, None, 0.95, None, None, 0.95, 0.95, 0.95, 100, "private-answer", refused=False
    )
    assert not runner.report([complete, incomplete], True, True)
    assert not runner._dong("Required", None, 0.9, 2, True)


@pytest.mark.parametrize("test_split", [False, True])
async def test_development_and_confirmed_test_never_mix(
    monkeypatch: Any,
    eval_fixture: tuple[Path, list[str]],
    test_split: bool,
) -> None:
    dataset, dev_ids = eval_fixture
    test_id = next(f"held{i}" for i in range(30) if split_for_id(f"held{i}") == "test")
    with dataset.open("a", encoding="utf-8") as stream:
        stream.write(
            "\n"
            + json.dumps(
                {
                    "id": test_id,
                    "question": "Entirely different held-out topic",
                    "expected_chunk_ids": ["3"],
                }
            )
        )
    args = ["runner", str(dataset)]
    if test_split:
        args += ["--split", "test", "--confirm-test"]
        # This unit test isolates selection, not actual dataset acceptance.
        monkeypatch.setattr(runner, "MINIMUM_TOTAL", 3)
        monkeypatch.setattr(runner, "coverage_deficits", lambda _: {})
        monkeypatch.setattr(runner, "annotation_deficits", lambda _: {})
        monkeypatch.setattr(runner, "check_review", lambda *_: {"attested": True})
    monkeypatch.setattr(sys, "argv", args)
    calls = AsyncMock(return_value=object())
    monkeypatch.setattr(runner, "run_one", calls)
    monkeypatch.setattr(runner, "report", lambda *_: True)
    assert await runner.main() == 0
    actual = {call.args[0].id for call in calls.await_args_list}
    assert actual == ({test_id} if test_split else set(dev_ids))


async def test_dataset_change_during_preflight_blocks_paid_calls(
    monkeypatch: Any,
    eval_fixture: tuple[Path, list[str]],
) -> None:
    dataset, _ = eval_fixture

    async def preflight(_: Any) -> CorpusCheck:
        with dataset.open("a", encoding="utf-8") as stream:
            stream.write("\n")
        return CorpusCheck("same", 2, 2)

    calls = AsyncMock()
    monkeypatch.setattr(runner, "check_corpus", preflight)
    monkeypatch.setattr(runner, "run_one", calls)
    assert await runner.main() == 1
    calls.assert_not_awaited()


@pytest.mark.parametrize("case", ["dataset_changed", "dataset_deleted", "source_unavailable"])
async def test_final_input_check_failure_preserves_artifact(
    monkeypatch: Any,
    tmp_path: Path,
    eval_fixture: tuple[Path, list[str]],
    case: str,
) -> None:
    dataset, _ = eval_fixture
    target = tmp_path / "input-failure.json"
    monkeypatch.setattr(sys, "argv", ["runner", str(dataset), "--output", str(target)])

    async def run(row: runner.Row, _: bool) -> runner.Outcome:
        if case == "dataset_changed":
            with dataset.open("a", encoding="utf-8") as stream:
                stream.write("\n")
        elif case == "dataset_deleted":
            dataset.unlink(missing_ok=True)
        return runner.Outcome(
            row, 0.95, 0.95, None, 0.95, 0.95, 0.95, 0.95, 100, "private-answer", refused=False
        )

    monkeypatch.setattr(runner, "run_one", run)
    if case == "source_unavailable":
        # Synchronous identity checks must fail only AFTER the run starts.
        monkeypatch.setattr(
            runner,
            "source_identity",
            Mock(side_effect=[{"source_sha256": "same"}, OSError("private-path")]),
        )
    assert await runner.main() == 1
    report = json.loads(target.read_text(encoding="utf-8"))
    assert report["totals"]["completed"] == 2
    assert not report["run_passed"]
    assert not report["source_stable" if case == "source_unavailable" else "dataset_stable"]
    assert "private" not in target.read_text(encoding="utf-8")


def test_config_fingerprints_reply_and_judge_without_keys() -> None:
    config = runner.run_config(True, True, "development")
    assert config["judge_model"] == MODELS["summarize"].id
    assert len(config["judge_endpoint_sha256"]) == 64
    assert "api_key" not in json.dumps(config).lower()


async def test_confirmed_test_without_review_blocks_provider_calls(
    monkeypatch: Any,
    eval_fixture: tuple[Path, list[str]],
) -> None:
    dataset, _ = eval_fixture
    monkeypatch.setattr(sys, "argv", ["runner", str(dataset), "--split", "test", "--confirm-test"])
    calls = AsyncMock()
    monkeypatch.setattr(runner, "run_one", calls)
    assert await runner.main() == runner.EXIT_CHUA_CO_DU_LIEU
    calls.assert_not_awaited()


def test_config_lock_excludes_split_but_includes_pipeline_and_threshold() -> None:
    development = runner.run_config(True, True, "development")
    test = runner.run_config(True, True, "test")
    assert runner.locked_config_hash(development) == runner.locked_config_hash(test)
    assert runner.locked_config_hash(development) != runner.locked_config_hash(
        {**test, "pipeline": "retrieval"}
    )
