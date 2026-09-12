"""Boc SDK OpenAI, implement LlmPort.

Day la NOI DUY NHAT trong codebase biet ten nha cung cap. Doi provider = viet lai
mot file nay, agents/ khong doi mot dong.
"""

import json
import time
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)

from agents.ports.llm import (
    CallContext,
    CheapRoute,
    Effort,
    LlmMessage,
    LlmResult,
    LlmUsage,
    ReplyRoute,
    ToolCall,
    ToolMessage,
    ToolSpec,
    UserMessage,
)
from config import get_settings
from infra.logger import get_logger

from .cost_meter import UsageRecord, record
from .models import (
    CHEAP_TIMEOUT_S,
    MODELS,
    POEM_TIMEOUT_S,
    REPLY_TIMEOUT_S,
    ModelConfig,
    Route,
    model_cho,
)

_log = get_logger()
_EMPTY_USAGE = LlmUsage(
    input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_write_tokens=0
)

_T = TypeVar("_T")

#: Mot client cho MOI endpoint, khoa theo (base_url, api_key).
#:
#: Truoc day la MOT bien toan cuc, vi ca bot chi noi chuyen voi OpenAI. Tu khi route
#: `poem` co the tro sang mot may tu host, mot client khong con du — va dung chung
#: mot client cho hai endpoint se gui khoa cua ben nay sang ben kia.
_clients: dict[tuple[str | None, str | None], AsyncOpenAI] = {}


def _get_client(model: ModelConfig | None = None) -> AsyncOpenAI:
    khoa = (model.base_url if model else None, model.api_key if model else None)
    client = _clients.get(khoa)
    if client is None:
        client = AsyncOpenAI(
            api_key=khoa[1] or get_settings().OPENAI_API_KEY,
            base_url=khoa[0] or None,
            max_retries=0,
        )
        _clients[khoa] = client
    return client


def _to_usage(raw: Any) -> LlmUsage:
    """Chuan hoa usage cua OpenAI ve hop dong cua LlmPort.

    BAY: prompt_tokens cua OpenAI la TONG input, DA BAO GOM phan doc tu cache.
    Hop dong LlmUsage.input_tokens la phan tinh gia day du, nen phai tru ra. Cong ca
    hai vao rieng nhau se tinh tien thua phan cache.
    """
    if raw is None:
        return _EMPTY_USAGE
    details = getattr(raw, "prompt_tokens_details", None)
    cached = getattr(details, "cached_tokens", 0) or 0
    return LlmUsage(
        input_tokens=max(0, raw.prompt_tokens - cached),
        output_tokens=raw.completion_tokens,
        cache_read_tokens=cached,
        # OpenAI khong tinh phi ghi cache -> luon 0.
        cache_write_tokens=0,
    )


def _to_openai_tools(tools: tuple[ToolSpec, ...]) -> list[ChatCompletionToolParam]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.input_schema,
            },
        }
        for t in tools
    ]


def _to_openai_messages(
    system: str, messages: tuple[LlmMessage, ...]
) -> list[ChatCompletionMessageParam]:
    """Chuyen hop dong LlmMessage sang dang OpenAI. Union nen phai map tung nhanh."""
    # system dat dau va la HANG SO -> prompt caching bat duoc tien to nay.
    out: list[ChatCompletionMessageParam] = [{"role": "system", "content": system}]

    for m in messages:
        if isinstance(m, UserMessage):
            out.append({"role": "user", "content": m.content})
        elif isinstance(m, ToolMessage):
            out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content})
        elif m.tool_calls:
            out.append(
                {
                    "role": "assistant",
                    "content": m.content or None,
                    "tool_calls": [
                        {
                            "id": c.id,
                            "type": "function",
                            "function": {"name": c.name, "arguments": json.dumps(c.input)},
                        }
                        for c in m.tool_calls
                    ],
                }
            )
        else:
            out.append({"role": "assistant", "content": m.content})
    return out


def _parse_tool_calls(message: Any, trace_id: str) -> tuple[ToolCall, ...]:
    calls: list[ToolCall] = []
    for call in getattr(message, "tool_calls", None) or []:
        if call.type != "function":
            continue
        # arguments hong van phai tra ve loi goi, KHONG duoc bo qua: moi tool_call
        # deu can mot tool_result khop id, thieu mot cai la ca request sau 400.
        try:
            payload = json.loads(call.function.arguments)
        except json.JSONDecodeError:
            _log.error(
                "arguments cua tool khong phai JSON hop le — goi voi input rong",
                trace_id=trace_id,
                tool=call.function.name,
            )
            payload = {}
        calls.append(ToolCall(id=call.id, name=call.function.name, input=payload))
    return tuple(calls)


def _finish_reason(raw: str | None) -> Any:
    return raw if raw in ("stop", "tool_calls", "length") else "other"


class OpenAiLlm:
    """Implement LlmPort."""

    async def reply(
        self,
        *,
        system: str,
        messages: tuple[LlmMessage, ...],
        max_tokens: int,
        effort: Effort,
        ctx: CallContext,
        tools: tuple[ToolSpec, ...] = (),
        route: ReplyRoute = "reply",
    ) -> LlmResult:
        return await self._measured(
            "reply",
            ctx,
            lambda: self._do_reply(system, messages, max_tokens, effort, ctx, tools, route),
        )

    async def _do_reply(
        self,
        system: str,
        messages: tuple[LlmMessage, ...],
        max_tokens: int,
        effort: Effort,
        ctx: CallContext,
        tools: tuple[ToolSpec, ...],
        route: ReplyRoute,
    ) -> tuple[LlmResult, LlmUsage]:
        model = model_cho(route)
        extra: dict[str, Any] = {}
        if tools:
            extra["tools"] = _to_openai_tools(tools)
            # Model tu quyet dinh goi hay khong. Ep goi se lam no goi ca khi cau hoi
            # khong can tra cuu gi. Parallel tool calling la MAC DINH, khong tat.
            extra["tool_choice"] = "auto"

        # `reasoning_effort` CHI gui khi model co no. Model tu host (Gemma, Qwen...)
        # khong co tham so nay va se tu choi ca request.
        if model.effort is not None:
            extra["reasoning_effort"] = effort

        response = await _get_client(model).chat.completions.create(
            model=model.id,
            # KHONG phai max_tokens: model reasoning dung max_completion_tokens, va
            # token reasoning an vao cap nay. Xem canh bao trong models.py.
            max_completion_tokens=max_tokens,
            messages=_to_openai_messages(system, messages),
            timeout=POEM_TIMEOUT_S if route == "poem" else REPLY_TIMEOUT_S,
            **extra,
        )

        usage = _to_usage(response.usage)
        if not response.choices:
            raise RuntimeError("OpenAI tra ve response khong co choice nao")
        choice = response.choices[0]
        text = choice.message.content or ""

        # Cap het truoc khi model kip viet cau tra loi: content rong, khong loi nao
        # duoc nem. Phai bat o day, neu khong bot se "im lang" mot cach bi an.
        if choice.finish_reason == "length" and not text:
            details = getattr(response.usage, "completion_tokens_details", None)
            _log.error(
                "het max_completion_tokens truoc khi co cau tra loi — nang cap trong models.py",
                trace_id=ctx.trace_id,
                max_completion_tokens=max_tokens,
                reasoning_tokens=getattr(details, "reasoning_tokens", None),
            )

        result = LlmResult(
            text=text,
            tool_calls=_parse_tool_calls(choice.message, ctx.trace_id),
            usage=usage,
            finish_reason=_finish_reason(choice.finish_reason),
        )
        return result, usage

    async def cheap(
        self,
        *,
        system: str,
        input: str,
        max_tokens: int,
        route: CheapRoute,
        ctx: CallContext,
    ) -> str:
        async def call() -> tuple[str, LlmUsage]:
            model = MODELS[route]
            them: dict[str, Any] = {}
            if model.effort is not None:
                them["reasoning_effort"] = model.effort
            response = await _get_client(model).chat.completions.create(
                model=model.id,
                max_completion_tokens=max_tokens,
                **them,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": input},
                ],
                # Duong nen khong nhay latency nhu duong tra loi, nhung van phai co
                # tran: mac dinh cua SDK du de treo ca mot job.
                timeout=CHEAP_TIMEOUT_S,
            )
            usage = _to_usage(response.usage)
            text = response.choices[0].message.content if response.choices else ""
            return text or "", usage

        return await self._measured(route, ctx, call)

    async def _measured(
        self,
        route: Route,
        ctx: CallContext,
        call: Callable[[], Awaitable[tuple[_T, LlmUsage]]],
    ) -> _T:
        """Gom phan lap lai: do thoi gian, ghi cost du thanh hay bai."""
        started = time.monotonic()
        usage = _EMPTY_USAGE
        ok = False
        try:
            value, usage = await call()
            ok = True
            return value
        finally:
            # L6: moi loi goi ra ngoai deu duoc do cost, ke ca lan that bai.
            await record(
                UsageRecord(
                    route=route,
                    usage=usage,
                    scope=ctx.scope,
                    sender_id=ctx.sender_id,
                    trace_id=ctx.trace_id,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    ok=ok,
                )
            )


llm = OpenAiLlm()
