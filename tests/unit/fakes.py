"""Cai gia cho moi port.

Duong ong phai chay duoc HOAN TOAN khong can Postgres, Redis hay API key. Do la ly
do ton tai cua agents/ports — neu test bat dau can Docker thi mot rang buoc kien
truc da bi pha o dau do.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from agents.domain.message import InboundMessage, StoredMessage
from agents.domain.thread import ThreadScope
from agents.ports.knowledge import RetrievedChunk
from agents.ports.llm import (
    CallContext,
    Effort,
    LlmMessage,
    LlmResult,
    LlmUsage,
    ToolCall,
    ToolSpec,
)
from agents.ports.memory import Fact, NewFact, NewMessage
from agents.ports.ratelimit import Allowed, Denied, LimitVerdict
from agents.ports.tool import ToolDefinition, ToolRequirements, ToolResult

USAGE = LlmUsage(input_tokens=10, output_tokens=5, cache_read_tokens=0, cache_write_tokens=0)

TOOL_DEF = ToolDefinition(
    name="web_search",
    description="tim web",
    parameters={"type": "object"},
    requirements=ToolRequirements(rate_limit="-", cost_per_call="-", timeout_ms=1000),
    returns="-",
    failure_modes=(),
)


def make_msg(text: str = "deadline bao cao quy 3 la ngay nao", **over: Any) -> InboundMessage:
    base: dict[str, Any] = {
        "platform": "cli",
        "thread_id": "t1",
        "sender_id": "u1",
        "sender_name": "Nam",
        "text": text,
        "is_group": False,
        "mentioned_bot": True,
        "message_id": "m1",
        "timestamp": 0,
        "trace_id": "tr1",
    }
    base.update(over)
    return InboundMessage(**base)


def answer(text: str) -> LlmResult:
    return LlmResult(text=text, tool_calls=(), usage=USAGE, finish_reason="stop")


def wants_tools(*names: str, text: str = "") -> LlmResult:
    calls = tuple(
        ToolCall(id=f"call-{i}", name=name, input={"query": "x"}) for i, name in enumerate(names)
    )
    return LlmResult(text=text, tool_calls=calls, usage=USAGE, finish_reason="tool_calls")


class FakeLogger:
    """Im lang, nhung van ghi lai de test kiem tra khi can."""

    def __init__(self) -> None:
        self.records: list[tuple[str, str, dict[str, Any]]] = []

    def _log(self, level: str, event: str, **kw: Any) -> None:
        self.records.append((level, event, kw))

    def debug(self, event: str, **kw: Any) -> None:
        self._log("debug", event, **kw)

    def info(self, event: str, **kw: Any) -> None:
        self._log("info", event, **kw)

    def warning(self, event: str, **kw: Any) -> None:
        self._log("warning", event, **kw)

    def error(self, event: str, **kw: Any) -> None:
        self._log("error", event, **kw)

    def bind(self, **kw: Any) -> "FakeLogger":
        return self


@dataclass
class FakeLlm:
    replies: list[LlmResult] = field(default_factory=list)
    error: BaseException | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def reply(
        self,
        *,
        system: str,
        messages: tuple[LlmMessage, ...],
        max_tokens: int,
        effort: Effort,
        ctx: CallContext,
        tools: tuple[ToolSpec, ...] = (),
    ) -> LlmResult:
        self.calls.append({"system": system, "messages": messages, "tools": tools})
        if self.error is not None:
            raise self.error
        index = min(len(self.calls) - 1, len(self.replies) - 1)
        return self.replies[index]

    async def cheap(self, **kw: Any) -> str:
        return ""


@dataclass
class FakeMemory:
    appended: list[NewMessage] = field(default_factory=list)
    recent_messages: list[StoredMessage] = field(default_factory=list)
    stored_summary: str | None = None
    stored_facts: list[Fact] = field(default_factory=list)
    forget_matches: list[Fact] = field(default_factory=list)
    staged: list[tuple[str, list[str]]] = field(default_factory=list)
    #: So fact ma confirm_forget() se bao la da xoa. 0 = khong co gi dang cho.
    confirm_result: int = 0
    confirm_choices: list[tuple[int, ...]] = field(default_factory=list)

    async def append(self, scope: ThreadScope, msg: NewMessage) -> None:
        self.appended.append(msg)

    async def recent(self, scope: ThreadScope, limit: int) -> list[StoredMessage]:
        return self.recent_messages

    async def summary(self, scope: ThreadScope) -> str | None:
        return self.stored_summary

    async def facts(self, scope: ThreadScope, subject_id: str, query: str) -> list[Fact]:
        return self.stored_facts

    async def remember(self, scope: ThreadScope, fact: NewFact) -> None:
        return None

    async def forget(self, scope: ThreadScope, actor_id: str, pattern: str) -> list[Fact]:
        return self.forget_matches

    async def stage_forget(self, scope: ThreadScope, actor_id: str, fact_ids: list[str]) -> None:
        self.staged.append((actor_id, fact_ids))

    async def confirm_forget(
        self, scope: ThreadScope, actor_id: str, choices: tuple[int, ...] = ()
    ) -> int:
        self.confirm_choices.append(choices)
        return self.confirm_result

    async def list_facts(self, scope: ThreadScope, subject_id: str) -> list[Fact]:
        return self.stored_facts


class FakeKnowledge:
    async def search(self, query: str, k: int) -> list[RetrievedChunk]:
        return []


@dataclass
class FakeChannel:
    sent: list[str] = field(default_factory=list)
    max_message_chars: int = 4000
    typing_error: BaseException | None = None
    typing_hangs: bool = False

    async def typing(self, scope: ThreadScope) -> None:
        if self.typing_error is not None:
            raise self.typing_error
        if self.typing_hangs:
            import asyncio

            await asyncio.sleep(3600)

    async def send(self, scope: ThreadScope, text: str, reply_to: str | None = None) -> None:
        self.sent.append(text)


@dataclass
class FakeRateLimit:
    budget_ok: bool = True
    budget_calls: int = 0
    #: Lan lượt tra ve cac gia tri nay; het thi dung gia tri cuoi.
    budget_sequence: list[bool] | None = None
    #: None = khong bi chan. Dat mot Denied de mo phong bi rate limit.
    denied: Denied | None = None
    #: Con duoc phep gui cau nhac khong (co cooldown 5 phut o ban that).
    warn_allowed: bool = True
    warn_calls: int = 0

    async def check(self, scope: ThreadScope, sender_id: str) -> LimitVerdict:
        return self.denied if self.denied is not None else Allowed()

    async def should_warn(self, scope: ThreadScope) -> bool:
        self.warn_calls += 1
        return self.warn_allowed

    async def within_daily_budget(self) -> bool:
        self.budget_calls += 1
        if self.budget_sequence:
            index = min(self.budget_calls - 1, len(self.budget_sequence) - 1)
            return self.budget_sequence[index]
        return self.budget_ok


@dataclass
class FakeTools:
    definitions: tuple[ToolDefinition, ...] = (TOOL_DEF,)
    ok: bool = True
    batches: list[tuple[ToolCall, ...]] = field(default_factory=list)

    def specs(self) -> tuple[ToolDefinition, ...]:
        return self.definitions

    async def call_many(
        self, calls: tuple[ToolCall, ...], ctx: CallContext
    ) -> tuple[ToolResult, ...]:
        self.batches.append(calls)
        return tuple(
            ToolResult(
                tool_call_id=c.id,
                name=c.name,
                content=f"<ket_qua_cong_cu>ket qua cho {c.name}</ket_qua_cong_cu>"
                if self.ok
                else "Cong cu loi.",
                ok=self.ok,
                latency_ms=5,
            )
            for c in calls
        )


class FakeClock:
    def now(self) -> datetime:
        return datetime(2026, 1, 1, tzinfo=UTC)
