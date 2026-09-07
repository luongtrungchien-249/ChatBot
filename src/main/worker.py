"""ARQ worker cho HAI queue tach biet.

    WorkerSettings             queue `reply`        max_jobs=1  (FIFO theo thread)
    MaintenanceWorkerSettings  queue `maintenance`  max_jobs=2  (nen L2, trich fact)

Tach hai process chu khong gop: queue `reply` chay tuan tu de giu dung thu tu tra
loi, nen mot job nen ton vai giay se lam moi cau hoi phia sau phai xep hang cho no.

Chong trung va co "da tra loi" nam O DAY, khong o handle_message: chung la ha tang,
va pipeline phai test duoc ma khong can Redis.
"""

import uuid
from typing import Any

from adapters.web.send import publish_progress, web_channel
from adapters.zalo_bot.send import zalo_bot_channel
from agents.domain.errors import is_retryable
from agents.domain.message import scope_of
from agents.domain.thread import Platform, ThreadScope
from agents.pipeline.handle_message import Failed, Handled, handle_message
from agents.ports.channel import ChannelPort
from infra.cancel import clear_cancel, is_cancelled
from infra.dedupe import has_replied, mark_replied
from infra.logger import configure_logging, get_logger
from infra.queue import (
    QUEUE_MAINTENANCE,
    QUEUE_REPLY,
    REPLY_CONCURRENCY,
    enqueue_summarize,
    from_payload,
    redis_settings,
)
from memory.jobs.extract_facts import extract_facts
from memory.jobs.summarize import summarize_thread

from .container import build_deps

configure_logging()
_log = get_logger()

#: CLI khong di qua hang doi (xem cli.py) nen khong co mat o day.
_CHANNELS: dict[Platform, ChannelPort] = {
    "web": web_channel,
    "zalo_bot": zalo_bot_channel,
}


async def handle_reply(ctx: dict[str, Any], payload: dict[str, Any]) -> None:
    msg = from_payload(payload)
    log = _log.bind(trace_id=msg.trace_id)

    # Retry cua hang doi khong duoc phep gui tin nhan thu hai cho cung mot message_id.
    # Thieu co nay, mot su co 5xx bien thanh bot spam nhom.
    #
    # Co nay CHI duoc dat khi that su co van ban gui di — xem Failed.replied. Dat no
    # o moi that bai (ban cu lam vay) thi lan retry vao day roi thoat ngay, va
    # max_tries = 3 chua bao gio thu lai lan nao.
    if await has_replied(msg.platform, msg.message_id):
        log.warning("da tra loi tin nay roi, bo qua lan retry")
        return

    # ARQ dem tu 1. Lan cuoi thi khong con co hoi nao nua, nen pipeline phai tra loi
    # nguoi dung ngay ca khi loi thuoc loai binh thuong se retry.
    job_try = int(ctx.get("job_try", 1) or 1)
    is_final_attempt = job_try >= WorkerSettings.max_tries

    channel = _CHANNELS.get(msg.platform)
    if channel is None:
        # Khong nem loi: retry cung se that bai y het, chi ton them ba lan.
        log.error("chua co ChannelPort cho nen tang nay", platform=msg.platform)
        return

    scope = scope_of(msg)
    # Co huy phai xoa TRUOC khi chay: mot co sot lai tu cau truoc se huy oan cau nay.
    await clear_cancel(scope)

    deps = await build_deps(channel, msg.platform)
    # Chi kenh web hien duoc tien do. Zalo khong co cho de ve.
    on_event = (
        (lambda event: publish_progress(msg.thread_id, event))
        if msg.platform == "web"
        else None
    )

    result = await handle_message(
        msg,
        _with_runtime_hooks(deps, on_event, lambda: is_cancelled(scope), is_final_attempt),
    )
    await clear_cancel(scope)

    if isinstance(result, Handled):
        if result.replied:
            await mark_replied(msg.platform, msg.message_id)
        return

    assert isinstance(result, Failed)
    # Chi danh dau khi pipeline THAT SU da gui gi do. Chua gui thi de trong, de lan
    # retry con chay lai duoc.
    if result.replied:
        await mark_replied(msg.platform, msg.message_id)

    if is_retryable(result.error):
        raise RuntimeError(
            f"upstream loi, de hang doi retry (lan {job_try}/{WorkerSettings.max_tries}): "
            f"{result.error}"
        )

    log.warning("that bai nhung khong retry", error=str(result.error))


async def handle_summarize(_ctx: dict[str, Any], payload: dict[str, Any]) -> None:
    """Job bao tri L2 + L3 implicit. Chay tren queue `maintenance`.

    Hai viec, mot job, THEO THU TU: nen truoc roi moi trich fact tren dung lo vua
    nen. Trich fact la viec phu — no chay SAU khi L2 da commit, nen hong o buoc do
    khong dung toi du lieu da ghi.
    """
    trace_id = str(uuid.uuid4())
    scope = ThreadScope(platform=payload["platform"], thread_id=payload["thread_id"])

    batch = await summarize_thread(scope, trace_id)
    if batch:
        await extract_facts(scope, batch, trace_id)


def _with_runtime_hooks(
    deps: Any, on_event: Any, should_stop: Any, is_final_attempt: bool
) -> Any:
    """Gan cac hook chi biet duoc luc chay vao Deps (dataclass frozen)."""
    from dataclasses import replace

    async def schedule(scope: ThreadScope) -> None:
        await enqueue_summarize(scope.platform, scope.thread_id)

    return replace(
        deps,
        on_react_event=on_event,
        should_stop=should_stop,
        schedule_maintenance=schedule,
        is_final_attempt=is_final_attempt,
    )


class WorkerSettings:
    """ARQ doc class nay. Chay: uv run arq main.worker.WorkerSettings"""

    functions = [handle_reply]  # noqa: RUF012
    redis_settings = redis_settings()
    #: PHAI khop _queue_name luc enqueue. Thieu dong nay thi worker lang nghe queue
    #: mac dinh cua ARQ con job nam o queue 'reply' — khong ai nhan, khong ai bao loi.
    queue_name = QUEUE_REPLY
    #: FIFO theo thread: ARQ khong co 'group', nen tuan tu toan cuc.
    #: Xem giai thich day du o infra/queue.py.
    max_jobs = REPLY_CONCURRENCY
    #: Job cham nhat la cau co tool (~15s) cong deadline ReAct 60s.
    job_timeout = 120
    max_tries = 3


class MaintenanceWorkerSettings:
    """Chay: uv run arq main.worker.MaintenanceWorkerSettings

    Tach khoi WorkerSettings vi hai queue co rang buoc nguoc nhau: `reply` phai
    tuan tu (dung thu tu tra loi), con `maintenance` thi khong — cho no chay song
    song vai job de mot nhom dong khong don viec nen lai.
    """

    functions = [handle_summarize]  # noqa: RUF012
    redis_settings = redis_settings()
    queue_name = QUEUE_MAINTENANCE
    max_jobs = 2
    #: Nen mot doan hoi thoai = mot lan goi model re. Rong rai hon duong tra loi vi
    #: khong ai dang ngoi cho.
    job_timeout = 120
    max_tries = 2
