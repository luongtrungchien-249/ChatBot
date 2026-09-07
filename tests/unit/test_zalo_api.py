"""Hop dong voi Zalo Bot API — cac diem da kiem chung bang lenh goi that.

Test o day khong cham mang: chung chot lai CACH DOC phan hoi, vi do moi la cho
sai duoc mot cach im lang.
"""

import httpx
import pytest

from adapters.zalo_bot import api
from adapters.zalo_bot.api import (
    EMPTY_POLL_CODE,
    MAX_MESSAGE_CHARS,
    ZaloApiError,
    _unwrap,
)


class TestDocPhanHoi:
    def test_ok_true_thi_tra_ve_result(self) -> None:
        assert _unwrap({"ok": True, "result": {"message_id": "abc"}}) == {"message_id": "abc"}

    def test_ok_false_thi_nem_loi_kem_status(self) -> None:
        # Zalo tra HTTP 200 KEM ok:false. Chi doc status code thi moi loi deu
        # trong nhu thanh cong — day la cho de sai nhat cua ca adapter.
        with pytest.raises(ZaloApiError) as caught:
            _unwrap({"ok": False, "description": "Unauthorized", "error_code": 401})
        assert caught.value.status == 401

    def test_khong_co_error_code_thi_status_None(self) -> None:
        with pytest.raises(ZaloApiError) as caught:
            _unwrap({"ok": False})
        assert caught.value.status is None


class TestPollRong:
    async def test_408_la_BINH_THUONG_khong_phai_loi(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Da kiem chung bang curl: nhom im lang -> ok:false, error_code:408.

        Coi day la loi thi vong poll backoff nham va bot tre hang phut, dong thoi
        log day canh bao gia.
        """
        body = {"ok": False, "description": "Request timeout", "error_code": EMPTY_POLL_CODE}
        _fake_get(monkeypatch, body)

        assert await api.get_updates(1) is None

    async def test_loi_that_su_van_duoc_nem(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _fake_get(monkeypatch, {"ok": False, "error_code": 401})

        with pytest.raises(ZaloApiError):
            await api.get_updates(1)

    async def test_co_tin_thi_tra_ve_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        result = {"message": {"text": "hi"}, "event_name": "message.text.received"}
        _fake_get(monkeypatch, {"ok": True, "result": result})

        assert await api.get_updates(1) == result

    async def test_timeout_HTTP_dai_hon_timeout_long_poll(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nguoc lai la client tu ngat truoc khi server kip tra loi.

        Hau qua: moi tin den dung o cuoi cua so poll deu bi mat, va trieu chung
        nhin y het "Zalo khong gui tin" — mot loi rat kho lan ra.
        """
        seen: dict[str, float] = {}

        class Client:
            async def get(
                self,
                url: str,
                params: dict[str, int] | None = None,
                timeout: float = 0.0,
            ) -> httpx.Response:
                # Timeout gio di theo TUNG lan goi, khong nam o constructor cua client:
                # ca process dung chung mot pool (infra/http.py), va mot vong long-poll
                # 25 giay khong the ap dat timeout cua no len moi loi goi khac.
                seen["timeout"] = timeout
                seen["poll"] = float((params or {}).get("timeout", 0))
                return httpx.Response(200, json={"ok": True, "result": {}})

        monkeypatch.setattr(api, "get_http", lambda: Client())
        monkeypatch.setattr(api, "_url", lambda method: f"http://test/{method}")

        await api.get_updates(25)
        assert seen["timeout"] > seen["poll"]


class TestGioiHanDoDai:
    def test_khop_gioi_han_tai_lieu(self) -> None:
        # sendMessage: text 1-2000 ky tu. Gui dai hon thi Zalo cat cut phan duoi
        # ma van bao thanh cong.
        assert MAX_MESSAGE_CHARS == 2_000


def _fake_get(monkeypatch: pytest.MonkeyPatch, body: dict[str, object]) -> None:
    """Thay chinh cho ma adapter lay client ra.

    Truoc day test vá thang `httpx.AsyncClient`. Cho noi do khong con: adapter goi
    `get_http()` de lay pool dung chung cua ca process. Vá o cho cu thi test van xanh
    trong khi code that di mot duong khac — va lan doi that su lam ba test do.
    """

    class Client:
        async def get(
            self, url: str, params: dict[str, int] | None = None, timeout: float = 0.0
        ) -> httpx.Response:
            return httpx.Response(200, json=body)

    monkeypatch.setattr(api, "get_http", lambda: Client())
    monkeypatch.setattr(api, "_url", lambda method: f"http://test/{method}")
