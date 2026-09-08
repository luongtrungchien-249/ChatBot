"""Cong cu `search_knowledge_base` — phan model doc va phan model nhan lai.

Khong I/O: cai gia cho KnowledgePort la du, va do la ly do ton tai cua ports.
"""

from typing import Any

import pytest

from agents.domain.knowledge import RetrievedChunk
from agents.domain.thread import ThreadScope
from agents.ports.llm import CallContext
from tools import knowledge_search
from tools.knowledge_search import (
    KNOWLEDGE_SEARCH_DEFINITION,
    is_knowledge_search_available,
    run_knowledge_search,
)


#: Pham vi di cung moi lan goi cong cu, y het hop dong cua memory_fact.
CTX = CallContext(
    scope=ThreadScope(platform="cli", thread_id="t1"), sender_id="u1", trace_id="tr"
)


def chunk(content: str, section: str | None = "Chinh sach hoan tien") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="1",
        doc_title="So tay nhan vien 2026",
        section=section,
        page=None,
        content=content,
        score=0.9,
    )


@pytest.fixture
def kho(monkeypatch: pytest.MonkeyPatch) -> list[RetrievedChunk]:
    """Thay KnowledgePort that bang mot cai gia, tra ve danh sach do test dat vao."""
    ket_qua: list[RetrievedChunk] = []

    class KhoGia:
        async def search(
            self, scope: ThreadScope, query: str, k: int
        ) -> list[RetrievedChunk]:
            return ket_qua

    import knowledge.retrieve.service as service

    monkeypatch.setattr(service, "knowledge", KhoGia())
    return ket_qua


class TestKhaiBao:
    async def test_mo_ta_noi_ro_khi_nao_KHONG_dung(self) -> None:
        """Model doc dong nay de chon cong cu. Chi noi "tim tai lieu" thi no se goi
        ca khi nguoi dung hoi gia bitcoin.
        """
        assert "web_search" in KNOWLEDGE_SEARCH_DEFINITION.description

    async def test_khong_khai_khi_chua_co_tai_lieu(self) -> None:
        """Cho model thay mot cong cu roi de no tra ve rong lien tuc la day no bia."""
        knowledge_search._has_documents = False
        assert is_knowledge_search_available() is False

    async def test_khai_khi_da_co_tai_lieu(self) -> None:
        knowledge_search._has_documents = True
        assert is_knowledge_search_available() is True

    async def test_schema_chan_tham_so_la(self) -> None:
        assert KNOWLEDGE_SEARCH_DEFINITION.parameters["additionalProperties"] is False


class TestMoTaNoiDungKho:
    """Mo ta cong cu la CODE, khong phai chu thich — model doc no de quyet dinh.

    Ban dau mo ta viet kho la "tai lieu noi bo cua to chuc: quy dinh, quy trinh,
    chinh sach" va bao dung "TRUOC khi tra loi cau hoi ve cach to chuc nay lam viec".
    Do duoc tren bot that: hoi "Ga ham bi do can nguyen lieu gi" — mot mon CO trong
    kho — model KHONG goi cong cu nay lan nao, vi cau hoi khong giong "cach to chuc
    lam viec". No tra loi tu tri nho, khong nguon.

    Sau khi mo ta noi ro kho co the chua BAT KY loai tai lieu nao va model khong biet
    trong do co gi cho toi khi tra: 6/6 nhom do deu dat.
    """

    async def test_khong_bo_hep_kho_vao_moi_tai_lieu_quan_tri(self) -> None:
        mo_ta = KNOWLEDGE_SEARCH_DEFINITION.description
        assert "BẤT KỲ" in mo_ta

    async def test_noi_ro_model_KHONG_BIET_trong_kho_co_gi(self) -> None:
        assert "KHÔNG BIẾT TRONG KHO CÓ GÌ" in KNOWLEDGE_SEARCH_DEFINITION.description

    async def test_bat_tra_TRUOC_khi_tra_loi_tu_tri_nho(self) -> None:
        mo_ta = KNOWLEDGE_SEARCH_DEFINITION.description
        assert "TRƯỚC" in mo_ta
        assert "trí nhớ" in mo_ta


class TestKetQua:
    async def test_kem_nguon_va_muc_de_trich_dan(self, kho: list[RetrievedChunk]) -> None:
        kho.append(chunk("Don hoan tien xu ly trong 7 ngay lam viec."))

        out = await run_knowledge_search({"query": "hoan tien"}, CTX)

        assert "So tay nhan vien 2026" in out
        assert "Chinh sach hoan tien" in out
        assert "7 ngay lam viec" in out

    async def test_khong_co_muc_thi_van_chay(self, kho: list[RetrievedChunk]) -> None:
        kho.append(chunk("Noi dung.", section=None))
        assert "So tay nhan vien 2026" in await run_knowledge_search({"query": "x"}, CTX)

    async def test_khong_tim_thay_thi_NOI_THANG(self, kho: list[RetrievedChunk]) -> None:
        """Cau nay di thang vao prompt, va no la don bay manh nhat cua ca luong: no
        den DUNG khoanh khac model vua thay ket qua rong.
        """
        out = await run_knowledge_search({"query": "gia bitcoin"}, CTX)

        assert "Không tìm thấy" in out
        # Tri nho cua model van bi cam — do la luat cu, KHONG doi.
        assert "đừng lấy trí nhớ của bạn ra thay thế" in out.lower() or (
            "trí nhớ" in out and "thay thế" in out
        )

    async def test_CHAN_tra_web_cho_cau_hoi_noi_bo(self, kho: list[RetrievedChunk]) -> None:
        """Nhanh nguy hiem hon trong hai nhanh.

        Web tra ve luat lao dong chung cho cau "chinh sach nghi phep nam" — hop ly,
        co nguon, va SAI voi to chuc nay. Thong diep phai noi ro VI SAO cam, khong
        chi ra lenh: model tuan lenh co ly do tot hon lenh tran.
        """
        out = await run_knowledge_search({"query": "chinh sach nghi phep"}, CTX)

        assert "ĐỪNG tra web" in out
        assert "quy định riêng" in out

    async def test_CHO_PHEP_tra_web_cho_kien_thuc_chung(
        self, kho: list[RetrievedChunk]
    ) -> None:
        out = await run_knowledge_search({"query": "cach lam bun cha"}, CTX)

        assert "web_search" in out
        assert "lấy từ web" in out

    async def test_thieu_query_thi_nem(self, kho: list[RetrievedChunk]) -> None:
        with pytest.raises(ValueError):
            await run_knowledge_search({}, CTX)

    async def test_query_rong_thi_nem(self, kho: list[RetrievedChunk]) -> None:
        with pytest.raises(ValueError):
            await run_knowledge_search({"query": "   "}, CTX)

    async def test_query_khong_phai_chuoi_thi_nem(self, kho: list[RetrievedChunk]) -> None:
        payload: dict[str, Any] = {"query": 42}
        with pytest.raises(ValueError):
            await run_knowledge_search(payload, "tr")
