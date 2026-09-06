"""L8: moi tin nhan vao co dung MOT trace_id xuyen suot moi log.

Moi gia tri deu di qua redact_deep truoc khi ghi — che secret la MAC DINH, khong
phai viec cho nguoi goi nho lam. Mot token lot vao log tap trung la mot token phai
thu hoi.

structlog.BoundLogger khop cau truc voi LoggerPort nen agents/ cam thang vao,
khong can adapter.
"""

import logging
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog

from config import get_settings
from shared.redact import redact_deep

_LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "warn": logging.WARNING,
           "error": logging.ERROR}


def _redact_processor(
    _logger: Any, _name: str, event_dict: MutableMapping[str, Any]
) -> Mapping[str, Any]:
    """Che secret trong TOAN BO event, ke ca ten su kien."""
    return {k: redact_deep(v) for k, v in event_dict.items()}


def configure_logging() -> None:
    settings = get_settings()
    is_dev = settings.NODE_ENV == "development"

    # Console Windows mac dinh la cp1252 va se nem UnicodeEncodeError khi in tieng
    # Viet. Bot nay tra loi bang tieng Viet nen day khong phai truong hop hiem.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    renderer: structlog.typing.Processor = (
        structlog.dev.ConsoleRenderer(colors=True)
        if is_dev
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="%H:%M:%S" if is_dev else "iso"),
            _redact_processor,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(_LEVELS[settings.LOG_LEVEL]),
        cache_logger_on_first_use=True,
    )


def get_logger(**initial: Any) -> Any:
    """Logger goc. Dung .bind(trace_id=...) de tao logger cho mot tin nhan."""
    return structlog.get_logger(**initial)
