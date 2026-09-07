"""Process `zalo`: chi nhan tin tu Zalo va xep hang.

Tach khoi `api` va `worker` co chu dich. Long-poll la mot vong lap treo lien tuc;
nhet no vao process api nghia la mot loi trong vong poll keo do ca giao dien web
xuong theo. Ba process, ba trach nhiem, tat rieng duoc tung cai.

Chay: uv run python -m main.zalo
"""

import asyncio

from adapters.zalo_bot.polling import poll_forever
from config import get_settings
from infra.http import close_http
from infra.logger import configure_logging, get_logger
from infra.queue import close_queue
from infra.redis_client import close_redis

configure_logging()
_log = get_logger()


async def main() -> None:
    settings = get_settings()

    if not settings.ZALO_BOT_TOKEN:
        _log.error("ZALO_BOT_TOKEN rong — khong co gi de chay")
        return
    if settings.ZALO_MODE != "polling":
        # Khong tu y chay: doi lai ZALO_MODE=webhook la nguoi dung da dinh dung
        # route webhook. Chay poller song song se lam hai duong cung nhan mot tin.
        _log.error("ZALO_MODE khong phai 'polling' — dat lai roi chay lai", mode=settings.ZALO_MODE)
        return

    try:
        await poll_forever()
    finally:
        await close_queue()
        await close_redis()
        await close_http()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _log.info("dung theo yeu cau")
