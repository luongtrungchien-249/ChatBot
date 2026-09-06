"""Client HTTP cua Zalo Bot API.

Ba dieu da KIEM CHUNG bang lenh goi that toi API (khong suy doan tu tai lieu):

1. Base URL `https://bot-api.zaloplatforms.com/bot<TOKEN>/`. Hai host khac cung
   phan hoi (`bot-api.zapps.me`, `openapi.zalo.me/bot`) nhung tai lieu chinh thuc
   chi cong bo host tren — dung host tai lieu de khong dinh vao mot alias co the
   bien mat.

2. **`getUpdates` rong tra ve `{"ok": false, "error_code": 408}`**, sau khi treo
   dung `timeout` giay. Day la trang thai BINH THUONG — nhom im lang thi moi lan
   poll deu the. Coi 408 la loi thi log day man hinh canh bao gia va vong poll se
   backoff nham cho toi luc bot tre hang phut.

3. `sendMessage` gioi han 2000 ky tu.

`getUpdates` KHONG co tham so `offset` (khac Telegram): server tu giu vi tri doc.
Nen chong trung khong dua vao offset ma dua vao `message_id` qua `infra/dedupe`.
"""

import asyncio
from typing import Any

import httpx

from config import get_settings
from infra.logger import get_logger


class ZaloApiError(Exception):
    """Loi tu Zalo Bot API, mang theo `status` de phan loai retry.

    `agents/domain/errors.UpstreamError` la GIA TRI (dataclass) chu khong phai
    ngoai le — no khong nem duoc. Quy uoc trong du an: tang ngoai bien nem ngoai
    le co thuoc tinh `.status`, cho goi moi doi sang kieu gia tri.
    """

    def __init__(self, status: int | None, detail: str = "") -> None:
        super().__init__(f"zalo_bot {status}: {detail}" if detail else f"zalo_bot {status}")
        self.status = status


BASE_URL = "https://bot-api.zaloplatforms.com"

#: Tai lieu sendMessage: text dai 1-2000 ky tu.
MAX_MESSAGE_CHARS = 2_000

#: Ma tra ve khi het thoi gian cho ma khong co tin nao. Khong phai loi.
EMPTY_POLL_CODE = 408

#: Poll ngan hon mac dinh 30s cua Zalo: mot vong ngan cho phep dung tien trinh
#: nhanh, va giup phat hien som khi token bi thu hoi.
POLL_TIMEOUT_S = 25

_SEND_TIMEOUT_S = 10.0
_SEND_MAX_ATTEMPTS = 3

_log = get_logger()


def _url(method: str) -> str:
    token = get_settings().ZALO_BOT_TOKEN
    if not token:
        raise ZaloApiError(401, "ZALO_BOT_TOKEN rong")
    return f"{BASE_URL}/bot{token}/{method}"


def _unwrap(body: dict[str, Any]) -> dict[str, Any]:
    """Boc `{"ok": ..., "result": ...}`, doi loi cua API thanh UpstreamError.

    Zalo tra HTTP 200 KEM `ok: false` cho ca loi that su. Chi doc status code thi
    moi loi deu trong nhu thanh cong.
    """
    if body.get("ok"):
        result = body.get("result")
        return result if isinstance(result, dict) else {}

    code = body.get("error_code")
    raise ZaloApiError(
        code if isinstance(code, int) else None,
        str(body.get("description") or ""),
    )


async def get_me() -> dict[str, Any]:
    """Ho so bot. Dung de kiem tra token luc khoi dong thay vi doi tin dau tien."""
    async with httpx.AsyncClient(timeout=_SEND_TIMEOUT_S) as client:
        response = await client.get(_url("getMe"))
    return _unwrap(response.json())


async def get_updates(timeout_s: int = POLL_TIMEOUT_S) -> dict[str, Any] | None:
    """Mot vong long-poll. `None` = het gio ma khong co tin (408), khong phai loi.

    Tra ve `result` da boc: `{"message": {...}, "event_name": "..."}`.
    """
    # Timeout HTTP phai DAI hon timeout long-poll, neu khong client tu ngat truoc
    # khi server kip tra loi va moi tin den dung luc do deu bi mat.
    async with httpx.AsyncClient(timeout=timeout_s + 10) as client:
        response = await client.get(_url("getUpdates"), params={"timeout": timeout_s})

    body = response.json()
    if not body.get("ok") and body.get("error_code") == EMPTY_POLL_CODE:
        return None
    return _unwrap(body)


async def send_message(chat_id: str, text: str) -> str:
    """Gui mot doan text. Tra ve message_id. Da chunk san boi ZaloBotChannel."""
    payload = {"chat_id": chat_id, "text": text}
    last: ZaloApiError | None = None

    for attempt in range(1, _SEND_MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=_SEND_TIMEOUT_S) as client:
                response = await client.post(_url("sendMessage"), json=payload)
            result = _unwrap(response.json())
            message_id = result.get("message_id")
            return message_id if isinstance(message_id, str) else ""
        except (ZaloApiError, httpx.HTTPError) as error:
            last = error if isinstance(error, ZaloApiError) else ZaloApiError(None, str(error))
            # 401/403 la token sai: thu lai ba lan van sai ba lan, chi lam nguoi
            # dung doi lau hon truoc khi thay cau fallback.
            if last.status in (401, 403) or attempt == _SEND_MAX_ATTEMPTS:
                break
            _log.warning("gui tin Zalo that bai, thu lai", attempt=attempt, status=last.status)
            await asyncio.sleep(0.5 * 2 ** (attempt - 1))

    assert last is not None
    raise last
