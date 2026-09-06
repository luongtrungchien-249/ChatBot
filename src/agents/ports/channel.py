from typing import Protocol

from ..domain.thread import ThreadScope


class ChannelPort(Protocol):
    #: Messenger 2000 — agents khong hardcode con so cua tung nen tang.
    max_message_chars: int

    async def typing(self, scope: ThreadScope) -> None: ...

    async def send(self, scope: ThreadScope, text: str, reply_to: str | None = None) -> None:
        """Tu chunk theo max_message_chars."""
        ...
