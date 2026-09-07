"""Process `api`: nhan request tu giao dien, tra 200 duoi 2s roi thoi.

TUYET DOI khong cho LLM o day — pipeline chay ben worker.

Giao dien do chinh process nay render (Jinja2) va phuc vu tep tinh. Khong con buoc
build, khong con Node: sua giao dien la tai lai trang.

TODO(webhook-zalo): route webhook. Dang dung polling — xem adapters/zalo_bot/polling.py.
"""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from adapters.web.routes import WEB_ROOT, require_localhost, router
from config import get_settings
from infra.db import close_db
from infra.http import close_http
from infra.logger import configure_logging, get_logger
from infra.queue import close_queue
from infra.redis_client import close_redis

configure_logging()
_log = get_logger()

templates = Jinja2Templates(directory=str(WEB_ROOT / "templates"))


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield
    await close_queue()
    await close_db()
    await close_redis()
    await close_http()


app = FastAPI(title="CP Assistant", lifespan=lifespan)
app.include_router(router)
app.mount("/static", StaticFiles(directory=WEB_ROOT / "static"), name="static")


@app.middleware("http")
async def log_requests(request: Request, call_next: object) -> Response:
    """Tu log thay vi dung middleware co san: giu duoc lop redact va kiem soat dinh dang."""
    started = time.monotonic()
    response: Response = await call_next(request)  # type: ignore[operator]
    _log.info(
        "http",
        method=request.method,
        url=request.url.path,
        status=response.status_code,
        ms=int((time.monotonic() - started) * 1000),
    )
    return response


@app.get("/")
async def index(request: Request) -> Response:
    """Trang chat. Cung chinh sach truy cap nhu cac route /api (D17: chi localhost)."""
    require_localhost(request)
    # Ten bot lay tu config chu khong hardcode trong template: no da doi mot lan,
    # va lan sau doi thi tieu de trang khong duoc phep noi mot cai ten khac.
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"bot_name": get_settings().BOT_MENTION_NAME.split(",")[0].replace("_", " ")},
    )


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "main.api:app",
        host=settings.WEB_BIND,
        port=settings.WEB_PORT,
        log_config=None,  # structlog da lo phan log
    )


if __name__ == "__main__":
    run()
