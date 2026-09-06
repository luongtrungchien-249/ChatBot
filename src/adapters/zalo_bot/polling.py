"""Vong long-poll: nhan tin tu Zalo roi day vao hang doi.

L5 — adapter chi lam bon viec: nhan, chuan hoa, chong trung, xep hang. Khong goi
LLM, khong doc memory. Worker moi chay pipeline.

Vi sao poll chu khong webhook: webhook can mot URL cong khai co HTTPS, va
ZALO_MODE dang la `polling`. Doi sang webhook khong phai viet lai adapter — chi
them mot route goi thang `normalize_update` roi `ingest()` o duoi.
"""

import asyncio
from typing import Any

import httpx

from infra.dedupe import claim
from infra.logger import get_logger
from infra.queue import enqueue_reply

from .api import POLL_TIMEOUT_S, ZaloApiError, get_me, get_updates
from .normalize import GROUP_CHAT_TYPE, normalize_update

_log = get_logger()

#: Backoff khi API loi lien tiep. Khong retry ngay: mot su co ben Zalo se bien
#: thanh vai nghin request mot phut tu phia ta.
_BACKOFF_S = (1, 2, 5, 10, 30)


async def ingest(result: dict[str, Any], bot_id: str) -> bool:
    """Mot update -> hang doi. True = da xep hang. Dung chung cho poll va webhook."""
    msg = normalize_update(result, bot_id)
    if msg is None:
        _log.debug("bo qua update khong phai tin text", event=result.get("event_name"))
        return False

    log = _log.bind(trace_id=msg.trace_id)

    # Da do bang tin nhom that (06/09/2026): payload nhom chi co
    # ['chat', 'date', 'from', 'message_id', 'text'] — KHONG co truong mention nao.
    # Zalo chen thang TEN HIEN THI cua bot vao text: "@Bot CP Assistant xin chao".
    # Nen _mentioned_bot() luon tra False o day va lop regex trong policy/mention.py
    # moi la lop lam viec that su. Giu log ten truong de biet ngay khi Zalo doi.
    if (result.get("message") or {}).get("chat", {}).get("chat_type") == GROUP_CHAT_TYPE:
        log.debug("tin nhom Zalo", truong=sorted((result.get("message") or {}).keys()))

    # Lop chong trung thu nhat. getUpdates khong co `offset` nen mot tin hoan toan
    # co the ve hai lan; thieu buoc nay la bot tra loi doi.
    if not await claim(msg.platform, msg.message_id):
        log.info("tin da duoc xu ly roi, bo qua")
        return False

    await enqueue_reply(msg)
    # thread_id o day KHONG phai de go loi: voi GROUP_POLICY=allowlist, day la cach
    # duy nhat nguoi van hanh biet phai go gi vao `cli allow <platform> <thread_id>`.
    # Bo dong nay di la bot im lang trong nhom moi va khong ai tra ra duoc id.
    log.info("da xep hang tin Zalo", is_group=msg.is_group, thread_id=msg.thread_id)
    return True


async def poll_forever() -> None:
    """Chay den khi bi huy. Chi thoat khi token sai — loi do retry khong chua duoc."""
    me = await get_me()
    bot_id = str(me.get("id") or "")
    _log.info(
        "Zalo poller khoi dong",
        bot=me.get("display_name"),
        can_join_groups=me.get("can_join_groups"),
    )

    failures = 0
    while True:
        try:
            result = await get_updates(POLL_TIMEOUT_S)
            failures = 0
            # None = het gio ma khong ai nhan tin. Trang thai binh thuong nhat cua
            # mot con bot; khong log gi ca, neu khong file log se day rac.
            if result is not None:
                await ingest(result, bot_id)
        except asyncio.CancelledError:
            _log.info("Zalo poller dung")
            raise
        except ZaloApiError as error:
            if error.status in (401, 403):
                _log.error("ZALO_BOT_TOKEN sai hoac bi thu hoi — dung poller", status=error.status)
                raise
            failures += 1
            await _backoff(failures, error)
        except (httpx.HTTPError, ValueError) as error:
            # ValueError: body khong phai JSON (Zalo tra trang loi HTML luc su co).
            failures += 1
            await _backoff(failures, error)


async def _backoff(failures: int, error: Exception) -> None:
    delay = _BACKOFF_S[min(failures, len(_BACKOFF_S)) - 1]
    _log.warning("poll Zalo loi, cho roi thu lai", lan=failures, giay=delay, loi=str(error))
    # KHONG nuot CancelledError o day: nuot la Ctrl+C phai bam nhieu lan moi tat.
    await asyncio.sleep(delay)
