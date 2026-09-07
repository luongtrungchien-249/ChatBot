"""Ban rerank khong can khoa.

No khong phai cross-encoder va khong gia vo la mot cai — nhung no la thu chay khi
RERANK_PROVIDER chua duoc chot, nen no phai bat duoc dung ca ma tai lieu (thu ma
hybrid search ton tai de bat) va phai tra diem trong [0;1] de nguong con nghia.
"""

from llm.reranker import LexicalOverlapReranker, _terms

DOCS = [
    "Don hoan tien duoc xu ly trong 7 ngay lam viec. Ma don co dang HT-2026-0042.",
    "Nhan vien chinh thuc duoc 12 ngay phep nam.",
    "Quy trinh duyet chi gom ba buoc.",
]


class TestTachTu:
    async def test_tach_theo_ky_tu_chu_so_chu_khong_theo_khoang_trang(self) -> None:
        """Da troi that: "HT-2026" khong khop "HT-2026-xxxx" khi tach theo khoang trang."""
        assert "2026" in _terms("HT-2026")
        assert "ht" in _terms("HT-2026")

    async def test_bo_dau_truoc_khi_so_khop(self) -> None:
        assert _terms("nghỉ phép") == _terms("nghi phep")

    async def test_bo_tu_mot_ky_tu(self) -> None:
        assert "a" not in _terms("a b hoan tien")


class TestXepHang:
    async def test_ma_tai_lieu_tim_dung_chunk(self) -> None:
        hits = await LexicalOverlapReranker().rerank("HT-2026", DOCS, 3)
        assert hits[0].index == 0
        assert hits[0].score == 1.0

    async def test_cau_hoi_thuong_tim_dung_chunk(self) -> None:
        hits = await LexicalOverlapReranker().rerank("nghi phep nam", DOCS, 3)
        assert hits[0].index == 1

    async def test_diem_nam_trong_khoang_0_1(self) -> None:
        hits = await LexicalOverlapReranker().rerank("hoan tien ngay", DOCS, 3)
        assert all(0.0 <= h.score <= 1.0 for h in hits)

    async def test_tra_ve_toi_da_top_n(self) -> None:
        assert len(await LexicalOverlapReranker().rerank("ngay", DOCS, 2)) == 2

    async def test_danh_sach_rong(self) -> None:
        assert await LexicalOverlapReranker().rerank("x", [], 5) == []

    async def test_cau_hoi_khong_co_tu_nao_dung_van_khong_nem(self) -> None:
        hits = await LexicalOverlapReranker().rerank("?", DOCS, 2)
        assert len(hits) == 2
        assert all(h.score == 0.0 for h in hits)

    async def test_cau_hoi_khong_lien_quan_duoc_diem_0(self) -> None:
        """Diem 0 nam duoi RERANK_MIN_SCORE, nen no thanh 'khong tim thay'."""
        hits = await LexicalOverlapReranker().rerank("bitcoin ethereum", DOCS, 3)
        assert max(h.score for h in hits) == 0.0
