"""Offline probes for answer applicability, abstention, provenance and judge failures."""

import dataclasses
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from agents.domain.knowledge import RetrievalEvidence
from agents.ports.tool import ToolResult
from evals import runner
from evals.metrics import claim_faithfulness, faithfulness, final_answer
from evals.metrics._cham import doc_phan_quyet
from evals.metrics.final_answer import FinalAnswerJudgment, parse_judgment
from evals.run_artifact import aggregate, no_answer_summary


def outcome(answerable: bool = True, refused: bool | None = False) -> runner.Outcome:
    row = runner.Row(
        "synthetic", "Question", "Expected", ["chunk"] if answerable else [], answerable=answerable
    )
    return runner.Outcome(
        row,
        0.99 if answerable else None,
        0.99,
        None,
        0.99 if answerable else None,
        0.99 if answerable else None,
        None if refused else 0.99,
        None if refused else 0.99,
        100,
        "Synthetic output",
        refused=refused,
    )


def test_correct_refusal_is_not_a_missing_claim_judgment() -> None:
    answered, refused = outcome(), outcome(False, True)
    assert runner.report([answered, refused], True)
    states = runner.metric_states(refused, True, False)
    assert states["claim_faithfulness"] == states["context_precision"] == "not_applicable"
    measured = aggregate(
        [
            {
                "latency_ms": 100,
                "claim_faithfulness": None,
                "metric_states": {"claim_faithfulness": states["claim_faithfulness"]},
                "answerable": False,
                "refused": True,
            }
        ],
        1,
    )
    assert measured["metrics"]["claim_faithfulness"]["not_applicable_completed"] == 1
    assert measured["metrics"]["claim_faithfulness"]["unknown_completed"] == 0


@pytest.mark.parametrize("answerable,refused", [(True, True), (False, False), (False, None)])
def test_false_refusal_false_answer_or_unknown_fail(answerable: bool, refused: bool | None) -> None:
    assert not runner.report([outcome(), outcome(answerable, refused)], True)


def test_no_answer_confusion_counts_and_undefined_denominator() -> None:
    rows: list[dict[str, Any]] = [
        {"answerable": False, "refused": True},
        {"answerable": False, "refused": False},
        {"answerable": True, "refused": True},
        {"answerable": True, "refused": False},
        {"answerable": False, "refused": None},
    ]
    scores = no_answer_summary(rows, 6)
    assert scores["precision"] == scores["recall"] == scores["false_answer_rate"] == 0.5
    assert scores["measured"] == 4 and scores["unknown"] == 2
    empty = no_answer_summary([{"answerable": True, "refused": False}], 1)
    assert empty["precision"] is None and empty["recall"] is None


def test_bad_category_cannot_hide_in_mean() -> None:
    good = [
        dataclasses.replace(outcome(), row=dataclasses.replace(outcome().row, id=f"good{i}"))
        for i in range(20)
    ]
    bad = dataclasses.replace(
        outcome(), row=dataclasses.replace(outcome().row, loai="cross_language"), context_recall=0.4
    )
    assert runner.measured_quality_gate([*good, bad], True, False)
    assert not runner.report([*good, bad], True)


def test_required_and_forbidden_claims_are_final_answer_gates() -> None:
    item = outcome()
    item = dataclasses.replace(
        item,
        row=dataclasses.replace(
            item.row, required_claims=("12 days",), forbidden_claims=("unlimited leave",)
        ),
        required_claims_recall=1.0,
        forbidden_claims_rate=0.0,
    )
    assert runner.report([item], True)
    for invalid in (
        dataclasses.replace(item, required_claims_recall=0.0),
        dataclasses.replace(item, required_claims_recall=None),
        dataclasses.replace(item, forbidden_claims_rate=1.0),
        dataclasses.replace(item, forbidden_claims_rate=None),
    ):
        assert not runner.report([invalid], True)


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        '{"refused": 1, "required_claims": [true], "forbidden_claims": []}',
        '{"refused": true, "required_claims": [], "forbidden_claims": []}',
        '{"refused": true, "required_claims": ["true"], "forbidden_claims": []}',
    ],
)
def test_malformed_final_judgment_stays_unknown(raw: str) -> None:
    judged = parse_judgment(raw, 1, 0)
    assert judged.refused is None and judged.required_claims_recall is None


async def test_structured_judge_can_classify_mixed_refusal_and_claims(monkeypatch: Any) -> None:
    call = AsyncMock(
        return_value=json.dumps(
            {"refused": False, "required_claims": [True], "forbidden_claims": [False]}
        )
    )
    monkeypatch.setattr(final_answer, "goi_cham", call)
    judged = await final_answer.judge_final_answer(
        "Not covered, but the answer is 12 days.", ("12 days",), ("unlimited",), "fake"
    )
    assert judged == FinalAnswerJudgment(False, (True,), (False,))
    assert call.await_args is not None
    assert "Not covered" in call.await_args.kwargs["input"]


async def test_mixed_refusal_phrase_does_not_skip_claim_check(monkeypatch: Any) -> None:
    call = AsyncMock(return_value="1|12 days\n---\n1|KHONG")
    monkeypatch.setattr(claim_faithfulness, "goi_cham", call)
    assert (
        await claim_faithfulness.judge_claim_faithfulness(
            "Not covered, but 12 days.", "No leave policy", "fake"
        )
        == 0.0
    )
    call.assert_awaited_once()


@pytest.mark.parametrize("raw", ["garbage", "10", "1.9", "comment 1.0", "0.5 because"])
async def test_invalid_legacy_judge_is_unknown_not_zero(monkeypatch: Any, raw: str) -> None:
    monkeypatch.setattr(faithfulness, "llm", SimpleNamespace(cheap=AsyncMock(return_value=raw)))
    assert await faithfulness.judge_faithfulness("q", "a", "c", "fake") is None


def test_duplicate_claim_judgments_are_rejected() -> None:
    assert doc_phan_quyet("1|CO\n1|KHONG\n2|CO", 2) is None


def test_provenance_unknown_empty_and_violations_are_distinct() -> None:
    assert runner.evidence_metrics(None, "team") == (None, None)
    assert runner.evidence_metrics([], "team") == (0.0, 0.0)
    assert runner.evidence_metrics([RetrievalEvidence("chunk")], "team") == (None, None)
    good = RetrievalEvidence("good", "doc", 2, "chung", True)
    bad = RetrievalEvidence("bad", "old-doc", 1, "other-team", False)
    assert runner.evidence_metrics([good, bad], "team") == (0.5, 0.5)
    invalid = dataclasses.replace(outcome(), retrieval_scope_violation_rate=0.5)
    assert not runner.report([invalid], True)


async def test_tool_wrapper_keeps_unknown_and_measured_empty_separate() -> None:
    tool = AsyncMock()
    tool.call_many.return_value = (ToolResult("id", "search_knowledge_base", "empty", True, 1, ()),)
    wrapper = runner._CongCuGhiLai(tool)
    await wrapper.call_many((), None)  # type: ignore[arg-type]
    assert wrapper.retrieval_observed and not wrapper.retrieval_unknown
    tool.call_many.return_value = (ToolResult("id2", "search_knowledge_base", "unknown", True, 1),)
    await wrapper.call_many((), None)  # type: ignore[arg-type]
    assert wrapper.retrieval_unknown


async def test_run_one_correct_refusal_skips_inapplicable_judges(monkeypatch: Any) -> None:
    monkeypatch.setattr(runner, "knowledge", SimpleNamespace(search=AsyncMock(return_value=[])))
    monkeypatch.setattr(
        runner,
        "llm",
        SimpleNamespace(
            reply=AsyncMock(return_value=SimpleNamespace(text="No information is available."))
        ),
    )
    monkeypatch.setattr(runner, "judge_faithfulness", AsyncMock(return_value=1.0))
    monkeypatch.setattr(
        runner, "judge_final_answer", AsyncMock(return_value=FinalAnswerJudgment(True, (), ()))
    )
    claim, relevance = AsyncMock(), AsyncMock()
    monkeypatch.setattr(runner, "judge_claim_faithfulness", claim)
    monkeypatch.setattr(runner, "judge_answer_relevance", relevance)
    measured = await runner.run_one(
        runner.Row("synthetic", "Unanswerable", "", [], answerable=False), True
    )
    assert runner.report([measured], True)
    assert measured.refused is True and measured.claim_faithfulness is None
    claim.assert_not_awaited()
    relevance.assert_not_awaited()


async def test_tool_path_measures_typed_provenance_without_parsing_text(monkeypatch: Any) -> None:
    @dataclasses.dataclass
    class FakeDeps:
        tools: Any
        channel: Any

    tool = AsyncMock()
    evidence = RetrievalEvidence("source-id", "doc", 2, "chung", True)
    tool.call_many.return_value = (
        ToolResult("id", "search_knowledge_base", "Context without IDs", True, 1, (evidence,)),
    )

    async def build(channel: Any) -> FakeDeps:
        return FakeDeps(tool, channel)

    async def handle(_: Any, deps: FakeDeps) -> None:
        await deps.tools.call_many((), None)
        await deps.channel.send(None, "Supported answer")

    monkeypatch.setattr(runner, "build_deps", build)
    monkeypatch.setattr(runner, "handle_message", handle)
    for name in (
        "judge_faithfulness",
        "judge_context_recall",
        "judge_context_precision",
        "judge_claim_faithfulness",
        "judge_answer_relevance",
    ):
        monkeypatch.setattr(runner, name, AsyncMock(return_value=1.0))
    monkeypatch.setattr(
        runner, "judge_final_answer", AsyncMock(return_value=FinalAnswerJudgment(False, (), ()))
    )
    measured = await runner.run_one_qua_cong_cu(
        runner.Row("synthetic", "Question", "Expected", ["source-id"]), True
    )
    assert measured.recall == 1.0
    assert (
        measured.retrieval_scope_violation_rate == measured.retrieval_version_violation_rate == 0.0
    )
    assert runner.report([measured], True, True)
