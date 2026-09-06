"""L3 tren POSTGRES + EMBEDDING THAT.

Ba thu khong test gia duoc, va ca ba deu la cho hong nang:
  - pgvector: cot VECTOR(1024), toan tu `<=>`, index HNSW.
  - Chong trung: can vector THAT de "cung y" va "khac y" tach duoc nhau.
  - Hang rao thread: mot cau SQL thieu `thread_id` chi lo ra khi co du lieu that
    cua thread khac nam ben canh.

Tu bo qua khi khong co Postgres hoac khong co khoa OpenAI.

Chay: docker compose -f ops/docker-compose.yml up -d postgres && uv run pytest tests/integration
"""

import uuid
from collections.abc import AsyncIterator

import pytest

from agents.domain.thread import ThreadScope, user_subject
from config import get_settings
from infra.db import execute, fetch
from memory.repository import fact_repo

NAM = user_subject("nam")
LAN = user_subject("lan")


@pytest.fixture
async def san_sang() -> AsyncIterator[None]:
    if get_settings().EMBEDDING_PROVIDER.lower() != "openai":
        pytest.skip("EMBEDDING_PROVIDER khong phai 'openai' — embedder gia lam test vo nghia")
    try:
        await fetch("SELECT 1")
    except Exception as error:
        pytest.skip(f"khong co Postgres: {error}")
    yield


@pytest.fixture
async def thread(san_sang: None) -> AsyncIterator[ThreadScope]:
    scope = ThreadScope(platform="cli", thread_id=f"it-fact-{uuid.uuid4()}")
    yield scope
    await execute(
        "DELETE FROM memory_fact WHERE platform = $1 AND thread_id = $2",
        scope.platform,
        scope.thread_id,
    )


async def nho(scope: ThreadScope, subject: str, content: str) -> None:
    await fact_repo.remember(scope, fact_repo.new_fact(subject, content, created_by="nam"))


class TestGhiVaDoc:
    async def test_ghi_roi_doc_lai(self, thread: ThreadScope) -> None:
        await nho(thread, NAM, "Nam làm backend Node.js")

        facts = await fact_repo.list_facts(thread, NAM)

        assert [f.content for f in facts] == ["Nam làm backend Node.js"]
        assert facts[0].source == "explicit"
        assert facts[0].confidence == 1.0

    async def test_hai_fact_KHAC_nhau_ve_cung_mot_nguoi_thi_giu_ca_hai(
        self, thread: ThreadScope
    ) -> None:
        # Day la ca de mat du lieu nhat neu nguong chong trung dat qua thap.
        await nho(thread, NAM, "Nam làm backend Node.js")
        await nho(thread, NAM, "Nam học đại học Bách khoa")

        facts = await fact_repo.list_facts(thread, NAM)
        assert len(facts) == 2

    async def test_cung_mot_y_khac_cach_noi_thi_THAY_THE_chu_khong_cong_don(
        self, thread: ThreadScope
    ) -> None:
        await nho(thread, NAM, "Nam làm backend Node.js")
        await nho(thread, NAM, "Nam phụ trách phần backend")

        facts = await fact_repo.list_facts(thread, NAM)
        assert len(facts) == 1
        assert facts[0].content == "Nam phụ trách phần backend"

    async def test_y_MAU_THUAN_thi_ban_moi_thang(self, thread: ThreadScope) -> None:
        await nho(thread, NAM, "Nam làm ở công ty A")
        await nho(thread, NAM, "Nam làm ở công ty B")

        facts = await fact_repo.list_facts(thread, NAM)
        assert [f.content for f in facts] == ["Nam làm ở công ty B"]

    async def test_chep_y_HET_thi_bo_qua_khong_tao_ban_moi(self, thread: ThreadScope) -> None:
        await nho(thread, NAM, "Nam làm backend Node.js")
        await nho(thread, NAM, "  nam LÀM backend node.js  ")

        facts = await fact_repo.list_facts(thread, NAM)
        assert len(facts) == 1
        # Giu NGUYEN VAN ban dau, khong bi ban chep de len.
        assert facts[0].content == "Nam làm backend Node.js"


class TestTimTheoYNghia:
    async def test_tra_ve_fact_lien_quan_nhat_truoc(self, thread: ThreadScope) -> None:
        await nho(thread, NAM, "Nam làm backend Node.js")
        await nho(thread, NAM, "Nam học đại học Bách khoa")
        await nho(thread, NAM, "Nam thích uống cà phê đen")

        facts = await fact_repo.search_facts(thread, NAM, "Nam làm nghề gì", k=1)

        assert len(facts) == 1
        assert "backend" in facts[0].content

    async def test_query_rong_thi_tra_ve_tat_ca(self, thread: ThreadScope) -> None:
        await nho(thread, NAM, "Nam làm backend Node.js")
        await nho(thread, NAM, "Nam học đại học Bách khoa")

        assert len(await fact_repo.search_facts(thread, NAM, "   ")) == 2


class TestHangRaoThread:
    async def test_thread_khac_KHONG_thay_gi(self, thread: ThreadScope) -> None:
        khac = ThreadScope(platform="cli", thread_id=f"it-fact-{uuid.uuid4()}")
        await nho(khac, NAM, "Nam làm ở công ty bí mật")
        try:
            assert await fact_repo.list_facts(thread, NAM) == []
            assert await fact_repo.search_facts(thread, NAM, "công ty") == []
            assert await fact_repo.dump_thread(thread) == []
        finally:
            await execute(
                "DELETE FROM memory_fact WHERE platform = $1 AND thread_id = $2",
                khac.platform,
                khac.thread_id,
            )

    async def test_subject_khac_KHONG_thay_gi(self, thread: ThreadScope) -> None:
        await nho(thread, NAM, "Nam làm backend Node.js")

        assert await fact_repo.list_facts(thread, LAN) == []
        assert await fact_repo.search_facts(thread, LAN, "backend") == []

    async def test_dump_thread_thay_MOI_subject_cua_dung_thread_do(
        self, thread: ThreadScope
    ) -> None:
        # Cong cu audit: phai thay het, nhung chi trong pham vi mot thread.
        await nho(thread, NAM, "Nam làm backend Node.js")
        await nho(thread, LAN, "Lan làm giao diện")

        subjects = {f.subject_id for f in await fact_repo.dump_thread(thread)}
        assert subjects == {NAM, LAN}


class TestQuen:
    async def test_liet_ke_ung_vien_theo_cach_NGUOI_DUNG_noi(self, thread: ThreadScope) -> None:
        await nho(thread, NAM, "Nam làm ở công ty A")
        await nho(thread, NAM, "Nam thích uống cà phê đen")

        matched = await fact_repo.match_for_forget(thread, NAM, "chỗ làm của tôi")

        assert [f.content for f in matched][:1] == ["Nam làm ở công ty A"]

    async def test_liet_ke_KHONG_xoa_gi(self, thread: ThreadScope) -> None:
        # Buoc xac nhan la lop chan that su. Neu ham nay tu xoa thi buoc do vo nghia.
        await nho(thread, NAM, "Nam làm ở công ty A")

        await fact_repo.match_for_forget(thread, NAM, "chỗ làm")

        assert len(await fact_repo.list_facts(thread, NAM)) == 1

    async def test_revoke_thi_khong_con_thay_nua(self, thread: ThreadScope) -> None:
        await nho(thread, NAM, "Nam làm ở công ty A")
        facts = await fact_repo.list_facts(thread, NAM)

        assert await fact_repo.revoke(thread, [facts[0].id], revoked_by="nam") == 1

        assert await fact_repo.list_facts(thread, NAM) == []
        assert await fact_repo.search_facts(thread, NAM, "công ty") == []

    async def test_revoke_hai_lan_khong_dem_lan_thu_hai(self, thread: ThreadScope) -> None:
        await nho(thread, NAM, "Nam làm ở công ty A")
        facts = await fact_repo.list_facts(thread, NAM)

        await fact_repo.revoke(thread, [facts[0].id], revoked_by="nam")
        assert await fact_repo.revoke(thread, [facts[0].id], revoked_by="nam") == 0

    async def test_quen_het_chi_dung_toi_subject_cua_MINH(self, thread: ThreadScope) -> None:
        await nho(thread, NAM, "Nam làm backend Node.js")
        await nho(thread, LAN, "Lan làm giao diện")

        await fact_repo.revoke_all(thread, NAM, revoked_by="nam")

        assert await fact_repo.list_facts(thread, NAM) == []
        assert len(await fact_repo.list_facts(thread, LAN)) == 1

    async def test_KHONG_revoke_duoc_fact_o_thread_khac(self, thread: ThreadScope) -> None:
        khac = ThreadScope(platform="cli", thread_id=f"it-fact-{uuid.uuid4()}")
        await nho(khac, NAM, "Nam làm ở công ty bí mật")
        of_khac = await fact_repo.list_facts(khac, NAM)
        try:
            # Doan dung id nhung dung SAI thread: phai khong dung duoc gi.
            assert await fact_repo.revoke(thread, [of_khac[0].id], revoked_by="ke-xau") == 0
            assert len(await fact_repo.list_facts(khac, NAM)) == 1
        finally:
            await execute(
                "DELETE FROM memory_fact WHERE platform = $1 AND thread_id = $2",
                khac.platform,
                khac.thread_id,
            )
