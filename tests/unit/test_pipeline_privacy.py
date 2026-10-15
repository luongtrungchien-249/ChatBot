"""Cross-stage invariants: public output, history, progress and poetry lifecycle."""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from agents.domain.errors import UpstreamError
from agents.domain.knowledge import RetrievalEvidence
from agents.domain.message import StoredMessage
from agents.pipeline.handle_message import Failed, Handled, ReactLimits, handle_message
from agents.pipeline.stages.generate import FALLBACK_TEXT
from agents.ports.llm import CallContext, ToolCall
from agents.ports.memory import MemoryUnavailableError
from agents.ports.tool import ToolResult
from agents.prompt.context import conversation_turns

from .fakes import FakeLlm, FakeLogger, FakeRateLimit, FakeTools, answer, make_msg, wants_tools
from .test_handle_message import make_deps
from .test_tho_sinh import DUNG_LUAT

RAW = "Key sk-FAKE_REVIEW_ONLY_1234567890 email review@example.invalid"
POETRY = "Viết bài thơ lục bát về con trâu"


async def test_final_stored_and_sent_have_identical_guarded_text() -> None:
    deps = make_deps(llm=FakeLlm(replies=[answer(RAW)]))
    await handle_message(make_msg(), deps)
    text = deps.channel.sent[0]  # type: ignore[attr-defined]
    stored = deps.memory.appended[-1]  # type: ignore[attr-defined]
    assert stored.from_bot and stored.text == text
    assert "sk-FAKE" not in text and "review@example.invalid" not in text


async def test_sse_progress_cannot_bypass_output_policy() -> None:
    events: list[Any] = []
    deps = make_deps(
        llm=FakeLlm(replies=[wants_tools("web_search", text=RAW), answer("Xong.")]),
        tools=FakeTools(), on_react_event=events.append,
    )
    await handle_message(make_msg(), deps)
    thought = next(event for event in events if event.type == "thought")
    assert "sk-FAKE" not in thought.text and "review@example.invalid" not in thought.text


class EvidenceTools(FakeTools):
    async def call_many(
        self, calls: tuple[ToolCall, ...], ctx: CallContext
    ) -> tuple[ToolResult, ...]:
        return tuple(
            ToolResult(
                call.id, call.name, "Đoạn tài liệu có dữ kiện.", True, 1,
                (RetrievalEvidence("chunk-1", "doc-1", 1, "chung", True),),
            )
            for call in calls
        )


async def test_runtime_retrieval_metadata_activates_citation_check() -> None:
    definition = replace(FakeTools().definitions[0], name="search_knowledge_base")
    logger = FakeLogger()
    deps = make_deps(
        llm=FakeLlm(replies=[wants_tools(definition.name), answer("Đáp án không có nguồn.")]),
        tools=EvidenceTools(definitions=(definition,)), logger=logger,
    )
    result = await handle_message(make_msg(), deps)
    assert result.telemetry.generation is not None
    assert result.telemetry.generation.retrieved_chunks == 1
    assert any("khong neu nguon" in event for _, event, _ in logger.records)


async def test_poetry_persists_public_final_and_schedules_maintenance() -> None:
    scheduled: list[Any] = []

    async def schedule(scope: Any) -> None:
        scheduled.append(scope)

    deps = make_deps(llm=FakeLlm(replies=[answer(DUNG_LUAT)]), schedule_maintenance=schedule)
    result = await handle_message(make_msg(POETRY), deps)
    assert isinstance(result, Handled) and result.telemetry.reason == "poetry"
    assert result.telemetry.poetry_calls == 4
    assert deps.memory.appended[-1].text == deps.channel.sent[-1]  # type: ignore[attr-defined]
    assert deps.memory.appended[-1].from_bot  # type: ignore[attr-defined]
    assert len(scheduled) == 1


async def test_poetry_stop_prevents_all_paid_calls() -> None:
    async def stopped() -> bool:
        return True

    llm = FakeLlm(replies=[answer(DUNG_LUAT)])
    result = await handle_message(make_msg(POETRY), make_deps(llm=llm, should_stop=stopped))
    assert result.telemetry.reason == "user_stopped" and result.telemetry.poetry_calls == 0
    assert llm.calls == []


async def test_poetry_budget_rechecked_before_fanout() -> None:
    llm = FakeLlm(replies=[answer(DUNG_LUAT)])
    deps = make_deps(llm=llm, rate_limit=FakeRateLimit(budget_sequence=[True, False]))
    result = await handle_message(make_msg(POETRY), deps)
    assert result.telemetry.reason == "budget" and result.telemetry.poetry_calls == 0
    assert llm.calls == []


async def test_budget_stop_survives_candidate_exception_recovery() -> None:
    llm = FakeLlm(replies=[answer(DUNG_LUAT)])
    deps = make_deps(llm=llm, rate_limit=FakeRateLimit(
        budget_sequence=[True, True, True, False],
    ))
    result = await handle_message(make_msg(POETRY), deps)
    assert result.telemetry.reason == "budget" and result.telemetry.poetry_calls == 1


async def test_poetry_deadline_stops_before_model_call() -> None:
    llm = FakeLlm(replies=[answer(DUNG_LUAT)])
    deps = make_deps(llm=llm, react=ReactLimits(5, -1))
    result = await handle_message(make_msg(POETRY), deps)
    assert result.telemetry.reason == "deadline" and llm.calls == []


@pytest.mark.parametrize("final_attempt", [False, True])
async def test_all_poetry_upstreams_fail_use_retry_and_final_fallback(final_attempt: bool) -> None:
    deps = make_deps(
        llm=FakeLlm(error=RuntimeError("503 upstream")), is_final_attempt=final_attempt,
    )
    result = await handle_message(make_msg(POETRY), deps)
    assert isinstance(result, Failed) and result.replied is final_attempt
    assert result.telemetry.poetry_calls == 4
    assert deps.channel.sent == ([FALLBACK_TEXT] if final_attempt else [])  # type: ignore[attr-defined]


def test_single_oversize_recent_message_cannot_escape_context_cap() -> None:
    row = StoredMessage("u", "User", "x" * 100_000, datetime.now(UTC), True)
    assert conversation_turns((row,), False, FakeLogger()) == ()


@pytest.mark.parametrize("entry", ["facts", "forget", "remember"])
async def test_typed_memory_failure_returns_visible_final_without_model_call(
    entry: str, monkeypatch: Any,
) -> None:
    from unittest.mock import AsyncMock

    llm = FakeLlm(replies=[answer("must not be called")])
    deps = make_deps(llm=llm)
    monkeypatch.setattr(deps.memory, entry, AsyncMock(side_effect=MemoryUnavailableError(
        "unverified memory", UpstreamError("embed", 409),
    )))
    text = {
        "facts": "Câu hỏi thường", "forget": "quên sở thích", "remember": "nhớ giúp: thích trà",
    }[entry]
    result = await handle_message(make_msg(text), deps)
    assert isinstance(result, Failed) and result.replied
    assert result.error == UpstreamError("embed", 409) and llm.calls == []
    assert deps.memory.appended[-1].from_bot  # type: ignore[attr-defined]
