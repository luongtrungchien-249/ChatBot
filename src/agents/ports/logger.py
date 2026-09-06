"""L8: moi tin nhan vao co dung MOT trace_id xuyen suot moi log.

agents/ khong duoc import infra/ nen phai co port rieng. Protocol nay khop cau truc
voi structlog.BoundLogger, nen infra/logger.py cam thang vao, khong can adapter.

Logger truyen vao stage LUON la logger da gan trace_id — stage khong tu gan lay,
va cung khong the quen.
"""

from typing import Any, Protocol


class LoggerPort(Protocol):
    def debug(self, event: str, **kw: Any) -> Any: ...

    def info(self, event: str, **kw: Any) -> Any: ...

    def warning(self, event: str, **kw: Any) -> Any: ...

    def error(self, event: str, **kw: Any) -> Any: ...

    def bind(self, **kw: Any) -> "LoggerPort":
        """Gan them truong co dinh (trace_id). structlog.bind() khop san chu ky nay."""
        ...
