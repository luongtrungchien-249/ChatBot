"""Taxonomy loi. Xem bang hanh vi trong ARCHITECTURE.md section 9."""

from dataclasses import dataclass
from typing import Literal, TypeAlias

UpstreamService = Literal["llm", "embed", "rerank", "db"]


@dataclass(frozen=True, slots=True)
class RateLimited:
    retry_after_ms: int


@dataclass(frozen=True, slots=True)
class BudgetExceeded:
    pass


@dataclass(frozen=True, slots=True)
class NotAllowed:
    pass


@dataclass(frozen=True, slots=True)
class UpstreamTimeout:
    service: UpstreamService


@dataclass(frozen=True, slots=True)
class UpstreamError:
    service: str
    status: int | None = None


@dataclass(frozen=True, slots=True)
class BadPayload:
    detail: str


BotError: TypeAlias = (
    RateLimited | BudgetExceeded | NotAllowed | UpstreamTimeout | UpstreamError | BadPayload
)


def is_config_error(error: BotError) -> bool:
    """Loi cau hinh: khoa sai, het han, khong du quyen.

    Khac han loi tam thoi o cho: THU LAI KHONG BAO GIO HET. Phai co nguoi sua bien
    moi truong. Gop chung voi 5xx la vua ton ba lan retry vo ich, vua noi doi nguoi
    dung rang "thu lai sau di".
    """
    return isinstance(error, UpstreamError) and error.status in (401, 403)


def is_retryable(error: BotError) -> bool:
    """Loi nao dang duoc retry job.

    - UpstreamTimeout: KHONG. Nguoi dung da nhan cau fallback roi.
    - 401/403: KHONG. Retry mot cau hinh sai ba lan van sai ba lan.
    - 4xx khac (400 payload hong): KHONG. Gui lai y het thi hong y het.
    - 429 va 5xx: CO. Day moi that su la tam thoi.
    - Khong ro status: CO, cho huong loi cua su nghi ngo (loi mang thuong khong co status).
    """
    if not isinstance(error, UpstreamError):
        return False
    if error.status is None:
        return True
    return error.status == 429 or error.status >= 500


def is_silent(error: BotError) -> bool:
    """Loi nao im lang hoan toan trong nhom."""
    return isinstance(error, NotAllowed | BadPayload)
