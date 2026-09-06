"""TEST BAT BUOC — khong duoc phep xoa.

Master plan xep ro ri cross-group la "xac suat thap, hau qua nghiem trong".
Xac suat thap LA NHO co test nay. Bo test thi xac suat khong con thap nua.

Bo test nay di qua BE MAT CONG KHAI cua MemoryPort, khong goi thang repository:
mot lo ro ri co the nam o tang uy quyen chu khong o cau SQL. Rieng test cuoi cung
kiem tren CHUOI PROMPT DA BUILD, vi ro ri co the xay ra o builder trong khi
repository van sach.

Can Postgres that: mot cau SQL thieu `thread_id` chi lo ra khi co du lieu cua thread
khac nam ben canh. Fake khong bao gio bat duoc loai loi nay.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from agents.domain.message import StoredMessage
from agents.domain.thread import ThreadScope, user_subject
from agents.ports.memory import NewMessage
from agents.prompt.context import ContextInput, build_context
from config import get_settings
from infra.db import execute, fetch
from memory.repository import fact_repo
from memory.repository.message_repo import message_repo
from memory.repository.summary_repo import commit_summary

BI_MAT = "Nam làm ở công ty tuyệt mật Hoshi"
NAM = user_subject("nam")
LAN = user_subject("lan")


class GhiLog:
    """LoggerPort toi thieu — build_context can mot cai."""

    def debug(self, event: str, **kw: object) -> None: ...
    def info(self, event: str, **kw: object) -> None: ...
    def warning(self, event: str, **kw: object) -> None: ...
    def error(self, event: str, **kw: object) -> None: ...
    def bind(self, **kw: object) -> "GhiLog":
        return self


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
async def hai_thread(san_sang: None) -> AsyncIterator[tuple[ThreadScope, ThreadScope]]:
    """Thread A co du lieu nhay cam. Thread B phai KHONG thay gi cua A."""
    a = ThreadScope(platform="cli", thread_id=f"sec-a-{uuid.uuid4()}")
    b = ThreadScope(platform="cli", thread_id=f"sec-b-{uuid.uuid4()}")
    yield a, b
    for scope in (a, b):
        for table in ("memory_fact", "inbound_message", "thread_summary"):
            await execute(
                f"DELETE FROM {table} WHERE platform = $1 AND thread_id = $2",
                scope.platform,
                scope.thread_id,
            )


async def nap_thread_A(a: ThreadScope) -> None:
    """Do day thread A bang du lieu nhay cam o ca ba tang L1, L2, L3."""
    await message_repo.append(
        a,
        NewMessage(
            message_id=f"m-{uuid.uuid4()}",
            sender_id="nam",
            sender_name="Nam",
            text=BI_MAT,
            is_group=True,
            from_bot=False,
        ),
    )
    await commit_summary(a, f"Tóm tắt: {BI_MAT}", [f"khong-ton-tai-{uuid.uuid4()}"], None)
    await message_repo.remember(a, fact_repo.new_fact(NAM, BI_MAT, created_by="nam"))


class TestKhongRoRiGiuaCacThread:
    async def test_moi_phuong_thuc_public_goi_tu_B_deu_rong(
        self, hai_thread: tuple[ThreadScope, ThreadScope]
    ) -> None:
        """Khong tru phuong thuc nao. Them mot phuong thuc vao MemoryPort thi phai
        them mot dong o day — do la muc dich cua test nay.
        """
        a, b = hai_thread
        await nap_thread_A(a)

        assert await message_repo.recent(b, 50) == []
        assert await message_repo.summary(b) is None
        assert await message_repo.facts(b, NAM, BI_MAT) == []
        assert await message_repo.list_facts(b, NAM) == []
        assert await message_repo.forget(b, "nam", BI_MAT) == []

    async def test_recent_cua_B_khong_chua_tin_cua_A(
        self, hai_thread: tuple[ThreadScope, ThreadScope]
    ) -> None:
        a, b = hai_thread
        await nap_thread_A(a)
        # B co tin cua chinh no — de chac chan la loc dung, khong phai rong vi trong.
        await message_repo.append(
            b,
            NewMessage(
                message_id=f"m-{uuid.uuid4()}",
                sender_id="lan",
                sender_name="Lan",
                text="chào cả nhà",
                is_group=True,
                from_bot=False,
            ),
        )

        texts = [m.text for m in await message_repo.recent(b, 50)]

        assert texts == ["chào cả nhà"]
        assert BI_MAT not in texts

    async def test_summary_cua_B_khong_chua_noi_dung_cua_A(
        self, hai_thread: tuple[ThreadScope, ThreadScope]
    ) -> None:
        a, b = hai_thread
        await nap_thread_A(a)

        assert await message_repo.summary(b) is None
        # ...va cua A thi van con, de biet la du lieu that su da duoc ghi.
        summary_a = await message_repo.summary(a)
        assert summary_a is not None and BI_MAT in summary_a

    async def test_facts_cua_B_rong_du_query_TRUNG_Y_HET(
        self, hai_thread: tuple[ThreadScope, ThreadScope]
    ) -> None:
        """Truy van theo y nghia la duong de ro ri nhat: khong loc theo thread thi
        vector search se vui ve tra ve fact giong nhat trong CA BANG.
        """
        a, b = hai_thread
        await nap_thread_A(a)

        assert await message_repo.facts(b, NAM, BI_MAT) == []
        assert len(await message_repo.facts(a, NAM, BI_MAT)) == 1

    async def test_list_facts_cua_B_khong_liet_ke_fact_cua_A(
        self, hai_thread: tuple[ThreadScope, ThreadScope]
    ) -> None:
        a, b = hai_thread
        await nap_thread_A(a)

        assert await message_repo.list_facts(b, NAM) == []
        assert await fact_repo.dump_thread(b) == []

    async def test_fact_da_REVOKE_khong_vao_CHUOI_PROMPT_CUOI_CUNG(
        self, hai_thread: tuple[ThreadScope, ThreadScope]
    ) -> None:
        """Kiem tren chuoi DA BUILD, khong phai tren ket qua repository.

        Ro ri co the xay ra o builder trong khi repository van sach — vi du builder
        cache lai fact cua luot truoc, hoac render tu mot danh sach lay tu cho khac.
        """
        a, _ = hai_thread
        await nap_thread_A(a)
        facts = await message_repo.list_facts(a, NAM)
        assert len(facts) == 1

        await fact_repo.revoke(a, [facts[0].id], revoked_by="nam")

        con_lai = await message_repo.facts(a, NAM, BI_MAT)
        envelope = build_context(
            ContextInput(
                question="Nam làm ở đâu?",
                is_group=True,
                facts=tuple(con_lai),
                recent=(
                    StoredMessage(
                        sender_id="lan",
                        sender_name="Lan",
                        text="ai biết không",
                        created_at=datetime.now(UTC),
                        from_bot=False,
                    ),
                ),
            ),
            GhiLog(),
        )

        toan_bo_prompt = envelope.system + "".join(m.content for m in envelope.messages)
        assert BI_MAT not in toan_bo_prompt

    async def test_nguoi_dung_X_khong_revoke_duoc_fact_cua_nguoi_dung_Y(
        self, hai_thread: tuple[ThreadScope, ThreadScope]
    ) -> None:
        """`forget` nhan actor_id va tu suy ra subject — khong nhan subject tu ngoai.

        Nho vay mot nguoi go dung nguyen van fact cua nguoi khac van khong dung toi
        duoc no.
        """
        a, _ = hai_thread
        await message_repo.remember(a, fact_repo.new_fact(LAN, "Lan làm giao diện", "lan"))

        # Nam go dung y het fact cua Lan.
        assert await message_repo.forget(a, "nam", "Lan làm giao diện") == []

        # Va fact cua Lan van con nguyen.
        assert len(await message_repo.list_facts(a, LAN)) == 1
