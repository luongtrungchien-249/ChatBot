"""Chon thuoc do de LOC ket qua tim kiem: diem rerank hay khoang cach vector.

Luat trung tam: mot thuoc do chi duoc dung de loc khi no la DO LIEN QUAN da hieu
chuan. Ban rerank du phong cham do trung TU VUNG — mot dai luong khac han — nen no
duoc quyen xep thu tu nhung khong duoc quyen phu quyet.

Do duoc 08/09/2026 tren corpus tieng Anh voi cau hoi tieng Viet: ban du phong cham
0,00 cho cau khong co tu tieng Anh nao, trong khi tang vector tim dung chunk o hang
1. Dung diem do de loc lam 7/10 cau hoi tieng Viet bi tra ve rong — bot noi "khong
tim thay" ve thu dang nam trong CSDL.

Khong I/O.
"""

import pytest

from knowledge.retrieve.search import ChunkRow
from knowledge.retrieve.service import HybridKnowledge
from llm.reranker import CohereReranker, LexicalOverlapReranker, RerankHit


def row(chunk_id: int, distance: float | None) -> ChunkRow:
    return ChunkRow(
        chunk_id=chunk_id,
        doc_title="So tay",
        section="Muc",
        page=1,
        content=f"noi dung {chunk_id}",
        distance=distance,
    )


class TestKhaiBaoDiemDangTin:
    """Co nay quyet dinh ca duong di. Dat sai la hong toan bo tang loc."""

    async def test_cross_encoder_that_thi_diem_dang_tin(self) -> None:
        assert CohereReranker.diem_dang_tin is True

    async def test_ban_du_phong_thi_KHONG(self) -> None:
        assert LexicalOverlapReranker.diem_dang_tin is False


class TestLocTheoDiem:
    """Duong chuan, giu nguyen hanh vi cu."""

    async def test_giu_cai_dat_nguong_bo_cai_duoi(self) -> None:
        kept = HybridKnowledge._loc_theo_diem(
            [RerankHit(index=0, score=0.9), RerankHit(index=1, score=0.2)],
            [row(1, 0.3), row(2, 0.3)],
            nguong=0.45,
        )

        assert [c.chunk_id for c in kept] == ["1"]

    async def test_deu_duoi_nguong_thi_RONG(self) -> None:
        """Rong la hop dong: "khong co trong tai lieu"."""
        kept = HybridKnowledge._loc_theo_diem(
            [RerankHit(index=0, score=0.1)], [row(1, 0.3)], nguong=0.45
        )

        assert kept == []

    async def test_KHONG_dung_khoang_cach_o_duong_nay(self) -> None:
        """Cross-encoder that da phan xu roi; khoang cach khong duoc phu quyet no."""
        kept = HybridKnowledge._loc_theo_diem(
            [RerankHit(index=0, score=0.9)], [row(1, distance=0.99)], nguong=0.45
        )

        assert len(kept) == 1


class TestLocTheoKhoangCach:
    """Duong du phong — phan duoc them 08/09/2026."""

    async def test_giu_chunk_GAN_bo_chunk_XA(self) -> None:
        kept = HybridKnowledge._loc_theo_khoang_cach(
            [RerankHit(index=0, score=0.0), RerankHit(index=1, score=0.0)],
            [row(1, 0.60), row(2, 0.92)],
            tran=0.78,
        )

        assert [c.chunk_id for c in kept] == ["1"]

    async def test_DIEM_BANG_KHONG_van_duoc_giu_neu_du_gan(self) -> None:
        """Ca quan trong nhat cua ca tep.

        Cau hoi tieng Viet tren tai lieu tieng Anh cho diem tu vung 0,00. Truoc day
        no bi loai sach; gio khoang cach ngu nghia moi la nguoi phan xu.
        """
        kept = HybridKnowledge._loc_theo_khoang_cach(
            [RerankHit(index=0, score=0.0)], [row(1, 0.70)], tran=0.78
        )

        assert len(kept) == 1

    async def test_van_noi_duoc_KHONG_TIM_THAY(self) -> None:
        """Kha nang tu choi phai con nguyen. Bo tang loc di thi bot se tra loi moi
        cau hoi bang mot chunk bat ky — te hon han truong hop cu.
        """
        kept = HybridKnowledge._loc_theo_khoang_cach(
            [RerankHit(index=0, score=0.0), RerankHit(index=1, score=0.0)],
            [row(1, 0.83), row(2, 0.91)],
            tran=0.78,
        )

        assert kept == []

    async def test_chunk_tu_BM25_khong_co_khoang_cach_thi_GIU(self) -> None:
        """Khop duoc bang tu la tin hieu doc lap va manh. Bo no vi thieu mot thuoc
        do khac la vut di ket qua tot nhat cua duong lexical.
        """
        kept = HybridKnowledge._loc_theo_khoang_cach(
            [RerankHit(index=0, score=0.8)], [row(1, distance=None)], tran=0.78
        )

        assert len(kept) == 1

    async def test_dung_ngay_tren_tran_thi_giu(self) -> None:
        kept = HybridKnowledge._loc_theo_khoang_cach(
            [RerankHit(index=0, score=0.0)], [row(1, 0.78)], tran=0.78
        )

        assert len(kept) == 1

    async def test_giu_nguyen_THU_TU_cua_reranker(self) -> None:
        """Ban du phong mat quyen LOC nhung giu quyen XEP THU TU — do van la thong
        tin that, chi khong phai do lien quan da hieu chuan.
        """
        kept = HybridKnowledge._loc_theo_khoang_cach(
            [RerankHit(index=1, score=0.6), RerankHit(index=0, score=0.2)],
            [row(1, 0.5), row(2, 0.5)],
            tran=0.78,
        )

        assert [c.chunk_id for c in kept] == ["2", "1"]


class TestBanDuPhongChamDiem:
    @pytest.mark.parametrize(
        "cau",
        [
            "lam sao de nau nuoc dung tu xuong bo",
            "huong dan luoc trung",
        ],
    )
    async def test_cau_tieng_viet_tren_van_ban_tieng_anh_ra_0(self, cau: str) -> None:
        """Chung minh ly do ton tai cua ca duong du phong: khong phai chunk khong
        lien quan, ma la thuoc do khong do duoc gi.
        """
        hits = await LexicalOverlapReranker().rerank(
            cau, ["How to make stocks: place the beef bones into a large pot."], 1
        )

        assert hits[0].score == 0.0
