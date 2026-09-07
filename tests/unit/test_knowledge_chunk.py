"""Cat tai lieu — bien so anh huong chat luong tra loi nhieu nhat.

Khong I/O: cat van ban la phep bien doi thuan, va no phai kiem duoc ma khong can
Postgres hay khoa API.
"""

from knowledge.ingest.chunk import (
    OVERLAP_CHARS,
    TARGET_CHARS,
    Chunk,
    chunk_document,
)
from knowledge.ingest.pipeline import contextualize
from knowledge.retrieve.fusion import reciprocal_rank_fusion
from knowledge.retrieve.service import _strip_title

TAI_LIEU = """# So tay 2026

Loi noi dau.

## Hoan tien

Don hoan tien xu ly trong 7 ngay lam viec.

## Nghi phep

Duoc 12 ngay phep nam.

### Phep ton

Chuyen sang quy 1, toi da 5 ngay.
"""


class TestCatTheoTieuDe:
    async def test_moi_muc_thanh_mot_chunk_rieng(self) -> None:
        chunks = chunk_document(TAI_LIEU)
        assert [c.section for c in chunks] == [
            "So tay 2026",
            "So tay 2026 > Hoan tien",
            "So tay 2026 > Nghi phep",
            "So tay 2026 > Nghi phep > Phep ton",
        ]

    async def test_duong_dan_tieu_de_LONG_NHAU_chu_khong_phang(self) -> None:
        """'Phep ton' nam trong 'Nghi phep'. Mat quan he do thi trich dan chi sai cho."""
        chunks = chunk_document(TAI_LIEU)
        assert chunks[-1].section == "So tay 2026 > Nghi phep > Phep ton"

    async def test_van_ban_truoc_tieu_de_dau_tien_KHONG_bi_mat(self) -> None:
        chunks = chunk_document("Mo dau khong co tieu de.\n\n# Muc A\n\nNoi dung.")
        assert any("Mo dau" in c.content for c in chunks)

    async def test_khong_co_tieu_de_nao_van_cat_duoc(self) -> None:
        chunks = chunk_document("Mot doan duy nhat, khong tieu de.")
        assert len(chunks) == 1
        assert chunks[0].section is None

    async def test_ord_tang_dan_va_khong_trung(self) -> None:
        chunks = chunk_document(TAI_LIEU)
        assert [c.ord for c in chunks] == list(range(len(chunks)))

    async def test_doan_dai_hon_tran_thi_bi_cat_nho(self) -> None:
        dai = "Cau van day du. " * (TARGET_CHARS // 8)
        chunks = chunk_document(f"# Muc\n\n{dai}")
        assert len(chunks) > 1
        # Chunk sau chunk dau mang theo phan duoi cua chunk truoc, nen no dai hon
        # tran mot chut — do la overlap, khong phai loi.
        assert all(len(c.content) <= TARGET_CHARS + OVERLAP_CHARS + 8 for c in chunks)

    async def test_chunk_lien_tiep_CHONG_LAN_nhau(self) -> None:
        """Cau tra loi hay nam vat qua ranh gioi: cau hoi khop chunk sau, dieu kien
        cua no lai o cuoi chunk truoc.
        """
        dai = "".join(f"Cau so {i}. " for i in range(TARGET_CHARS // 6))
        chunks = chunk_document(f"# Muc\n\n{dai}")
        duoi_chunk_dau = chunks[0].content[-40:]
        assert duoi_chunk_dau in chunks[1].content

    async def test_khong_tao_chunk_rong(self) -> None:
        chunks = chunk_document("# A\n\n\n\n## B\n\nCo chu.\n")
        assert all(c.content.strip() for c in chunks)


class TestNguCanhChoEmbed:
    async def test_them_ten_tai_lieu_va_muc(self) -> None:
        chunk = Chunk(ord=0, section="Hoan tien", content="7 ngay lam viec.")
        assert contextualize(chunk, "So tay 2026").startswith("[So tay 2026 > Hoan tien]")

    async def test_KHONG_lap_ten_tai_lieu_khi_tieu_de_da_chua(self) -> None:
        chunk = Chunk(ord=0, section="So tay 2026 > Hoan tien", content="x")
        assert contextualize(chunk, "So tay 2026").startswith("[So tay 2026 > Hoan tien]")

    async def test_giu_NGUYEN_VAN_noi_dung(self) -> None:
        """`content` la thu dem di trich dan. Sua mot chu la sai trich dan."""
        chunk = Chunk(ord=0, section=None, content="Ma don: HT-2026-0042.")
        assert "Ma don: HT-2026-0042." in contextualize(chunk, "So tay")


class TestHopNhatXepHang:
    async def test_chunk_xuat_hien_o_CA_HAI_duong_duoc_day_len(self) -> None:
        fused = reciprocal_rank_fusion([[1, 2, 3], [3, 4, 5]])
        assert fused[0].chunk_id == 3

    async def test_mot_duong_rong_van_chay(self) -> None:
        fused = reciprocal_rank_fusion([[7, 8], []])
        assert [f.chunk_id for f in fused] == [7, 8]

    async def test_khong_co_duong_nao_thi_rong(self) -> None:
        assert reciprocal_rank_fusion([]) == []

    async def test_diem_giam_dan(self) -> None:
        fused = reciprocal_rank_fusion([[1, 2, 3, 4]])
        assert [f.score for f in fused] == sorted((f.score for f in fused), reverse=True)


class TestTrichDan:
    async def test_bo_ten_tai_lieu_lap_o_dau_muc(self) -> None:
        assert _strip_title("So tay 2026 > Hoan tien", "So tay 2026") == "Hoan tien"

    async def test_muc_trung_ten_tai_lieu_thi_khong_con_muc(self) -> None:
        assert _strip_title("So tay 2026", "So tay 2026") is None

    async def test_muc_khong_lien_quan_thi_giu_nguyen(self) -> None:
        assert _strip_title("Chuong 2 > Hoan tien", "So tay 2026") == "Chuong 2 > Hoan tien"
