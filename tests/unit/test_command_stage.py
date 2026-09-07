"""Stage 3 — lenh quan tri memory.

Day la stage co quyen XOA du lieu cua nguoi dung, nen phan lon test o day noi ve
hai dieu: khong xoa nham cua nguoi khac, va khong xoa khi chua duoc xac nhan.
"""

from datetime import UTC, datetime
from typing import Any

from agents.domain.thread import ThreadScope, user_subject
from agents.pipeline.handle_message import Handled, handle_message
from agents.pipeline.stages.command import (
    HELP_TEXT,
    NOTHING_MATCHED,
    NOTHING_PENDING,
    NOTHING_REMEMBERED,
    Answer,
    AskConfirm,
    DeferredWrite,
    NotACommand,
    handle_command,
)
from agents.ports.memory import Fact

from .fakes import FakeMemory, make_msg
from .test_handle_message import make_deps

SCOPE = ThreadScope(platform="cli", thread_id="t1")


def fact(content: str, fact_id: str = "1") -> Fact:
    return Fact(
        id=fact_id,
        subject_id=user_subject("u1"),
        content=content,
        source="explicit",
        confidence=1.0,
        created_at=datetime.now(UTC),
    )


class TestNhanDienLenh:
    async def test_cau_hoi_thuong_di_tiep_xuong_duong_ong(self) -> None:
        outcome = await handle_command("deadline là ngày nào", FakeMemory(), SCOPE, "u1")
        assert isinstance(outcome, NotACommand)

    async def test_help(self) -> None:
        assert await handle_command("help", FakeMemory(), SCOPE, "u1") == Answer(text=HELP_TEXT)


class TestXemMemory:
    async def test_chua_nho_gi(self) -> None:
        outcome = await handle_command("memory", FakeMemory(), SCOPE, "u1")
        assert outcome == Answer(text=NOTHING_REMEMBERED)

    async def test_liet_ke_co_danh_so(self) -> None:
        memory = FakeMemory(stored_facts=[fact("Nam làm backend"), fact("Nam họp thứ 3", "2")])

        outcome = await handle_command("memory", memory, SCOPE, "u1")

        assert isinstance(outcome, Answer)
        assert "1. Nam làm backend" in outcome.text
        assert "2. Nam họp thứ 3" in outcome.text


class TestQuen:
    async def test_khong_khop_gi_thi_noi_thang(self) -> None:
        outcome = await handle_command("quên chỗ làm", FakeMemory(), SCOPE, "u1")
        assert outcome == Answer(text=NOTHING_MATCHED)

    async def test_co_khop_thi_HOI_chu_khong_xoa(self) -> None:
        memory = FakeMemory(forget_matches=[fact("Nam làm ở công ty A")])

        outcome = await handle_command("quên chỗ làm", memory, SCOPE, "u1")

        assert isinstance(outcome, AskConfirm)
        assert "Nam làm ở công ty A" in outcome.text
        assert "đồng ý" in outcome.text

    async def test_quen_het_liet_ke_TAT_CA_roi_hoi(self) -> None:
        memory = FakeMemory(stored_facts=[fact("một"), fact("hai", "2")])

        outcome = await handle_command("quên hết", memory, SCOPE, "u1")

        assert isinstance(outcome, AskConfirm)
        assert len(outcome.facts) == 2

    async def test_quen_het_khi_chua_co_gi(self) -> None:
        outcome = await handle_command("quên hết", FakeMemory(), SCOPE, "u1")
        assert outcome == Answer(text=NOTHING_REMEMBERED)


class TestXacNhan:
    async def test_khong_co_gi_dang_cho(self) -> None:
        outcome = await handle_command("đồng ý", FakeMemory(confirm_result=0), SCOPE, "u1")
        assert outcome == Answer(text=NOTHING_PENDING)

    async def test_co_yeu_cau_dang_cho_thi_bao_so_luong(self) -> None:
        outcome = await handle_command("đồng ý", FakeMemory(confirm_result=3), SCOPE, "u1")
        assert isinstance(outcome, Answer)
        assert "3" in outcome.text


class TestQuyen:
    async def test_subject_suy_ra_tu_SENDER_ID_khong_tu_van_ban(self) -> None:
        """Chan "nguoi X xoa fact cua nguoi Y".

        Nguoi go la u1. Du van ban co nhac ten ai, `list_facts` cung chi duoc goi
        voi subject cua u1.
        """
        seen: list[str] = []

        class Ghi(FakeMemory):
            async def list_facts(self, scope: ThreadScope, subject_id: str) -> list[Fact]:
                seen.append(subject_id)
                return []

        await handle_command("memory", Ghi(), SCOPE, "u1")

        assert seen == [user_subject("u1")]

    async def test_forget_nhan_actor_id_chu_khong_nhan_subject(self) -> None:
        seen: list[str] = []

        class Ghi(FakeMemory):
            async def forget(self, scope: ThreadScope, actor_id: str, pattern: str) -> list[Fact]:
                seen.append(actor_id)
                return []

        await handle_command("quên Lan làm giao diện", Ghi(), SCOPE, "u1")

        assert seen == ["u1"]


class TestTrongDuongOng:
    def _deps(self, **over: Any) -> Any:
        return make_deps(memory=FakeMemory(**over))

    async def test_lenh_KHONG_goi_model(self) -> None:
        deps = self._deps(stored_facts=[fact("Nam làm backend")])

        result = await handle_message(make_msg("memory"), deps)

        assert result == Handled(replied=True)
        assert deps.llm.calls == []

    async def test_lenh_chay_TRUOC_rate_limit(self) -> None:
        """Nguoi dung phai xoa duoc memory cua minh ngay ca khi dang bi rate limit."""
        from agents.ports.ratelimit import Denied

        from .fakes import FakeRateLimit

        deps = make_deps(
            memory=FakeMemory(stored_facts=[fact("Nam làm backend")]),
            rate_limit=FakeRateLimit(denied=Denied(retry_after_ms=5000, tier="user")),
        )

        result = await handle_message(make_msg("memory"), deps)

        assert result == Handled(replied=True)
        assert "Nam làm backend" in deps.channel.sent[0]  # type: ignore[attr-defined]

    async def test_hoi_xac_nhan_thi_GHI_yeu_cau_dang_cho_truoc_khi_hoi(self) -> None:
        deps = self._deps(forget_matches=[fact("Nam làm ở công ty A", "42")])

        await handle_message(make_msg("quên chỗ làm"), deps)

        assert deps.memory.staged == [("u1", ["42"])]

    async def test_lenh_KHONG_bi_ghi_vao_lich_su_hoi_thoai(self) -> None:
        # "quen het" ma nam trong lich su thi ban tom tat L2 sau nay se chua no,
        # va cau tra loi cua bot cung vay — nhieu ngu canh bang viec quan tri.
        deps = self._deps(stored_facts=[fact("Nam làm backend")])

        await handle_message(make_msg("memory"), deps)

        assert deps.memory.appended == []


class TestLenhGhiPhaiQuaChotChan:
    """`nho giup:` la lenh GHI, va duong ghi fact goi embedding that o moi lan.

    Doc va xoa chay som la co chu dich. Ghi thi khong: de chung o stage 3 nghia la
    mot nguoi go `nho giup:` lien tuc se tieu tien ma khong qua rate limit lan
    ngan sach ngay.
    """

    async def test_handle_command_KHONG_ghi_ngay_ma_hoan_lai(self) -> None:
        memory = FakeMemory()

        outcome = await handle_command("nhớ giúp: deadline 30/11", memory, SCOPE, "u1")

        assert isinstance(outcome, DeferredWrite)
        assert outcome.command.content == "deadline 30/11"
        assert memory.remembered == []

    async def test_qua_duoc_chot_chan_thi_ghi_that(self) -> None:
        deps = make_deps(memory=FakeMemory())

        result = await handle_message(make_msg("nhớ giúp: deadline 30/11"), deps)

        assert result == Handled(replied=True)
        assert [f.content for f in deps.memory.remembered] == ["deadline 30/11"]  # type: ignore[attr-defined]
        # Van la duong khong goi model.
        assert deps.llm.calls == []  # type: ignore[attr-defined]

    async def test_bi_rate_limit_thi_KHONG_ghi(self) -> None:
        from agents.pipeline.stages.ratelimit import RATE_LIMITED_TEXT
        from agents.ports.ratelimit import Denied

        from .fakes import FakeRateLimit

        deps = make_deps(
            memory=FakeMemory(),
            rate_limit=FakeRateLimit(denied=Denied(retry_after_ms=5000, tier="user")),
        )

        await handle_message(make_msg("nhớ giúp: deadline 30/11"), deps)

        assert deps.memory.remembered == []  # type: ignore[attr-defined]
        assert deps.channel.sent == [RATE_LIMITED_TEXT]  # type: ignore[attr-defined]

    async def test_het_ngan_sach_thi_KHONG_ghi(self) -> None:
        from .fakes import FakeRateLimit

        deps = make_deps(memory=FakeMemory(), rate_limit=FakeRateLimit(budget_ok=False))

        await handle_message(make_msg("nhớ giúp: deadline 30/11"), deps)

        assert deps.memory.remembered == []  # type: ignore[attr-defined]

    async def test_XOA_van_chay_khi_dang_bi_rate_limit(self) -> None:
        """Chieu nguoc lai phai giu nguyen: chan duong ghi khong duoc chan duong xoa."""
        from agents.ports.ratelimit import Denied

        from .fakes import FakeRateLimit

        deps = make_deps(
            memory=FakeMemory(forget_matches=[fact("Nam làm ở công ty A", "42")]),
            rate_limit=FakeRateLimit(denied=Denied(retry_after_ms=5000, tier="user")),
        )

        await handle_message(make_msg("quên chỗ làm"), deps)

        assert deps.memory.staged == [("u1", ["42"])]  # type: ignore[attr-defined]

    async def test_subject_suy_ra_tu_SENDER_ID_khi_ghi(self) -> None:
        deps = make_deps(memory=FakeMemory())

        await handle_message(make_msg("nhớ giúp: tôi tên Nam", sender_id="u9"), deps)

        assert deps.memory.remembered[0].subject_id == user_subject("u9")  # type: ignore[attr-defined]
        assert deps.memory.remembered[0].source == "explicit"  # type: ignore[attr-defined]
        assert deps.memory.remembered[0].confidence == 1.0  # type: ignore[attr-defined]
