"""Chi so cua bo eval — thu do cai khac, nen chinh no phai duoc do truoc.

Mot chi so tinh sai khong bao gio tu bao: no chi cho ra mot con so trong hop ly, va
moi quyet dinh dua tren no deu sai theo.
"""

from evals.metrics.latency import percentile
from evals.metrics.recall import recall_at_k
from evals.runner import Row, is_placeholder


class TestRecall:
    async def test_chunk_dung_nam_trong_top_k(self) -> None:
        assert recall_at_k(["a", "b", "c"], ["b"], k=5) == 1.0

    async def test_chunk_dung_nam_NGOAI_top_k(self) -> None:
        assert recall_at_k(["a", "b", "c"], ["c"], k=2) == 0.0

    async def test_mot_phan(self) -> None:
        assert recall_at_k(["a", "b"], ["a", "z"], k=5) == 0.5

    async def test_cau_khong_can_tai_lieu_KHONG_tinh_la_truot(self) -> None:
        """Khong co chunk mong doi nghia la cau hoi khong can tra cuu. Cham 0 cho no
        se keo diem xuong vi mot dieu no khong he lam sai.
        """
        assert recall_at_k([], [], k=5) == 1.0


class TestPercentile:
    async def test_p95_cua_danh_sach_deu(self) -> None:
        assert percentile([float(i) for i in range(1, 101)], 0.95) == 96.0

    async def test_danh_sach_rong(self) -> None:
        assert percentile([], 0.95) == 0.0

    async def test_mot_phan_tu(self) -> None:
        assert percentile([7.0], 0.95) == 7.0

    async def test_khong_phu_thuoc_thu_tu_dau_vao(self) -> None:
        assert percentile([9.0, 1.0, 5.0], 0.5) == percentile([1.0, 5.0, 9.0], 0.5)


class TestDatasetMau:
    """Bo eval chay tren du lieu mau roi bao "dat" con te hon khong co eval: no cho
    ta niem tin ma khong kiem chung dieu gi.
    """

    def _row(self, question: str) -> Row:
        return Row(id="1", question=question, answer="x", expected_chunk_ids=[])

    async def test_nhan_ra_dong_mau(self) -> None:
        assert is_placeholder([self._row("VI DU - thay bang cau hoi that")]) is True

    async def test_dataset_rong_cung_la_chua_co_gi(self) -> None:
        assert is_placeholder([]) is True

    async def test_cau_hoi_that_thi_khong_phai_mau(self) -> None:
        assert is_placeholder([self._row("Hoàn tiền mất bao lâu?")]) is False

    async def test_chi_mot_cau_that_da_du_de_chay(self) -> None:
        rows = [self._row("VI DU - mau"), self._row("Hoàn tiền mất bao lâu?")]
        assert is_placeholder(rows) is False
