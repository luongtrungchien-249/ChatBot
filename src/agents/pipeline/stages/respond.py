"""Stage 13: gui cau tra loi.

KHONG chunk o day. Hop dong cua ChannelPort.send() la "tu chunk theo
max_message_chars" — moi nen tang mot gioi han (Zalo 2000 ky tu), va agents/
khong duoc hardcode con so cua tung nen tang.
"""

from ...domain.thread import ThreadScope
from ...ports.channel import ChannelPort


async def respond(
    channel: ChannelPort, scope: ThreadScope, text: str, reply_to: str | None = None
) -> None:
    await channel.send(scope, text, reply_to)
