"""Stage 4: rate limit ba tang.

Dat SAU stage 3 (command) co chu dich: nguoi dung phai xoa duoc memory cua chinh
minh ngay ca khi dang bi rate limit. Dung "toi uu" thu tu nay.

Dat TRUOC stage 5 (budget-guard) va stage 6 (persist): mot tin bi chan khong duoc
ghi vao lich su, neu khong mot dot spam se lam nhieu ca hoi thoai ma bot khong he
tra loi cau nao.

Cau nhac gui TOI DA MOT LAN / 5 PHUT / THREAD. Thieu tran do thi mot nguoi spam 100
tin nhan duoc 100 cau nhac — bot tu bien thanh ke spam nhom.
"""

from dataclasses import dataclass
from typing import TypeAlias

from ...domain.thread import ThreadScope
from ...ports.ratelimit import Denied, RateLimitPort

#: Ngan, khong trach moc, khong noi con so cu the. Con so la chuyen van hanh; noi ra
#: chi giup nguoi muon lach biet can cho bao lau.
RATE_LIMITED_TEXT = "Bạn nhắn hơi nhanh, mình chưa theo kịp. Chờ một chút rồi hỏi lại nhé."


@dataclass(frozen=True, slots=True)
class Pass:
    pass


@dataclass(frozen=True, slots=True)
class Warn:
    """Bi chan VA duoc phep noi mot cau."""

    tier: str
    retry_after_ms: int


@dataclass(frozen=True, slots=True)
class Silent:
    """Bi chan nhung da nhac thread nay roi — im lang."""

    tier: str
    retry_after_ms: int


RateLimitOutcome: TypeAlias = Pass | Warn | Silent


async def check_rate_limit(
    rate_limit: RateLimitPort, scope: ThreadScope, sender_id: str
) -> RateLimitOutcome:
    verdict = await rate_limit.check(scope, sender_id)
    if not isinstance(verdict, Denied):
        return Pass()

    if await rate_limit.should_warn(scope):
        return Warn(tier=verdict.tier, retry_after_ms=verdict.retry_after_ms)
    return Silent(tier=verdict.tier, retry_after_ms=verdict.retry_after_ms)
