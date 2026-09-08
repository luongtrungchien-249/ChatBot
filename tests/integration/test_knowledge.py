"""RAG tren POSTGRES THAT — nap tai lieu roi hoi lai.

Vi sao khong fake duoc: hai thu quan trong nhat cua duong nay chi ton tai trong
Postgres. `tsv` la generated column chay qua `vn_tsv()` (bo dau tieng Viet), va
toan tu `<=>` la cua pgvector. Fake ca hai nghia la test mot he thong khac.

Tu bo qua khi khong co Postgres, co neu ly do. Tren CI thi DO — xem tests/conftest.py.

Chay: docker compose -f ops/docker-compose.yml up -d postgres && uv run pytest tests/integration
"""

import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from agents.domain.thread import ThreadScope
from infra.db import execute, fetch
from knowledge.ingest.pipeline import ingest_file
from knowledge.retrieve.search import lexical_search, vector_search
from knowledge.retrieve.service import knowledge

#: Pham vi cua lan tim. Tai lieu nap qua cli co pham_vi="chung" nen moi nhom deu
#: doc duoc — day la mac dinh, va no duoc test rieng o test_ho_so/test_loc.
SCOPE = ThreadScope(platform="cli", thread_id="test")

TAI_LIEU = """# So tay thu nghiem

## Chinh sach hoan tien

Don hoan tien duoc xu ly trong 7 ngay lam viec ke tu khi nhan hang tra ve.
Ma don hoan tien co dang HT-2026-0042.

## Nghi phep nam

Nhan vien chinh thuc duoc 12 ngay phep nam mỗi năm.
"""


@pytest.fixture
async def tai_lieu_da_nap(postgres_san_sang: None, tmp_path: Path) -> AsyncIterator[str]:
    """Nap mot tai lieu that, tra ve tieu de, roi don sach."""
    title = f"So tay {uuid.uuid4()}"
    path = tmp_path / "so-tay.md"
    path.write_text(TAI_LIEU, encoding="utf-8")

    await ingest_file(path, ingested_by="test", title=title)
    yield title
    # kb_chunk co ON DELETE CASCADE nen xoa tai lieu la xoa het chunk theo.
    await execute("DELETE FROM kb_document WHERE title = $1", title)


class TestNap:
    async def test_nap_xong_thi_co_chunk_trong_bang(self, tai_lieu_da_nap: str) -> None:
        rows = await fetch(
            """SELECT count(*) AS n FROM kb_chunk c JOIN kb_document d ON d.id = c.doc_id
                WHERE d.title = $1""",
            tai_lieu_da_nap,
        )
        assert rows[0]["n"] >= 2

    async def test_nap_LAI_y_het_thi_khong_lam_gi(
        self, tai_lieu_da_nap: str, tmp_path: Path
    ) -> None:
        """Embed lai vai tram chunk de ra dung ket qua cu la dot tien."""
        path = tmp_path / "so-tay.md"
        result = await ingest_file(path, ingested_by="test", title=tai_lieu_da_nap)
        assert result.skipped is True
        assert result.chunks == 0

    async def test_noi_dung_doi_thi_len_PHIEN_BAN_moi(
        self, tai_lieu_da_nap: str, tmp_path: Path
    ) -> None:
        """Sua tai cho se lam moi trich dan cu noi doi. Nen phai la ban moi."""
        path = tmp_path / "so-tay.md"
        path.write_text(TAI_LIEU + "\n## Muc moi\n\nNoi dung moi.\n", encoding="utf-8")

        result = await ingest_file(path, ingested_by="test", title=tai_lieu_da_nap)

        assert result.skipped is False
        assert result.version == 2

    async def test_ghi_lai_AI_da_nap(self, tai_lieu_da_nap: str) -> None:
        rows = await fetch(
            "SELECT ingested_by FROM kb_document WHERE title = $1", tai_lieu_da_nap
        )
        assert rows[0]["ingested_by"] == "test"

    async def test_giu_NGUYEN_VAN_de_trich_dan(self, tai_lieu_da_nap: str) -> None:
        """`content` la thu se hien ra cho nguoi dung; `embed_input` moi la ban co
        them dong ngu canh.
        """
        rows = await fetch(
            """SELECT c.content, c.embed_input FROM kb_chunk c
                 JOIN kb_document d ON d.id = c.doc_id
                WHERE d.title = $1 AND c.content LIKE '%HT-2026-0042%'""",
            tai_lieu_da_nap,
        )
        assert rows
        assert not rows[0]["content"].startswith("[")
        assert rows[0]["embed_input"].startswith("[")


class TestHaiDuongTim:
    async def test_vector_tim_duoc_theo_Y_NGHIA(
        self, tai_lieu_da_nap: str, embedding_that: None
    ) -> None:
        """Can embedding THAT.

        Ban gia sinh vector tu hash, nen "bao lau thi duoc tra lai tien" va "hoan
        tien 7 ngay" ra hai vector khong lien quan. Chay test nay voi embedder gia
        la tu lua: no se do (hoac xanh) vi mot ly do khong dinh gi toi ngu nghia.
        """
        hits = await vector_search(SCOPE, "bao lau thi duoc tra lai tien", limit=5)
        assert any("hoan tien" in h.content.lower() for h in hits)

    async def test_lexical_tim_duoc_theo_MA_SO(self, tai_lieu_da_nap: str) -> None:
        """Dung ca ma vector search hong nhat: ma san pham, so hieu van ban."""
        hits = await lexical_search(SCOPE, "HT-2026-0042", limit=5)
        assert any("HT-2026-0042" in h.content for h in hits)

    async def test_lexical_tim_duoc_theo_TEN_MUC(self, tai_lieu_da_nap: str) -> None:
        """Ten muc phai tim duoc, du no khong lap lai trong than muc.

        Da troi that: `tsv` sinh tu `content`, ma dong tieu de thi da bi tach sang
        cot `section` tu luc cat chunk — nen "nghi phep nam" khong khop MOT tu nao.
        Migration 0008 doi sang sinh tsv tu `embed_input`.
        """
        hits = await lexical_search(SCOPE, "nghi phep nam", limit=5)
        assert any("phep nam" in h.content.lower() for h in hits)

    async def test_lexical_khop_du_cau_hoi_KHONG_DAU(self, tai_lieu_da_nap: str) -> None:
        """Postgres khong co dictionary tieng Viet. vn_tsv() bo dau ca hai phia —
        thieu buoc do thi "nghi phep" khong khop "nghỉ phép".
        """
        co_dau = await lexical_search(SCOPE, "nghỉ phép", limit=5)
        khong_dau = await lexical_search(SCOPE, "nghi phep", limit=5)
        assert co_dau and khong_dau
        assert {h.chunk_id for h in co_dau} == {h.chunk_id for h in khong_dau}


class TestDuongTimDayDu:
    """Duong day du co nhanh vector, nen ca nhom nay can embedding THAT."""

    async def test_tra_ve_chunk_dung_kem_nguon(
        self, tai_lieu_da_nap: str, embedding_that: None
    ) -> None:
        """Kiem THANH VIEN chu khong kiem hang nhat.

        CSDL that co nhieu tai lieu, va test chay tren cung mot CSDL do. Bat tai
        lieu cua rieng test nay phai dung dau bang la buoc no phai thang moi tai
        lieu khac mot ngay nao do se duoc nap vao — mot test se do vi mot ly do
        khong lien quan gi toi cai no dinh kiem.
        """
        hits = await knowledge.search(SCOPE, "hoan tien trong bao lau", 5)
        cua_ta = [h for h in hits if h.doc_title == tai_lieu_da_nap]
        assert cua_ta, [h.doc_title for h in hits]
        assert "7 ngay" in cua_ta[0].content

    async def test_cau_hoi_khong_lien_quan_KHONG_tra_ve_tai_lieu_nay(
        self, tai_lieu_da_nap: str, embedding_that: None
    ) -> None:
        """Rong = "khong tim thay trong tai lieu", va do la cai cho phep bot noi
        thang thay vi lay kien thuc chung ra thay the.
        """
        hits = await knowledge.search(SCOPE, "gia bitcoin hom nay bao nhieu", 5)
        assert [h for h in hits if h.doc_title == tai_lieu_da_nap] == []

    async def test_cau_hoi_rong_khong_goi_gi_ca(
        self, tai_lieu_da_nap: str, embedding_that: None
    ) -> None:
        assert await knowledge.search(SCOPE, "   ", 3) == []

    async def test_trich_dan_khong_lap_ten_tai_lieu(
        self, tai_lieu_da_nap: str, embedding_that: None
    ) -> None:
        hits = await knowledge.search(SCOPE, "hoan tien trong bao lau", 5)
        cua_ta = [h for h in hits if h.doc_title == tai_lieu_da_nap]
        assert cua_ta
        assert cua_ta[0].section is not None
        assert not cua_ta[0].section.startswith(tai_lieu_da_nap)
