"""Stage 7: bao "dang go" — KHONG await.

Cho typing xong la them mot vong mang vao duong phan hoi de doi lay mot hieu ung
hinh anh. Nhung van phai bat loi: mot task bi tu choi ma khong ai xu ly se in
"Task exception was never retrieved" va che mat loi that.
"""

import asyncio

from ...domain.thread import ThreadScope
from ...ports.channel import ChannelPort
from ...ports.logger import LoggerPort


def start_typing(
    channel: ChannelPort, scope: ThreadScope, logger: LoggerPort
) -> asyncio.Task[None]:
    async def run() -> None:
        try:
            await channel.typing(scope)
        except Exception as error:
            logger.warning("typing that bai", err=str(error))

    # Giu tham chieu tra ve de cho goi co the huy khi tat process; khong await.
    return asyncio.create_task(run())
