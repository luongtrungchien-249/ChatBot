from datetime import datetime
from typing import Protocol


class ClockPort(Protocol):
    """Co port cho thoi gian de test xac dinh duoc.

    Khong goi datetime.now() truc tiep trong agents/.
    """

    def now(self) -> datetime: ...
