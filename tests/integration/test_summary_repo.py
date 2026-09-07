"""L2 tren POSTGRES THAT.

Rui ro that su cua L2 khong phai chat luong ban tom tat — no la MAT DU LIEU o buoc
commit. Ma buoc do la mot transaction, tuc la thu khong test gia duoc: fake nao cung
"thanh cong" ca hai lenh.

Tu bo qua khi khong co Postgres, co neu ly do.

Chay: docker compose -f ops/docker-compose.yml up -d postgres && uv run pytest tests/integration
"""

import uuid
from collections.abc import AsyncIterator

import pytest

from agents.domain.thread import ThreadScope
from infra.db import execute
from memory.repository.summary_repo import (
    Summary,
    commit_summary,
    count_pending,
    get_summary,
    oldest_pending,
)


@pytest.fixture
async def thread(postgres_san_sang: None) -> AsyncIterator[ThreadScope]:
    scope = ThreadScope(platform="cli", thread_id=f"it-{uuid.uuid4()}")
    yield scope
    # Don sach: cac test o day ghi vao bang that.
    await execute(
        "DELETE FROM inbound_message WHERE platform = $1 AND thread_id = $2",
        scope.platform,
        scope.thread_id,
    )
    await execute(
        "DELETE FROM thread_summary WHERE platform = $1 AND thread_id = $2",
        scope.platform,
        scope.thread_id,
    )


async def them_tin(scope: ThreadScope, n: int) -> list[str]:
    """n tin, thu tu thoi gian tang dan. Tra ve message_id theo dung thu tu do."""
    ids = []
    for i in range(n):
        message_id = f"m{i:03d}-{uuid.uuid4()}"
        ids.append(message_id)
        await execute(
            """INSERT INTO inbound_message
                 (platform, message_id, thread_id, sender_id, sender_name, text,
                  is_group, from_bot, created_at)
               VALUES ($1,$2,$3,'u1','Nam',$4,FALSE,FALSE, now() + ($5 || ' seconds')::interval)""",
            scope.platform,
            message_id,
            scope.thread_id,
            f"tin thu {i}",
            str(i),
        )
    return ids


class TestDemVaLay:
    async def test_dem_dung_so_tin_chua_nen(self, thread: ThreadScope) -> None:
        await them_tin(thread, 7)
        assert await count_pending(thread) == 7

    async def test_lay_dung_nhung_tin_CU_NHAT(self, thread: ThreadScope) -> None:
        ids = await them_tin(thread, 10)

        batch = await oldest_pending(thread, 4)

        assert [m.message_id for m in batch] == ids[:4]

    async def test_thread_khac_KHONG_lot_vao(self, thread: ThreadScope) -> None:
        # Hang rao chong ro ri: moi truy van deu kem ThreadScope.
        khac = ThreadScope(platform="cli", thread_id=f"it-{uuid.uuid4()}")
        await them_tin(khac, 5)
        try:
            assert await count_pending(thread) == 0
            assert await oldest_pending(thread, 10) == []
        finally:
            await execute(
                "DELETE FROM inbound_message WHERE platform = $1 AND thread_id = $2",
                khac.platform,
                khac.thread_id,
            )


class TestCommit:
    async def test_ghi_tom_tat_VA_danh_dau_cung_luc(self, thread: ThreadScope) -> None:
        ids = await them_tin(thread, 10)

        await commit_summary(thread, "nhóm chốt deadline 30/11", ids[:6], None)

        stored = await get_summary(thread)
        assert stored is not None
        assert stored.text == "nhóm chốt deadline 30/11"
        assert stored.msg_count == 6
        assert stored.gen_count == 1
        # Sau khi nen, dung 4 tin con lai chua nen.
        assert await count_pending(thread) == 4

    async def test_chi_danh_dau_DUNG_nhung_tin_da_nen(self, thread: ThreadScope) -> None:
        ids = await them_tin(thread, 10)

        await commit_summary(thread, "tóm tắt", ids[:6], None)

        con_lai = await oldest_pending(thread, 10)
        assert [m.message_id for m in con_lai] == ids[6:]

    async def test_nen_lan_hai_cong_don_dem_the_he(self, thread: ThreadScope) -> None:
        ids = await them_tin(thread, 10)
        await commit_summary(thread, "lần một", ids[:5], None)

        previous = await get_summary(thread)
        await commit_summary(thread, "lần hai", ids[5:], previous)

        stored = await get_summary(thread)
        assert stored == Summary(text="lần hai", msg_count=10, gen_count=2)

    async def test_danh_sach_rong_thi_KHONG_ghi_gi(self, thread: ThreadScope) -> None:
        """Ghi mot ban tom tat 0 tin se lam dem the he tang oan, va canh bao troi
        thong tin se keu nham vai luot sau.
        """
        await them_tin(thread, 3)

        await commit_summary(thread, "không nên gì cả", [], None)

        assert await get_summary(thread) is None
        assert await count_pending(thread) == 3

    async def test_khong_dung_toi_thread_khac(self, thread: ThreadScope) -> None:
        khac = ThreadScope(platform="cli", thread_id=f"it-{uuid.uuid4()}")
        ids_khac = await them_tin(khac, 4)
        ids = await them_tin(thread, 4)
        try:
            await commit_summary(thread, "tóm tắt", ids, None)

            assert await get_summary(khac) is None
            assert await count_pending(khac) == len(ids_khac)
        finally:
            await execute(
                "DELETE FROM inbound_message WHERE platform = $1 AND thread_id = $2",
                khac.platform,
                khac.thread_id,
            )
