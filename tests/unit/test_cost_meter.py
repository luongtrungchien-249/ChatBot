"""Ke toan chi phi: route ghi ra phai KHOP route goi vao, va gia phai theo DUNG model.

VI SAO TEP NAY TON TAI. Loi da chay trong nhieu ngay ma khong ai thay:

    OpenAiLlm.reply(..., route="poem")  ->  self._measured("reply", ...)
                                                           ^^^^^^^ ghi cung

Moi luot lam tho bi ghi model cua route `reply` (gpt-5-mini) va tinh theo GIA cua
gpt-5-mini, trong khi lan goi that chay tren gpt-4o-mini.

Do 12/09/2026 tren 3.920 luot that: so ghi $1,15, dung ra $0,41 — THUA 2,8 lan.

Ba hau qua, va ca ba deu IM LANG:
  - chan ngan sach ban som gap 2,8 lan (da phai nang DAILY_BUDGET_USD vi tuong het tien)
  - `usage_log` khong phan biet duoc model nao lam gi -> moi so sanh chi phi deu sai
  - moi bao cao chi phi deu cao hon thuc te

Loi nay khong co test nao bat duoc vi khong co test nao cho `cost_meter`.
"""

import pytest

from agents.domain.thread import ThreadScope
from agents.ports.llm import LlmUsage
from llm.cost_meter import UsageRecord, cost_of
from llm.models import MODELS, Route, model_cho

_DUNG = LlmUsage(input_tokens=1_000_000, output_tokens=0, cache_read_tokens=0, cache_write_tokens=0)
_RA = LlmUsage(input_tokens=0, output_tokens=1_000_000, cache_read_tokens=0, cache_write_tokens=0)

#: Moi route hop le. `poem` la route DUY NHAT khong nam trong `MODELS`.
_MOI_ROUTE: tuple[Route, ...] = (
    "reply",
    "rewrite",
    "summarize",
    "extract_facts",
    "compress",
    "poem",
)


class TestCostOfMoiRoute:
    """`cost_of` phai chay duoc cho MOI route, ke ca route khong co trong `MODELS`."""

    @pytest.mark.parametrize("route", _MOI_ROUTE)
    def test_khong_nem_loi(self, route: Route) -> None:
        """`poem` doc config nen no KHONG nam trong `MODELS` — tra thang vao dict thi
        KeyError. Kieu `Route` van liet ke no, tuc kieu NOI DOI ve do an toan.
        """
        assert cost_of(route, _DUNG) >= 0.0

    @pytest.mark.parametrize("route", _MOI_ROUTE)
    def test_gia_khop_model_THAT_cua_route(self, route: Route) -> None:
        """Gia phai lay tu model ma route do THUC SU chay, khong phai model cua route khac."""
        model = model_cho(route)

        assert cost_of(route, _DUNG) == pytest.approx(model.price_in)
        assert cost_of(route, _RA) == pytest.approx(model.price_out)

    def test_poem_KHONG_nam_trong_MODELS(self) -> None:
        """Ghim chinh cai bay: `MODELS[route]` khong dung duoc cho moi route.

        Ngay nao `poem` duoc them vao `MODELS` thi test nay do, va nguoi sua se doc
        docstring dau tep de biet vi sao no tung bi tach ra.
        """
        assert "poem" not in MODELS
        assert model_cho("poem") is not None


class TestRouteGhiRaKhopRouteGoiVao:
    """Route ghi vao `usage_log` phai la route THAT, khong phai mot hang so ghi cung."""

    def test_UsageRecord_giu_nguyen_route(self) -> None:
        ban_ghi = UsageRecord(
            route="poem",
            usage=_DUNG,
            scope=ThreadScope(platform="cli", thread_id="t"),
            sender_id="s",
            trace_id="tr",
            latency_ms=1,
            ok=True,
        )

        assert ban_ghi.route == "poem"

    async def test_reply_TRUYEN_route_xuong_khau_do(self) -> None:
        """Ca am cho chinh loi da xay ra: `reply()` phai chuyen `route` xuong `_measured`.

        Bat bang cach doc ma nguon — kiem hanh vi that can mang va mot ban ghi DB, con
        cho hong thi chi la mot chuoi ghi cung, va doc ma nguon la du de ghim no.
        """
        import inspect

        from llm.openai_client import OpenAiLlm

        nguon = inspect.getsource(OpenAiLlm.reply)

        assert "self._measured(" in nguon
        assert '_measured(\n            "reply"' not in nguon, "route bị ghi cứng"
