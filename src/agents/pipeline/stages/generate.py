"""Stage 12: vong ReAct — Thought -> Action -> Observation -> lap.

VONG NAY NAM TRONG PIPELINE, KHONG THAY THE PIPELINE. Cac stage truoc van lo policy,
chong trung, ngan sach, dung ngu canh; cac stage sau van lo gui va ghi so. ReAct
khong tu co lop an toan nao trong so do.

Sau chan cung. Thieu cai nao cung thanh vong dot tien khong day:
  1. So vong toi da
  2. Tong so loi goi cong cu
  3. Deadline treo dong ho
  4. Ngan sach ngay — kiem tra lai TRUOC MOI VONG, vi mot cau hoi co the ton nhieu
     lan goi model
  5. Tran kich thuoc observation (ap trong tools/guard.py)
  6. Nguoi dung bam dung
"""

import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from shared.result import Err, Ok, Result

from ...domain.errors import BotError, UpstreamError, UpstreamTimeout
from ...ports.llm import AssistantMessage, CallContext, Effort, LlmMessage, LlmPort, ToolMessage
from ...ports.logger import LoggerPort
from ...ports.ratelimit import RateLimitPort
from ...ports.tool import ToolPort, to_spec
from ...prompt.context import ContextEnvelope

#: Loi tam thoi: cham, 5xx, mat mang. Thu lai THAT SU co the giup.
FALLBACK_TEXT = (
    "Xin lỗi, mình đang bị chậm nên chưa trả lời được câu này. "
    "Bạn thử hỏi lại sau một chút nhé."
)

#: Loi cau hinh (khoa sai/het han). Bao thu lai la NOI DOI: thu bao nhieu lan cung
#: hong cho toi khi co nguoi sua bien moi truong.
#: Khong noi ro "sai API key" trong nhom chat — do la thong tin van hanh, chi thuoc
#: ve log. Nguoi dung chi can biet loi khong nam o phia ho.
CONFIG_ERROR_TEXT = (
    "Mình đang gặp trục trặc kỹ thuật ở phía hệ thống, chưa trả lời được. "
    "Bạn báo giúp người quản trị nhé."
)

#: Het vong ma chua co cau tra loi. KHONG im lang, va KHONG noi doi la da tim xong.
INCOMPLETE_SUFFIX = "\n\n(Mình phải dừng tra cứu ở đây nên câu trả lời có thể chưa đầy đủ.)"

_TIMEOUT_PATTERN = re.compile(r"timeout|timed out|aborted|ETIMEDOUT", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ThoughtEvent:
    iteration: int
    text: str
    type: Literal["thought"] = "thought"


@dataclass(frozen=True, slots=True)
class ToolCallEvent:
    iteration: int
    tools: tuple[str, ...]
    type: Literal["tool_call"] = "tool_call"


@dataclass(frozen=True, slots=True)
class ObservationEvent:
    iteration: int
    tool: str
    ok: bool
    latency_ms: int
    type: Literal["observation"] = "observation"


#: Su kien de UI hien duoc bot dang lam gi. Adapter nao khong quan tam thi bo qua.
ReactEvent: TypeAlias = ThoughtEvent | ToolCallEvent | ObservationEvent


@dataclass(frozen=True, slots=True)
class GenerateDeps:
    llm: LlmPort
    tools: ToolPort
    rate_limit: RateLimitPort
    max_tokens: int
    effort: Effort
    max_iterations: int
    max_tool_calls: int
    deadline_ms: int
    #: Nguoi dung bam dung. Kiem tra moi vong, giong ngan sach.
    should_stop: Callable[[], Awaitable[bool]] | None = None
    #: Khong await: bao tien do khong duoc chan duong tra loi.
    on_event: Callable[[ReactEvent], None] | None = None


def _status_of(error: BaseException) -> int | None:
    """Doc HTTP status tu loi cua SDK ma khong phai import SDK (L1)."""
    status: Any = getattr(error, "status_code", None) or getattr(error, "status", None)
    return status if isinstance(status, int) else None


def _classify(error: BaseException, logger: LoggerPort) -> BotError:
    message = str(error)
    status = _status_of(error)

    if status in (401, 403):
        # Loi cua NGUOI VAN HANH, khong phai cua nguoi dung. Log to len: khong co
        # dong nay thi trieu chung o phia nguoi dung khong he chi ve nguyen nhan that.
        logger.error(
            "API key sai hoac het quyen — KIEM TRA OPENAI_API_KEY", status=status, err=message
        )
    else:
        logger.error("goi model that bai", status=status, err=message)

    # Timeout KHONG retry: nguoi dung da nhan cau fallback roi.
    if _TIMEOUT_PATTERN.search(message):
        return UpstreamTimeout(service="llm")
    return UpstreamError(service="llm", status=status)


def _finish(
    text: str, logger: LoggerPort, *, reason: str, iteration: int
) -> Result[str, BotError]:
    """Ket thuc som: co van ban thi tra ve kem ghi chu chua day du."""
    if not text.strip():
        logger.warning(
            "dung vong ReAct khi chua co van ban nao", reason=reason, iteration=iteration
        )
        return Err(UpstreamTimeout(service="llm"))
    return Ok(text + INCOMPLETE_SUFFIX)


async def generate(
    deps: GenerateDeps,
    prompt: ContextEnvelope,
    ctx: CallContext,
    logger: LoggerPort,
) -> Result[str, BotError]:
    deadline = time.monotonic() + deps.deadline_ms / 1000
    specs = tuple(to_spec(d) for d in deps.tools.specs())
    messages: list[LlmMessage] = list(prompt.messages)

    tool_calls_used = 0
    last_text = ""

    for iteration in range(1, deps.max_iterations + 1):
        # Chan 4: ngan sach kiem tra lai MOI VONG, khong phai mot lan o stage truoc.
        if not await deps.rate_limit.within_daily_budget():
            logger.warning("het ngan sach giua vong ReAct — dung lai", iteration=iteration)
            return _finish(last_text, logger, reason="budget", iteration=iteration)

        # Chan 3: deadline. Con qua it thoi gian thi dung, dung bat dau vong nua.
        if time.monotonic() > deadline:
            logger.warning("het deadline ReAct", iteration=iteration)
            return _finish(last_text, logger, reason="deadline", iteration=iteration)

        # Chan 6: nguoi dung bam dung. Kiem o dau vong chu khong giua mot loi goi —
        # huy nua chung mot request van bi tinh tien ma khong duoc gi.
        if deps.should_stop is not None and await deps.should_stop():
            logger.info("nguoi dung dung vong ReAct", iteration=iteration)
            return _finish(last_text, logger, reason="user_stopped", iteration=iteration)

        # Het luot goi cong cu thi van cho model noi not, nhung khong dua tool nua.
        out_of_tool_calls = tool_calls_used >= deps.max_tool_calls
        last_iteration = iteration == deps.max_iterations
        offer_tools = bool(specs) and not out_of_tool_calls and not last_iteration

        try:
            result = await deps.llm.reply(
                system=prompt.system,
                messages=tuple(messages),
                max_tokens=deps.max_tokens,
                effort=deps.effort,
                ctx=ctx,
                tools=specs if offer_tools else (),
            )
        except Exception as error:
            return Err(_classify(error, logger))

        if result.text:
            last_text = result.text

        # Model da tra loi xong, khong goi them cong cu nao.
        if not result.tool_calls:
            if not result.text.strip():
                logger.error("model tra ve chuoi rong", iteration=iteration)
                return Err(UpstreamError(service="llm"))
            logger.info("ReAct ket thuc", iteration=iteration, tool_calls_used=tool_calls_used)
            return Ok(result.text)

        # --- Co loi goi cong cu: Action ---
        calls = result.tool_calls[: deps.max_tool_calls - tool_calls_used]
        tool_calls_used += len(calls)

        if deps.on_event is not None:
            if result.text:
                deps.on_event(ThoughtEvent(iteration=iteration, text=result.text))
            deps.on_event(ToolCallEvent(iteration=iteration, tools=tuple(c.name for c in calls)))

        # Luot assistant phai mang DUNG cac tool call, neu khong ket qua se khong khop.
        messages.append(AssistantMessage(content=result.text, tool_calls=calls))

        # --- Observation: chay SONG SONG, tra ve DU so ket qua ---
        observations = await deps.tools.call_many(calls, ctx)
        for obs in observations:
            if deps.on_event is not None:
                deps.on_event(
                    ObservationEvent(
                        iteration=iteration, tool=obs.name, ok=obs.ok, latency_ms=obs.latency_ms
                    )
                )
            # Ket qua cong cu vao role 'tool', TUYET DOI khong vao 'system': van ban
            # nay do nguoi la soan, khong duoc mang tham quyen cua he thong.
            messages.append(ToolMessage(tool_call_id=obs.tool_call_id, content=obs.content))

    # Chan 1: het so vong.
    logger.warning("het so vong ReAct", tool_calls_used=tool_calls_used)
    return _finish(last_text, logger, reason="max_iterations", iteration=deps.max_iterations)
