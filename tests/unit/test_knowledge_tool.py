"""Cong cu `search_knowledge_base` — phan model doc va phan model nhan lai.

Khong I/O: cai gia cho KnowledgePort la du, va do la ly do ton tai cua ports.
"""

from typing import Any

import pytest

from agents.domain.knowledge import RetrievedChunk
from tools import knowledge_search
from tools.knowledge_search import (
    KNOWLEDGE_SEARCH_DEFINITION,
    is_knowledge_search_available,
    run_knowledge_search,
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
        async def search(self, query: str, k: int) -> list[RetrievedChunk]:
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


class TestKetQua:
    async def test_kem_nguon_va_muc_de_trich_dan(self, kho: list[RetrievedChunk]) -> None:
        kho.append(chunk("Don hoan tien xu ly trong 7 ngay lam viec."))

        out = await run_knowledge_search({"query": "hoan tien"}, "tr")

        assert "So tay nhan vien 2026" in out
        assert "Chinh sach hoan tien" in out
        assert "7 ngay lam viec" in out

    async def test_khong_co_muc_thi_van_chay(self, kho: list[RetrievedChunk]) -> None:
        kho.append(chunk("Noi dung.", section=None))
        assert "So tay nhan vien 2026" in await run_knowledge_search({"query": "x"}, "tr")

    async def test_khong_tim_thay_thi_NOI_THANG(self, kho: list[RetrievedChunk]) -> None:
        """Cau nay di thang vao prompt. No phai day model noi that thay vi lay kien
        thuc chung ra thay the.
        """
        out = await run_knowledge_search({"query": "gia bitcoin"}, "tr")

        assert "Không tìm thấy" in out
        assert "đừng thay bằng kiến thức chung" in out

    async def test_thieu_query_thi_nem(self, kho: list[RetrievedChunk]) -> None:
        with pytest.raises(ValueError):
            await run_knowledge_search({}, "tr")

    async def test_query_rong_thi_nem(self, kho: list[RetrievedChunk]) -> None:
        with pytest.raises(ValueError):
            await run_knowledge_search({"query": "   "}, "tr")

    async def test_query_khong_phai_chuoi_thi_nem(self, kho: list[RetrievedChunk]) -> None:
        payload: dict[str, Any] = {"query": 42}
        with pytest.raises(ValueError):
            await run_knowledge_search(payload, "tr")
