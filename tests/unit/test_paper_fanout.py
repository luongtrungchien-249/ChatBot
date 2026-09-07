"""Fan-out bon nguon: khong doi nguon cham nhat khi da co ket qua.

Do that trong log truoc khi sua: nguon khoe tra ve sau 2,4-3,2s, nhung ca lan goi mat
dung 10.016ms — mot nguon treo den het tran, ba nguon kia ngoi cho. `asyncio.gather`
doi TAT CA, nen do tre cua ca lan tim bang do tre cua nguon cham nhat. Duong nay nam
trong vong ReAct, tren duong phan hoi.

Khong I/O va khong cham mang: cac "nguon" o day la coroutine ngu mot khoang cho truoc.
Thoi gian trong file nay duoc thu nho (mili-giay) bang cach va hai hang so.
"""

from typing import Any

import pytest

from tools import paper_search
from tools.paper_search import Paper, _fan_out

TEN = ("OpenAlex", "arXiv", "Semantic Scholar", "Crossref")


@pytest.fixture(autouse=True)
def nhanh(monkeypatch: pytest.MonkeyPatch) -> None:
    """Thu nho han cho de test chay trong mili-giay thay vi giay."""
    monkeypatch.setattr(paper_search, "_SOFT_DEADLINE_S", 0.06)
    monkeypatch.setattr(paper_search, "_PER_SOURCE_TIMEOUT_S", 0.20)


def bai(title: str) -> Paper:
    return Paper(title=title, year=2026, doi=None, url=None, abstract=None, citations=None,
                 source="thu")


async def nhanh_chong(title: str) -> list[Paper]:
    import asyncio

    await asyncio.sleep(0.01)
    return [bai(title)]


async def cham(title: str) -> list[Paper]:
    import asyncio

    await asyncio.sleep(5)
    return [bai(title)]


async def hong() -> list[Paper]:
    raise RuntimeError("nguon nay chet")


class Log:
    def __init__(self) -> None:
        self.bo_qua: list[Any] = []

    def debug(self, event: str, **kw: Any) -> None: ...
    def warning(self, event: str, **kw: Any) -> None: ...
    def error(self, event: str, **kw: Any) -> None: ...

    def info(self, event: str, **kw: Any) -> None:
        if "bo qua nguon cham" in event:
            self.bo_qua.append(kw.get("bo_qua"))

    def bind(self, **kw: Any) -> "Log":
        return self


class TestKhongDoiNguonCham:
    async def test_co_ket_qua_thi_KHONG_doi_nguon_cham(self) -> None:
        """Ca da do duoc: mot nguon treo 10s, ba nguon kia xong tu giay thu ba."""
        log = Log()

        ket_qua = await _fan_out(
            (nhanh_chong("a"), cham("b"), nhanh_chong("c"), cham("d")), TEN, "tr", log
        )

        # Hai nguon nhanh cho ket qua that.
        assert ket_qua[0] == [bai("a")]
        assert ket_qua[2] == [bai("c")]
        # Hai nguon cham bi huy, va bao dung kieu loi de cho goi coi nhu "nguon chet".
        assert isinstance(ket_qua[1], BaseException)
        assert isinstance(ket_qua[3], BaseException)

    async def test_ghi_log_nguon_bi_bo_qua(self) -> None:
        """Bo qua trong im lang thi khong ai biet ket qua dang thieu nguon nao."""
        log = Log()

        await _fan_out((nhanh_chong("a"), cham("b"), cham("c"), cham("d")), TEN, "tr", log)

        assert log.bo_qua
        assert set(log.bo_qua[0]) == {"arXiv", "Semantic Scholar", "Crossref"}

    async def test_tat_ca_deu_nhanh_thi_lay_DU_bon_nguon(self) -> None:
        ket_qua = await _fan_out(
            tuple(nhanh_chong(t) for t in "abcd"), TEN, "tr", Log()
        )
        assert [r for r in ket_qua if isinstance(r, list)] == [[bai(t)] for t in "abcd"]


class TestVanChoKhiChuaCoGi:
    async def test_chua_nguon_nao_XONG_thi_cho_them(self) -> None:
        """Thieu mot bai bao con hon khong co bai nao.

        Han mem 60ms; nguon duy nhat tra ve o 120ms. Neu cat cung o han mem thi lan
        tim nay tra ve rong trong khi du lieu chi cham hon mot chut.
        """
        import asyncio

        async def hoi_cham() -> list[Paper]:
            await asyncio.sleep(0.12)
            return [bai("muon")]

        ket_qua = await _fan_out((hoi_cham(), cham("b"), cham("c"), cham("d")), TEN, "tr", Log())

        assert ket_qua[0] == [bai("muon")]

    async def test_nguon_LOI_khong_tinh_la_da_co_ket_qua(self) -> None:
        """`done` co the chi chua nhung task da nem loi. Coi do la "da co ket qua" thi
        mot lan ma bon nguon deu loi nhanh se tra ve rong ma khong cho ai kip tra loi.
        """
        import asyncio

        async def hoi_cham() -> list[Paper]:
            await asyncio.sleep(0.12)
            return [bai("muon")]

        ket_qua = await _fan_out((hong(), hong(), hong(), hoi_cham()), TEN, "tr", Log())

        assert ket_qua[3] == [bai("muon")]

    async def test_moi_nguon_deu_hong_thi_tra_ve_du_bon_loi(self) -> None:
        ket_qua = await _fan_out((hong(), hong(), hong(), hong()), TEN, "tr", Log())

        assert len(ket_qua) == 4
        assert all(isinstance(r, BaseException) for r in ket_qua)


class TestGiuDungThuTu:
    async def test_ket_qua_tra_ve_dung_thu_tu_dau_vao(self) -> None:
        """Cho goi ghep `zip(names, outcomes)` de biet nguon nao hong. Lech thu tu la
        bao sai ten nguon trong log, va do la loai sai khong ai kiem lai.
        """
        ket_qua = await _fan_out(
            (hong(), nhanh_chong("b"), hong(), nhanh_chong("d")), TEN, "tr", Log()
        )

        assert isinstance(ket_qua[0], BaseException)
        assert ket_qua[1] == [bai("b")]
        assert isinstance(ket_qua[2], BaseException)
        assert ket_qua[3] == [bai("d")]

    async def test_chay_duoc_khi_khong_co_logger(self) -> None:
        ket_qua = await _fan_out((nhanh_chong("a"), cham("b")), TEN[:2], "tr", None)
        assert ket_qua[0] == [bai("a")]
