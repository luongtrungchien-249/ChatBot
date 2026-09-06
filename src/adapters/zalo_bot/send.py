"""ChannelPort cua Zalo Bot."""

from agents.domain.thread import ThreadScope
from shared.chunk_text import chunk_text

from .api import MAX_MESSAGE_CHARS, send_message


class ZaloBotChannel:
    """Implement ChannelPort."""

    max_message_chars = MAX_MESSAGE_CHARS

    async def typing(self, scope: ThreadScope) -> None:
        """Zalo Bot API khong co endpoint bao "dang go".

        Khong nem loi va cung khong log: day khong phai su co, day la nen tang
        khong ho tro. Hop dong cua ChannelPort da noi typing la best-effort.
        """
        return None

    async def send(self, scope: ThreadScope, text: str, reply_to: str | None = None) -> None:
        # Zalo cat cung o 2000 ky tu. Gui nguyen cau dai hon la mat phan duoi ma
        # API van bao thanh cong — nen phai chunk o day, khong phai o agents/.
        for part in chunk_text(text, MAX_MESSAGE_CHARS):
            await send_message(scope.thread_id, part)


zalo_bot_channel = ZaloBotChannel()
