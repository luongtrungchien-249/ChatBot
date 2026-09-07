"""Implement ToolPort.

Day la NOI DUY NHAT biet ten cac nha cung cap cong cu — agents/ chi thay ToolPort.

Them mot cong cu = viet mot file trong tools/ roi them mot dong vao _REGISTRY.
Khong dung agents/, khong dung vong ReAct.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from agents.ports.llm import CallContext, ToolCall
from agents.ports.tool import ToolDefinition, ToolResult
from agents.prompt.instructions import COMPRESS_TOOL_RESULT_INSTRUCTION
from infra.logger import get_logger
from llm.models import MODELS
from llm.openai_client import llm

from .guard import exceeds_tool_budget, wrap_observation
from .knowledge_search import (
    KNOWLEDGE_SEARCH_DEFINITION,
    is_knowledge_search_available,
    run_knowledge_search,
)
from .paper_search import PAPER_SEARCH_DEFINITION, run_paper_search
from .web_search import WEB_SEARCH_DEFINITION, is_web_search_available, run_web_search

_log = get_logger()

Runner = Callable[[dict[str, Any], str], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class Registration:
    definition: ToolDefinition
    run: Runner
    #: Nguon ghi vao the <ket_qua_cong_cu nguon="...">
    source: str
    #: Thieu khoa thi khong khai trong specs().
    available: Callable[[], bool]


async def _run_paper_search(payload: dict[str, Any], trace_id: str) -> str:
    return await run_paper_search(payload, trace_id, _log)


_REGISTRY: tuple[Registration, ...] = (
    Registration(
        definition=WEB_SEARCH_DEFINITION,
        run=run_web_search,
        source="Tavily",
        available=is_web_search_available,
    ),
    Registration(
        definition=PAPER_SEARCH_DEFINITION,
        run=_run_paper_search,
        source="OpenAlex + arXiv + Semantic Scholar + Crossref",
        # Ba trong bon nguon khong can khoa nao ca.
        available=lambda: True,
    ),
    Registration(
        definition=KNOWLEDGE_SEARCH_DEFINITION,
        run=run_knowledge_search,
        source="Tai lieu noi bo",
        # Chua nap tai lieu nao thi khong khai — xem knowledge_search.py.
        available=is_knowledge_search_available,
    ),
)


async def _compress_if_too_long(raw: str, tool_name: str, ctx: CallContext) -> str:
    """Ket qua qua dai thi NEN bang model re, khong cat cung.

    Cat cung mat phan cuoi — ma phan cuoi thuong chua DOI va link nguon, dung thu
    system prompt bat buoc phai trich dan. Nen bang cheap() giu duoc chung.

    Nen that bai thi tra ve nguyen ban: wrap_observation con mot luoi cat cung phia
    sau, va mot cau tra loi bi cat con hon khong co cau tra loi nao.
    """
    if not exceeds_tool_budget(raw):
        return raw

    _log.info("ket qua dai, dang nen", trace_id=ctx.trace_id, tool=tool_name, chars=len(raw))
    try:
        compressed = await llm.cheap(
            system=COMPRESS_TOOL_RESULT_INSTRUCTION,
            input=raw,
            max_tokens=MODELS["compress"].max_tokens,
            route="compress",
            ctx=ctx,
        )
        # Model re co the tra chuoi rong (het cap cho phan reasoning) — dung ban goc.
        return compressed if compressed.strip() else raw
    except Exception as error:
        _log.warning(
            "nen ket qua that bai, dung ban goc va de wrap_observation cat",
            trace_id=ctx.trace_id,
            tool=tool_name,
            err=str(error),
        )
        return raw


async def _run_one(call: ToolCall, ctx: CallContext) -> ToolResult:
    started = time.monotonic()
    registration = next((r for r in _REGISTRY if r.definition.name == call.name), None)

    if registration is None or not registration.available():
        _log.warning("model goi cong cu khong ton tai", trace_id=ctx.trace_id, tool=call.name)
        return ToolResult(
            tool_call_id=call.id,
            name=call.name,
            content=(
                f'Công cụ "{call.name}" không tồn tại hoặc chưa được bật. '
                "Hãy trả lời bằng kiến thức sẵn có và nói rõ là không tra cứu được."
            ),
            ok=False,
            latency_ms=int((time.monotonic() - started) * 1000),
        )

    try:
        _log.info("goi cong cu", trace_id=ctx.trace_id, tool=call.name, input=call.input)
        raw = await _compress_if_too_long(
            await registration.run(call.input, ctx.trace_id), call.name, ctx
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        _log.info("cong cu tra ve", trace_id=ctx.trace_id, tool=call.name, latency_ms=latency_ms)

        return ToolResult(
            tool_call_id=call.id,
            name=call.name,
            # Boc + sanitize + cat tran. Ket qua cong cu la van ban do NGUOI LA soan.
            content=wrap_observation(
                tool_name=call.name,
                source=registration.source,
                content=raw,
                trace_id=ctx.trace_id,
                logger=_log,
            ),
            ok=True,
            latency_ms=latency_ms,
        )
    except Exception as error:
        latency_ms = int((time.monotonic() - started) * 1000)
        _log.error(
            "cong cu loi",
            trace_id=ctx.trace_id,
            tool=call.name,
            latency_ms=latency_ms,
            err=str(error),
        )
        return ToolResult(
            tool_call_id=call.id,
            name=call.name,
            content=(
                f'Công cụ "{call.name}" gặp lỗi: {error}. '
                "Hãy nói thẳng với người dùng là chưa tra cứu được, đừng bịa kết quả."
            ),
            ok=False,
            latency_ms=latency_ms,
        )


class ToolRegistry:
    """Implement ToolPort."""

    def specs(self) -> tuple[ToolDefinition, ...]:
        return tuple(r.definition for r in _REGISTRY if r.available())

    async def call_many(
        self, calls: tuple[ToolCall, ...], ctx: CallContext
    ) -> tuple[ToolResult, ...]:
        """Chay TAT CA loi goi dong thoi va tra ve DU so ket qua.

        Hai luat de sai:
          - Thieu mot tool_call_id la ca request tiep theo 400. Cong cu hong van phai
            co mot ket qua, danh dau la loi.
          - Tra ket qua trong MOT luot. Tach ra nhieu message se am tham day model
            thoi goi song song.
        """
        return tuple(await asyncio.gather(*(_run_one(c, ctx) for c in calls)))


tool_port = ToolRegistry()
