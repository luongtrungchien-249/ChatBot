"""NHIET DO lay mau cho route `poem` — can gat DUY NHAT khong nam o tang prompt.

VI SAO TEP NAY TON TAI. Toan du an chua tung dat tham so nay: moi lan goi tu truoc toi
nay deu chay o mac dinh 1,0. Cai do khong ai ghi lai, va no chi lo ra khi di tim can gat
cho `sang tao` — muc thap nhat cua he thong (1,15/5) — sau khi DA THU HET tang prompt:
9 lan can thiep, 8 lan that bai.

HAI RANG BUOC phai duoc ghim:
  1. `None` = KHONG GUI GI. Mot ngay nao do ai do dat mac dinh khac 0 se doi hanh vi
     cua MOI bai tho ma khong ai thay — nen mac dinh phai duoc test.
  2. CHI route `poem`. Nhiet cao tren route `reply` se lam bot tra loi bay bong hon
     trong khi ca he thong dang ep no bam tai lieu.
"""

from typing import Any

import pytest

import llm.models as models
from llm.models import NHIET_THO


class TestMacDinhKhongDoiHanhVi:
    def test_NHIET_THO_mac_dinh_la_None(self) -> None:
        """None = khong gui `temperature`, tuc giu nguyen hanh vi cu cua MOI route."""
        assert NHIET_THO is None


class TestChiGuiChoRoutePoem:
    """Doc ma nguon: kiem hanh vi that can mang va mot khoa API."""

    def test_temperature_chi_gui_khi_route_la_poem(self) -> None:
        import inspect

        from llm.openai_client import OpenAiLlm

        nguon = inspect.getsource(OpenAiLlm._do_reply)

        assert 'route == "poem"' in nguon
        assert "models.NHIET_THO is not None" in nguon

    def test_doc_NHIET_THO_luc_chay_chu_khong_nhap_thang(self) -> None:
        """Nhap thang hang so thi phep do A/B khong doi duoc no giua hai nhanh."""
        import inspect

        from llm.openai_client import OpenAiLlm

        nguon = inspect.getsource(OpenAiLlm._do_reply)

        assert "models.NHIET_THO" in nguon, "phải đọc qua module, không nhập thẳng"


class TestDoiDuocLucChay:
    """Phep do A/B doi `NHIET_THO` giua hai nhanh TRONG CUNG mot tien trinh."""

    @pytest.fixture(autouse=True)
    def _tra_lai(self) -> Any:
        cu = models.NHIET_THO
        yield
        models.NHIET_THO = cu

    def test_dat_roi_tra_lai_duoc(self) -> None:
        models.NHIET_THO = 1.4

        assert models.NHIET_THO == 1.4


class TestDaQuetVaDaGiuNone:
    """Ket qua quet 14/09 — ghim de khong ai bat len ma khong doc con so."""

    def test_van_giu_None_sau_khi_da_quet(self) -> None:
        """`sang tao` phang 1,35-1,65 tren ca bon muc, con moi chi so khac thi sup."""
        assert NHIET_THO is None

    def test_con_so_quet_duoc_ghi_ngay_canh_hang_so(self) -> None:
        import inspect

        khoi = inspect.getsource(models).split("NHIET_THO: float | None = None")[0]

        for dau_hieu in ("DA QUET", "sang tao", "khung %", "1,6"):
            assert dau_hieu in khoi, f"thiếu {dau_hieu!r} trong ghi chú của NHIET_THO"
