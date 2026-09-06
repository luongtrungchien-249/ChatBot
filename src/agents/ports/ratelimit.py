from dataclasses import dataclass
from typing import Literal, Protocol, TypeAlias

from ..domain.thread import ThreadScope


@dataclass(frozen=True, slots=True)
class Allowed:
    allowed: Literal[True] = True


@dataclass(frozen=True, slots=True)
class Denied:
    retry_after_ms: int
    tier: Literal["user", "thread", "global"]
    allowed: Literal[False] = False


LimitVerdict: TypeAlias = Allowed | Denied


class RateLimitPort(Protocol):
    async def check(self, scope: ThreadScope, sender_id: str) -> LimitVerdict:
        """Tru mot luot cua CA HAI tang (user va thread) neu ca hai con du.

        Chi tru khi ca hai cung cho phep: het luot o tang thread ma van tru cua
        nguoi dung nghia la ho mat luot cho mot cau bot khong tra loi.
        """
        ...

    async def should_warn(self, scope: ThreadScope) -> bool:
        """True = duoc phep gui cau nhac "cham lai" cho thread nay lan nay.

        Toi da MOT lan / 5 phut / thread (ARCHITECTURE.md section 9). Thieu cua nay
        thi mot nguoi spam 100 tin se nhan 100 cau nhac — bot tu bien thanh ke spam
        nhom, dung cai lam nguoi ta kick no ra.
        """
        ...

    async def within_daily_budget(self) -> bool:
        """CHOT CHAN CUNG theo ngan sach ngay, khong phai alert.

        Day chinh la tang thu ba ("global") cua rate limit. No khong nam trong
        check() vi duoc kiem o mot cho khac va lai nhieu lan: stage 5, roi truoc
        MOI vong ReAct — mot cau hoi co the ton nhieu lan goi model.
        """
        ...
