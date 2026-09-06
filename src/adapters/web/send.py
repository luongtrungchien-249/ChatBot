"""ChannelPort cua web: PUBLISH len Redis, process `api` doc lai roi day xuong SSE.

Worker va api la hai process khac nhau — day la duong duy nhat noi chung. Cung la ly
do web van di qua hang doi nhu moi adapter khac (L5) thay vi goi thang.
"""

import contextlib
import json
from dataclasses import asdict
from typing import Any

from agents.domain.thread import ThreadScope
from infra.logger import get_logger
from infra.redis_client import aw, get_redis

from .normalize import WEB_MAX_MESSAGE_CHARS, FinalEvent, TypingEvent, WebEvent, web_channel_key

_log = get_logger()


async def _publish(thread_id: str, event: WebEvent | Any) -> None:
    payload = json.dumps(asdict(event), ensure_ascii=False)
    await aw(get_redis().publish(web_channel_key(thread_id), payload))


def publish_progress(thread_id: str, event: Any) -> None:
    """Day su kien tien do (ReAct) xuong UI.

    KHONG await o cho goi: bao tien do khong duoc chan duong tra loi. Loi o day chi
    lam mat mot dong hien thi, khong duoc lam hong ca luot.
    """
    import asyncio

    async def run() -> None:
        with contextlib.suppress(Exception):
            await _publish(thread_id, event)

    task = asyncio.create_task(run())
    # Giu tham chieu de task khong bi thu gom giua chung.
    _BACKGROUND.add(task)
    task.add_done_callback(_BACKGROUND.discard)


_BACKGROUND: set[Any] = set()


class WebChannel:
    """Implement ChannelPort."""

    # Web khong co gioi han that su nhu Messenger; de rong de khong cat cau tra loi.
    max_message_chars = WEB_MAX_MESSAGE_CHARS

    async def typing(self, scope: ThreadScope) -> None:
        await _publish(scope.thread_id, TypingEvent())

    async def send(self, scope: ThreadScope, text: str, reply_to: str | None = None) -> None:
        await _publish(scope.thread_id, FinalEvent(text=text))


web_channel = WebChannel()
