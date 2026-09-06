"""Che secret truoc khi ghi log. Chay tren MOI dong log (xem infra/logger.py).

Nguyen tac: tha che nham con hon de lot. Mot token Zalo lot vao log tap trung la
mot token phai thu hoi, khong phai mot dong log xau.

Thu tu quan trong: mau cu the truoc, mau chung sau. Email di truoc so dien thoai
vi '0912345678@vd.com' se bi mau so dien thoai an mat phan truoc @.
"""

import re
from typing import Any

_RULES: list[tuple[re.Pattern[str], str]] = [
    # Chuoi ket noi co mat khau: postgres://user:pass@host
    (
        re.compile(r"\b(postgres|postgresql|redis|rediss|amqp|mongodb)://[^:@\s/]+:[^@\s]+@", re.I),
        r"\1://***:***@",
    ),
    # API key ho 'sk-': OpenAI (sk-proj-, sk-svcacct-, sk-), Anthropic (sk-ant-).
    # Bat ca ho thay vi liet ke tung tien to — doi nha cung cap thi khong phai nho
    # quay lai sua cho nay.
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"), "sk-***"),
    # Tavily (cong cu tim web)
    (re.compile(r"\btvly-[A-Za-z0-9_-]{8,}"), "tvly-***"),
    # Meta / Facebook page access token
    (re.compile(r"\bEAA[A-Za-z0-9]{20,}"), "EAA***"),
    # Zalo Bot Platform token: numeric_id:secret
    (re.compile(r"(?<!\d)\d{6,}:[A-Za-z0-9_-]{16,}"), "***:***"),
    # Header uy quyen
    (re.compile(r"\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}", re.I), r"\1 ***"),
    # Email — giu lai ten mien de con debug duoc
    (re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})"), r"***@\1"),
    # So dien thoai Viet Nam: +84xxxxxxxxx hoac 0xxxxxxxxx
    (re.compile(r"(?<!\d)(?:\+84|0)\d{9}(?!\d)"), "***"),
]


def redact(text: str) -> str:
    for pattern, replacement in _RULES:
        text = pattern.sub(replacement, text)
    return text


def redact_deep(value: Any) -> Any:
    """Che secret trong ca dict/list long nhau — log thuong la object, khong chi chuoi.

    Giu nguyen hinh dang; chi thay the cac gia tri chuoi.
    """
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: redact_deep(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_deep(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_deep(v) for v in value)
    return value
