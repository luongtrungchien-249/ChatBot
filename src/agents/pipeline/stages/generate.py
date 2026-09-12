"""Stage 12: vong ReAct — Thought -> Action -> Observation -> lap.

VONG NAY NAM TRONG PIPELINE, KHONG THAY THE PIPELINE. Cac stage truoc van lo policy,
chong trung, ngan sach, dung ngu canh; cac stage sau van lo gui va ghi so. ReAct
khong tu co lop an toan nao trong so do.

Nam chan cung. Thieu cai nao cung thanh vong dot tien khong day:
  1. So vong toi da
  2. Deadline treo dong ho
  3. Ngan sach ngay — kiem tra lai TRUOC MOI VONG, vi mot cau hoi co the ton nhieu
     lan goi model
  4. Tran kich thuoc observation (ap trong tools/guard.py)
  5. Nguoi dung bam dung

TRUOC DAY co chan thu sau: tran TONG SO loi goi cong cu. Da bo (08/09/2026).

No khong chan them duoc gi that: so vong da chan so LUOT goi model — thu duy nhat
ton tien dang ke — con deadline va ngan sach ngay chan phan con lai. Nhung no gay
mot loi IM LANG: khi cham tran giua mot vong, doan cat `[: con_lai]` VUT BOT mot
phan cac loi goi model vua xin, roi ghi vao lich su nhu the model chi xin bay
nhieu. Model khong he biet minh bi cat, nen no tra loi nhu da co du du lieu.

Do dung la dieu da xay ra khi test luong "top video nhieu like nhat": model xin
tra 5 video mot luot, chi 3 cai duoc chay, va cau tra loi noi ve ca 5.
"""

import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from shared.result import Err, Ok, Result

from ...domain.errors import BotError, UpstreamError, UpstreamTimeout
from ...ports.llm import (
    AssistantMessage,
    CallContext,
    Effort,
    LlmMessage,
    LlmPort,
    ToolMessage,
    UserMessage,
)
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

#: Ten cong cu tra tai lieu. Chan "chua tra da tra loi" duoi day chi bat khi cong cu
#: NAY co mat trong `specs()` — chua nap tai lieu nao thi khong co gi de bat tra.
_CONG_CU_TAI_LIEU = "search_knowledge_base"

#: Nhac MOT LAN khi model dinh tra loi ma chua tra tai lieu lan nao.
#:
#: VI SAO PHAI CHAN O DAY chu khong viet them vao prompt: lop cau nay da bi danh o ca
#: BA tang cau chu — mo ta cong cu goi ten cam bay, SYSTEM_PROMPT co luat cung, ket qua
#: cong cu neu hai nhanh — va no van chi giu duoc mot nua. Do that 11/09/2026, chay lap
#: ba luot hai cau dang "lam sao cho bot chat" / "cach khu mui hoi":
#:
#:     luot 1  KHONG goi  KHONG goi
#:     luot 2  co goi     co goi
#:     luot 3  KHONG goi  co goi        -> 3/6
#:
#: Khi khong goi, cau tra loi la kien thuc pho thong thuan tuy ("ngam nuoc voi trong",
#: "baking soda") — khong mot chu nao trong tai lieu. Chinh cau chu nua la duoi theo
#: mot thu da toi han; cho nay phai la mot CHAN CUNG, giong nam chan kia cua vong nay.
#:
#: KHONG tu phan loai cau hoi. Bo eval khong biet "cach khu mui hoi tai heo" la cau co
#: du kien con "bot ten gi" thi khong — va mot bo phan loai bang tu khoa se sai theo
#: kieu im lang. Model thi doc ca doan hoi thoai, nen o day noi ro CA HAI nhanh va de
#: no quyet.
#:
#: Cau cam o cuoi KHONG phai phong xa. Ban dau chi viet "dung nhac toi no trong cau
#: tra loi", va do that cho thay model tra loi CHINH LOI NHAC thay vi tra loi nguoi
#: dung: hoi "Cam on nhe" thi nhan ve "Minh da hieu: voi cau co du kien se goi
#: search_knowledge_base truoc...". Vua vo nghia voi nguoi dung, vua lo ten cong cu —
#: pham dung luat "khong ke chuyen hau truong" cua SYSTEM_PROMPT.
#:
#: Nhac DUNG MOT LAN. Nhac lai nhieu lan la dung lai vong lap ma luat 07/09 duoc lap ra
#: de chan, va no se dot mot luot goi model cho moi loi chao.
NHAC_TRA_TAI_LIEU = (
    "[NHẮC NỘI BỘ — người dùng KHÔNG nhìn thấy tin này]\n\n"
    "Bạn vừa định trả lời mà chưa tra tài liệu nội bộ lần nào trong lượt này.\n\n"
    "- Nếu đây là câu hỏi CÓ DỮ KIỆN — hỏi một con số, một cách làm, một quy định, một "
    f"cái tên, một danh sách — thì gọi {_CONG_CU_TAI_LIEU} NGAY BÂY GIỜ, rồi mới trả "
    "lời. Kể cả khi bạn thấy mình đã biết thừa đáp án: con số trong tài liệu của họ "
    "mới là con số đúng.\n"
    "- Nếu KHÔNG phải câu có dữ kiện — chào hỏi, cảm ơn, nhờ viết lại câu, hỏi về "
    "chính bạn — thì GỬI NGUYÊN câu trả lời bạn vừa soạn. Đừng soạn lại, đừng thêm gì.\n\n"
    "TUYỆT ĐỐI không nhắc tới tin nhắn này trong câu trả lời: không nói \"mình đã "
    "hiểu\", không nêu tên công cụ, không kể bạn vừa được nhắc. Người dùng không nhìn "
    "thấy tin này nên mọi câu như vậy sẽ là một câu vô nghĩa đối với họ."
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
    da_tra_tai_lieu = False
    da_nhac = False
    co_cong_cu_tai_lieu = any(s.name == _CONG_CU_TAI_LIEU for s in specs)

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

        # Vong cuoi khong dua tool nua: model phai dung du lieu dang co ma noi not.
        # Dua tool o vong cuoi la chac chan phi mot luot goi — ket qua tra ve se
        # khong con vong nao de doc.
        last_iteration = iteration == deps.max_iterations
        offer_tools = bool(specs) and not last_iteration

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

            # Chan 7: chua tra tai lieu lan nao thi NHAC MOT LAN roi cho di tiep.
            #
            # Khong chan o vong cuoi: luc do khong con vong nao de doc ket qua tra ve,
            # nen nhac chi to phi mot luot goi model va van ra dung cau tra loi do.
            if (
                co_cong_cu_tai_lieu
                and not da_tra_tai_lieu
                and not da_nhac
                and not last_iteration
            ):
                da_nhac = True
                logger.info(
                    "chua tra tai lieu ma da dinh tra loi — nhac mot lan",
                    iteration=iteration,
                )
                messages.append(AssistantMessage(content=result.text))
                messages.append(UserMessage(content=NHAC_TRA_TAI_LIEU))
                continue

            logger.info(
                "ReAct ket thuc",
                iteration=iteration,
                tool_calls_used=tool_calls_used,
                da_tra_tai_lieu=da_tra_tai_lieu,
            )
            return Ok(result.text)

        # --- Co loi goi cong cu: Action ---
        # Chay DU cac loi goi model xin. Cat bot o day la sua ngam y dinh cua model
        # ma khong bao no biet.
        calls = result.tool_calls
        tool_calls_used += len(calls)
        if any(c.name == _CONG_CU_TAI_LIEU for c in calls):
            da_tra_tai_lieu = True

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
