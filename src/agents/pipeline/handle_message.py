"""Orchestrator. Doc file nay la hieu ca he thong.

15 stage, moi stage mot file thuan trong ./stages/ va test rieng duoc.
Xem ARCHITECTURE.md section 5.3.

Cac stage chua den luot duoc BO QUA TUONG MINH, khong xoa, de doc file nay van thay
du hinh dang cuoi cung cua duong ong.

Chong trung va co "da tra loi" (dedupe / mark_replied) nam o worker, khong o day:
chung la ha tang, va handle_message phai test duoc ma khong can Redis.
"""

from asyncio import gather
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from shared.result import Ok
from tho.y_dinh import YeuCauTho, nhan_dien

from ..domain.errors import BotError, is_config_error, is_retryable
from ..domain.message import InboundMessage, scope_of
from ..domain.thread import ThreadScope, user_subject
from ..policy.access import AccessRules
from ..policy.injection import detect_injection
from ..policy.mention import primary_name
from ..ports.channel import ChannelPort
from ..ports.llm import CallContext, Effort, LlmPort
from ..ports.logger import LoggerPort
from ..ports.memory import MemoryPort
from ..ports.ratelimit import RateLimitPort
from ..ports.tool import ToolPort
from ..prompt.context import ContextEnvelope, ContextInput
from .stages.access import check_access
from .stages.budget_guard import BUDGET_EXCEEDED_TEXT, check_budget
from .stages.build_prompt import build_prompt
from .stages.command import (
    Answer,
    AskConfirm,
    DeferredWrite,
    handle_command,
    run_deferred_write,
)
from .stages.generate import (
    CONFIG_ERROR_TEXT,
    FALLBACK_TEXT,
    GenerateDeps,
    ReactEvent,
    generate,
)
from .stages.mention import Ask, Ignore, ShowHelp, help_text, resolve_mention_stage
from .stages.persist import persist_inbound, persist_outbound
from .stages.ratelimit import RATE_LIMITED_TEXT, Pass, Warn, check_rate_limit
from .stages.respond import respond
from .stages.tho import lam_tho
from .stages.typing_ import start_typing


@dataclass(frozen=True, slots=True)
class Handled:
    replied: bool
    ok: Literal[True] = True


@dataclass(frozen=True, slots=True)
class Failed:
    error: BotError
    #: Da gui van ban nao cho nguoi dung chua.
    #:
    #: Cho goi (worker) can biet de dat co `replied:` — dat co khi CHUA gui gi se
    #: lam lan retry tu thoat ngay, va `max_tries` thanh vo nghia.
    replied: bool
    ok: Literal[False] = False


HandleResult: TypeAlias = Handled | Failed


@dataclass(frozen=True, slots=True)
class ReplyModel:
    max_tokens: int
    effort: Effort


@dataclass(frozen=True, slots=True)
class ReactLimits:
    """Chan cung cua vong ReAct. Xem stages/generate.py."""

    max_iterations: int
    deadline_ms: int


@dataclass(frozen=True, slots=True)
class Deps:
    llm: LlmPort
    memory: MemoryPort
    channel: ChannelPort
    rate_limit: RateLimitPort
    logger: LoggerPort
    tools: ToolPort
    access_rules: AccessRules
    bot_name: str
    #: Tu llm/models.py — agents/ khong duoc import llm/ nen container tiem vao.
    reply: ReplyModel
    react: ReactLimits
    #: So tin gan nhat lay lam L1. Section 6.1 chot 15.
    recent_limit: int = 15
    #: Bao tien do ReAct ra kenh (web SSE hien duoc bot dang lam gi).
    on_react_event: Callable[[ReactEvent], None] | None = None
    #: Nguoi dung bam dung. Kenh nao khong co nut dung thi bo trong.
    should_stop: Callable[[], Awaitable[bool]] | None = None
    #: Day co phai lan thu CUOI CUNG cua job khong.
    #:
    #: False = con retry phia sau, nen loi CO THE retry duoc thi KHONG gui cau
    #: fallback: gui roi ma lan sau thanh cong thi nguoi dung nhan hai tin cho mot
    #: cau hoi. Loi khong retry duoc thi van tra loi ngay, du con luot.
    #:
    #: Mac dinh True cho cac duong khong di qua hang doi (CLI): mot lan chay la het.
    is_final_attempt: bool = True
    #: Stage 15 — xep hang viec nen L2. agents/ khong duoc import infra/ (L1) nen
    #: entrypoint tiem ham nay vao. Bo trong thi khong co viec nen nao chay.
    schedule_maintenance: Callable[[ThreadScope], Awaitable[None]] | None = None
    _unused: tuple[()] = field(default=(), repr=False)


def _co_tai_lieu(prompt: ContextEnvelope) -> bool:
    """Prompt lan nay co khoi <tai_lieu> khong.

    Doc tren CHUOI da build chu khong tren dau vao: tang budget co the da cat het khoi
    do, va luc do doi bot trich dan mot thu no khong duoc doc la bat vo ly.
    """
    return any("<tai_lieu" in m.content for m in prompt.messages)


async def handle_message(msg: InboundMessage, deps: Deps) -> HandleResult:
    log = deps.logger.bind(trace_id=msg.trace_id, platform=msg.platform)
    scope = scope_of(msg)
    ctx = CallContext(scope=scope, sender_id=msg.sender_id, trace_id=msg.trace_id)

    #  1. access — khong duoc phep thi dung, IM LANG.
    if not check_access(msg, deps.access_rules):
        log.info("thread khong trong allowlist, bo qua", thread_id=msg.thread_id)
        return Handled(replied=False)

    #  2. mention
    mention = resolve_mention_stage(msg, deps.bot_name)
    if isinstance(mention, Ignore):
        return Handled(replied=False)
    if isinstance(mention, ShowHelp):
        await respond(deps.channel, scope, help_text(deps.bot_name), msg.message_id, logger=log)
        return Handled(replied=True)
    assert isinstance(mention, Ask)

    #  2b. INPUT RAILS — do injection/jailbreak tren tin nhan nguoi dung.
    #
    #      GHI NHAN, KHONG CHAN. Chan theo tu khoa vua de vuot vua tao an toan gia;
    #      lop chan that su la RULES trong system prompt cong viec khong bao gio dua
    #      van ban la vao role 'system'. O day de DO: truoc buoc nay, khong co dong
    #      log nao cho biet co ai dang do bot hay khong.
    quet = detect_injection(mention.text)
    if quet.suspicious:
        log.warning(
            "tin nhan co mau giong tan cong prompt — ghi nhan de audit, KHONG chan",
            loai=list(quet.loai),
            mau=list(quet.patterns),
            sender_id=msg.sender_id,
        )

    #  3. command — memory / quen / help. Tra loi luon, KHONG goi model.
    #     Dung TRUOC ratelimit co chu dich: nguoi dung phai xoa duoc memory cua
    #     chinh minh ngay ca khi dang bi rate limit.
    #     Rieng lenh GHI (`nho giup:`) bi giu lai toi sau stage 5 — xem DeferredWrite.
    outcome = await handle_command(mention.text, deps.memory, scope, msg.sender_id)
    if isinstance(outcome, Answer):
        await respond(
            deps.channel, scope, outcome.text, msg.message_id,
            logger=log, van_ban_nguoi_dung=mention.text,
        )
        return Handled(replied=True)
    if isinstance(outcome, AskConfirm):
        # Ghi yeu cau dang cho TRUOC khi hoi: hoi xong moi ghi thi nguoi dung tra
        # loi that nhanh se gap mot cau "khong co yeu cau nao dang cho".
        await deps.memory.stage_forget(scope, msg.sender_id, [f.id for f in outcome.facts])
        await respond(
            deps.channel, scope, outcome.text, msg.message_id,
            logger=log, van_ban_nguoi_dung=mention.text,
        )
        return Handled(replied=True)

    #  4. ratelimit — user va thread, token bucket.
    limit = await check_rate_limit(deps.rate_limit, scope, msg.sender_id)
    if not isinstance(limit, Pass):
        log.warning(
            "bi rate limit",
            tier=limit.tier,
            retry_after_ms=limit.retry_after_ms,
            sender_id=msg.sender_id,
            nhac=isinstance(limit, Warn),
        )
        if isinstance(limit, Warn):
            await respond(deps.channel, scope, RATE_LIMITED_TEXT, msg.message_id, logger=log)
            return Handled(replied=True)
        # Da nhac thread nay trong 5 phut qua roi. Im lang o day KHONG mau thuan voi
        # "im lang trong nhom trong nhu bot chet": nguoi dung vua duoc noi la hay
        # cham lai, nhac lai lan nua chi la bot tu spam.
        return Handled(replied=False)

    #  5. budget-guard — CHOT CHAN CUNG, khong phai alert.
    if not await check_budget(deps.rate_limit):
        await respond(deps.channel, scope, BUDGET_EXCEEDED_TEXT, msg.message_id, logger=log)
        return Handled(replied=True)

    #  5b. lenh GHI da qua duoc ratelimit va ngan sach — gio moi thuc hien.
    if isinstance(outcome, DeferredWrite):
        text = await run_deferred_write(outcome, deps.memory, scope, msg.sender_id)
        await respond(
            deps.channel, scope, text, msg.message_id,
            logger=log, van_ban_nguoi_dung=mention.text,
        )
        return Handled(replied=True)

    #  6. persist — ghi TRUOC khi goi model, de cau hoi khong bien mat khi API hong.
    await persist_inbound(deps.memory, msg)

    #  7. typing — khong await.
    start_typing(deps.channel, scope, log)

    #  8. rewrite  BO, co chu dich (07/09/2026). Ke hoach thiet ke stage nay khi
    #              retrieval con la PRE-FETCH: cau "cai do bao nhieu?" phai duoc viet
    #              lai thanh cau doc lap truoc khi search. Gio retrieval la mot CONG
    #              CU trong vong ReAct, va model nhin thay lich su duoi dang luot
    #              that (xem prompt/context.py), nen chinh no da tu viet truy van co
    #              ngu canh — do duoc trong log: tu "AI" no sinh ra truy van
    #              "artificial intelligence latest 2026 2025 2024". Them mot lan goi
    #              model re de lam lai viec do la cong them do tre va tien cho thu
    #              vong lap dang lam roi. Lam lai neu do duoc truy van cong cu kem.
    #  9. retrieve Da thanh cong cu trong vong ReAct o stage 12, khong con pre-fetch.

    #  9b. lam tho — DUONG RIENG, khong qua vong ReAct.
    #
    #      Dat o day co chu dich: SAU chan ngan sach (lam tho van ton tien) va SAU
    #      persist (cau hoi khong duoc bien mat), nhung TRUOC recall va ReAct.
    #
    #      Mot yeu cau lam tho khong co tai lieu nao de tra. De no di qua vong ReAct
    #      thi no kich hoat chan 7 ("chua tra ma da dinh tra loi") va ton mot luot goi
    #      model thua cho MOI bai tho — dung luc tinh nang nay dat muc tieu giam do
    #      tre. Xem docs/plan-lam-tho-va-tu-host.md muc 1.
    y_dinh = nhan_dien(mention.text)
    if isinstance(y_dinh, YeuCauTho):
        log.info("yeu cau lam tho", the_tho=y_dinh.the_tho)
        bai = await lam_tho(
            y_dinh, deps.llm, max_tokens=deps.reply.max_tokens, ctx=ctx, logger=log
        )
        await respond(
            deps.channel, scope, bai, msg.message_id,
            logger=log, van_ban_nguoi_dung=mention.text,
        )
        return Handled(replied=True)

    # 10. recall — L1 + L2 + L3. Ba lan doc doc lap nen chay SONG SONG: tuan tu thi
    #     cong thang do tre cua ca ba vao duong phan hoi ma khong duoc gi.
    #     MOI truy van deu kem `scope` — hang rao chong ro ri cross-group.
    recent, summary, facts = await gather(
        deps.memory.recent(scope, deps.recent_limit),
        deps.memory.summary(scope),
        deps.memory.facts(scope, user_subject(msg.sender_id), mention.text),
    )

    # 11. build-prompt
    prompt = build_prompt(
        ContextInput(
            question=mention.text,
            is_group=msg.is_group,
            recent=tuple(recent),
            summary=summary,
            facts=tuple(facts),
        ),
        log,
    )

    # 12. generate — vong ReAct: Thought -> Action -> Observation -> lap.
    result = await generate(
        GenerateDeps(
            llm=deps.llm,
            tools=deps.tools,
            rate_limit=deps.rate_limit,
            max_tokens=deps.reply.max_tokens,
            effort=deps.reply.effort,
            max_iterations=deps.react.max_iterations,
            deadline_ms=deps.react.deadline_ms,
            should_stop=deps.should_stop,
            on_event=deps.on_react_event,
        ),
        prompt,
        ctx,
        log,
    )

    if not isinstance(result, Ok):
        # Im lang trong nhom trong nhu bot chet va nguoi dung se spam mention.
        # Nhung cung khong duoc bao "thu lai sau" cho mot loi cau hinh: thu lai se
        # hong y het, va nguoi dung se tuong bot khong hieu minh noi gi.
        #
        # Con luot retry VA loi thuoc loai retry duoc -> im lang o luot nay. Gui cau
        # fallback ngay bay gio nghia la neu lan sau thanh cong thi nguoi dung nhan
        # HAI tin cho mot cau hoi; ma neu de tranh dieu do bang cach danh dau "da
        # tra loi" thi lan retry lai tu thoat va khong bao gio thu lai that.
        will_retry = is_retryable(result.error) and not deps.is_final_attempt
        if not will_retry:
            text = CONFIG_ERROR_TEXT if is_config_error(result.error) else FALLBACK_TEXT
            await respond(deps.channel, scope, text, msg.message_id, logger=log)
        else:
            log.info("con luot retry, chua gui cau fallback", error=str(result.error))
        # Van bao loi ra ngoai de worker quyet dinh retry (chi UpstreamError moi
        # retry, xem is_retryable).
        return Failed(error=result.error, replied=not will_retry)

    # 13. respond — CHOT CHAN CUOI CUNG. Xem agents/policy/output_guard.py.
    await respond(
        deps.channel,
        scope,
        result.value,
        msg.message_id,
        logger=log,
        # Thong tin ca nhan nguoi dung VUA go ra thi bot duoc phep nhac lai; thu bot
        # lay tu tai lieu, tu web hay tu bo nho cua nguoi khac thi khong.
        van_ban_nguoi_dung=mention.text,
        # Co khoi <tai_lieu> trong prompt thi cau tra loi phai neu nguon.
        co_tai_lieu=_co_tai_lieu(prompt),
    )
    await persist_outbound(
        deps.memory,
        scope,
        msg.message_id,
        primary_name(deps.bot_name),
        result.value,
        msg.is_group,
    )

    # 14. account  Da ghi trong llm/cost_meter.py ngay tai lan goi.

    # 15. schedule — day job nen L2 vao hang doi `maintenance`. KHONG chay tai day:
    #     nen ton mot lan goi model, va nguoi dung da nhan cau tra loi o stage 13 roi.
    #     Hong o day khong duoc lam hong ca luot: cau tra loi da gui di.
    if deps.schedule_maintenance is not None:
        try:
            await deps.schedule_maintenance(scope)
        except Exception as error:
            log.warning("khong xep hang duoc job nen L2", err=str(error))

    return Handled(replied=True)
