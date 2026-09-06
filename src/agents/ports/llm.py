"""Hop dong giua agents/ va tang LLM. Ngan la co chu y."""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeAlias

from ..domain.thread import ThreadScope

LlmRole = Literal["user", "assistant", "tool"]
Effort = Literal["low", "medium", "high"]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """Mot lan model muon goi cong cu.

    `id` la BAT BUOC: OpenAI doi moi ket qua tra ve phai khop `tool_call_id` cua
    loi goi tuong ung. Thieu mot cai la ca request 400.
    """

    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True, slots=True)
class UserMessage:
    content: str
    role: Literal["user"] = "user"


@dataclass(frozen=True, slots=True)
class AssistantMessage:
    content: str
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)
    role: Literal["assistant"] = "assistant"


@dataclass(frozen=True, slots=True)
class ToolMessage:
    tool_call_id: str
    content: str
    role: Literal["tool"] = "tool"


#: Union chu khong phai {role, content} phang: luot assistant co the KHONG co van ban
#: ma chi co loi goi tool, va luot tool phai mang theo tool_call_id. Kieu phang khong
#: bieu dien duoc vong ReAct.
LlmMessage: TypeAlias = UserMessage | AssistantMessage | ToolMessage


@dataclass(frozen=True, slots=True)
class LlmUsage:
    #: Token input tinh gia DAY DU — da tru phan doc tu cache. Nha cung cap bao cao
    #: khac nhau (OpenAI gop ca hai vao prompt_tokens), nen viec chuan hoa thuoc ve
    #: implementation trong llm/, khong phai cho goi.
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    #: OpenAI khong tinh phi ghi cache -> luon 0. Giu cot de doi provider khong phai
    #: doi schema.
    cache_write_tokens: int


@dataclass(frozen=True, slots=True)
class LlmResult:
    text: str
    tool_calls: tuple[ToolCall, ...]
    usage: LlmUsage
    #: 'tool_calls' = model muon goi cong cu roi hoi tiep; 'stop' = da xong.
    finish_reason: Literal["stop", "tool_calls", "length", "other"]


@dataclass(frozen=True, slots=True)
class CallContext:
    """Ai gay ra lan goi nay.

    Bat buoc o MOI lan goi vi L6: khong do duoc cost theo thread va sender thi khong
    biet tien di dau, va bang usage_log (section 6.4) khai ba cot nay NOT NULL.

    Di kem tung lan goi chu khong nam trong constructor: mot LlmPort phuc vu moi
    thread, khong dung mot instance cho moi hoi thoai.
    """

    scope: ThreadScope
    sender_id: str
    trace_id: str


CheapRoute = Literal["rewrite", "summarize", "extract_facts"]


class LlmPort(Protocol):
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
        """Duong phan hoi chinh. `system` phai la HANG SO de prompt caching an."""
        ...

    async def cheap(
        self,
        *,
        system: str,
        input: str,
        max_tokens: int,
        route: CheapRoute,
        ctx: CallContext,
    ) -> str:
        """Model re, chay nen: rewrite / summarize / extract-facts."""
        ...
