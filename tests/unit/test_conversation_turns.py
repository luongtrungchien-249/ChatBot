"""Lich su hoi thoai phai la LUOT THAT, khong phai mot khoi van ban nen.

Bo test nay khoa lai ban sua cho mot lo hong da do duoc tren bot that: bon luot lien
tiep trong nhom Zalo, khong mot lan goi cong cu, khong mot cau tra loi. Nguoi dung
hoi "tim Top 5 bai bao AI moi nhat", bot hoi lai; dap "arXiv", bot hoi lai; "AI", bot
hoi lai; "Tim va tom tat cac bai bao do", bot van hoi lai.

Nguyen nhan nam o hinh dang cua mang `messages`. Ban cu nen ca lich su vao MOT user
message boc trong <hoi_thoai_gan_day>, roi chen mot luot assistant GIA — "Minh da doc
phan thong tin nen. Ban hoi gi?" — ngay truoc cau hoi. Nen luot assistant gan cau hoi
nhat khong bao gio la cau bot vua noi. Nguoi dung dap mot tu, va tu vi tri cua model
thi do la mot cuoc hoi thoai vua bat dau bang dung mot tu.

Khong I/O: dung cai gia cho LoggerPort, khong cham model.
"""

from datetime import UTC, datetime, timedelta

from agents.domain.message import StoredMessage
from agents.ports.llm import AssistantMessage, UserMessage
from agents.ports.memory import Fact
from agents.prompt.context import ContextInput, build_context, conversation_turns

from .fakes import FakeLogger

MOC = datetime(2026, 9, 7, 10, 0, tzinfo=UTC)


def tin(name: str, text: str, from_bot: bool, phut: int = 0) -> StoredMessage:
    return StoredMessage(
        sender_id="bot" if from_bot else "u1",
        sender_name=name,
        text=text,
        created_at=MOC + timedelta(minutes=phut),
        from_bot=from_bot,
    )


#: Dung doan hoi thoai da lam bot ket: bot hoi lai, nguoi dung dap MOT TU.
VONG_HOI_LAI = (
    tin("Nam", "@Bot CP Assistant Tôi cần tìm Top 5 bài báo AI mới nhất", False, 0),
    tin("CP_Assistant", "Bạn muốn preprint arXiv hay bài đã xuất bản?", True, 1),
    tin("Nam", "@Bot CP Assistant arXiv", False, 2),
)


class TestHinhDangLuot:
    async def test_tin_cua_bot_thanh_luot_ASSISTANT(self) -> None:
        turns = conversation_turns(VONG_HOI_LAI, is_group=True, logger=FakeLogger())
        assert any(isinstance(t, AssistantMessage) for t in turns)

    async def test_luot_NGAY_TRUOC_cau_hoi_la_cau_BOT_vua_noi(self) -> None:
        """Day chinh la ca da hong.

        Ban cu: luot cuoi luon la dong gia "Minh da doc phan thong tin nen. Ban hoi
        gi?" — mot loi moi mo cuoc hoi thoai moi, dat ngay truoc cau tra loi mot tu
        cua nguoi dung.
        """
        env = build_context(
            ContextInput(question="AI", is_group=True, recent=VONG_HOI_LAI), FakeLogger()
        )

        # [-1] la cau hoi hien tai; [-2] phai la cau BOT vua noi.
        assert isinstance(env.messages[-1], UserMessage)
        truoc_do = env.messages[-2]
        assert isinstance(truoc_do, AssistantMessage)
        assert truoc_do.content == "Bạn muốn preprint arXiv hay bài đã xuất bản?"

    async def test_KHONG_con_dong_gia_moi_hoi_lai(self) -> None:
        env = build_context(
            ContextInput(question="AI", is_group=True, recent=VONG_HOI_LAI), FakeLogger()
        )
        assert not any("Bạn hỏi gì" in m.content for m in env.messages)

    async def test_KHONG_boc_lich_su_trong_the_du_lieu(self) -> None:
        """`<hoi_thoai_gan_day>` la mot cai the, va RULES day model rang noi dung
        trong the la DU LIEU THAM KHAO chu khong phai chi thi. Boc lich su vao do la
        tu ha cap chinh cuoc hoi thoai xuong thanh tai lieu.
        """
        env = build_context(
            ContextInput(question="AI", is_group=True, recent=VONG_HOI_LAI), FakeLogger()
        )
        assert not any("<hoi_thoai_gan_day>" in m.content for m in env.messages)


class TestKhongLapCauHoi:
    async def test_bo_tin_cuoi_cua_nguoi_dung(self) -> None:
        """Stage 6 (persist) chay TRUOC stage 10 (recall), nen cau dang duoc tra loi
        da nam trong `recent`. De lai la hoi doi cau hoi.
        """
        turns = conversation_turns(VONG_HOI_LAI, is_group=False, logger=FakeLogger())

        assert len(turns) == 2
        # Tin cuoi cua NGUOI DUNG bien mat. (Cau hoi cua bot van chua chu "arXiv" —
        # kiem theo LUOT chu khong theo tu, neu khong test bat nham cho.)
        assert not any(
            isinstance(t, UserMessage) and t.content.strip().endswith("arXiv") for t in turns
        )

    async def test_cau_hoi_hien_tai_chi_xuat_hien_MOT_lan(self) -> None:
        env = build_context(
            ContextInput(question="arXiv", is_group=False, recent=VONG_HOI_LAI), FakeLogger()
        )
        assert sum(1 for m in env.messages if m.content.strip() == "arXiv") == 1

    async def test_lich_su_toan_tin_bot_thi_giu_nguyen(self) -> None:
        chi_bot = (tin("CP_Assistant", "Chào bạn.", True),)
        assert len(conversation_turns(chi_bot, is_group=False, logger=FakeLogger())) == 1


class TestTenNguoiGui:
    async def test_trong_NHOM_thi_giu_ten(self) -> None:
        """Nhieu nguoi noi cung luc: khong co ten thi model khong biet ai hoi gi."""
        turns = conversation_turns(VONG_HOI_LAI, is_group=True, logger=FakeLogger())
        assert turns[0].content.startswith("[Nam]: ")

    async def test_hoi_thoai_1_1_thi_KHONG_them_ten(self) -> None:
        turns = conversation_turns(VONG_HOI_LAI, is_group=False, logger=FakeLogger())
        assert not turns[0].content.startswith("[")

    async def test_luot_cua_bot_khong_bao_gio_co_tien_to_ten(self) -> None:
        """Tien to `[Ten]:` tren luot assistant se day model bat chuoc no trong cau
        tra loi — va nguoi dung se thay bot tu goi ten minh o dau moi tin.
        """
        turns = conversation_turns(VONG_HOI_LAI, is_group=True, logger=FakeLogger())
        bot = [t for t in turns if isinstance(t, AssistantMessage)]
        assert bot and not any(t.content.startswith("[") for t in bot)


class TestTranVaThuTu:
    async def test_giu_dung_thu_tu_thoi_gian(self) -> None:
        turns = conversation_turns(VONG_HOI_LAI, is_group=False, logger=FakeLogger())
        assert turns[0].content.endswith("Top 5 bài báo AI mới nhất")
        assert isinstance(turns[1], AssistantMessage)

    async def test_vuot_tran_thi_bo_luot_CU_NHAT(self) -> None:
        """Cat tu dau chu khong cat giua mot tin: mot luot bi cut nua chung con kho
        hieu hon la khong co no.
        """
        dai = "x" * 30_000
        recent = (
            *(tin("Nam", f"{dai} {i}", i % 2 == 1, i) for i in range(10)),
            tin("Nam", "câu hỏi mới", False, 99),
        )

        turns = conversation_turns(recent, is_group=False, logger=FakeLogger())

        assert 0 < len(turns) < 10
        # Luot con lai phai la nhung luot MOI nhat.
        assert turns[-1].content.endswith("9")

    async def test_lich_su_rong_thi_khong_co_luot_nao(self) -> None:
        assert conversation_turns((), is_group=False, logger=FakeLogger()) == ()

    async def test_khong_co_lich_su_thi_chi_con_cau_hoi(self) -> None:
        env = build_context(ContextInput(question="xin chào", is_group=False), FakeLogger())
        assert len(env.messages) == 1
        assert env.messages[0].content == "xin chào"


class TestNenVanLaNen:
    """Tai lieu, ghi nho va tom tat THAT SU la du lieu tham khao — chung o lai trong
    khoi rieng. Chi lich su hoi thoai duoc nang len thanh luot that.
    """

    async def test_ghi_nho_van_nam_trong_the(self) -> None:
        fact = Fact(
            id="1",
            subject_id="user:u1",
            content="Nam làm backend",
            source="explicit",
            confidence=1.0,
            created_at=MOC,
        )
        env = build_context(
            ContextInput(question="mình làm gì?", is_group=False, facts=(fact,)), FakeLogger()
        )
        assert "<ghi_nho>" in env.messages[0].content

    async def test_tom_tat_van_nam_trong_the(self) -> None:
        env = build_context(
            ContextInput(question="hôm qua chốt gì?", is_group=False, summary="Đã chốt A."),
            FakeLogger(),
        )
        assert "<tom_tat_truoc_do>" in env.messages[0].content

    async def test_co_nen_thi_van_co_mot_luot_assistant_ngan_cach(self) -> None:
        env = build_context(
            ContextInput(question="hỏi", is_group=False, summary="Đã chốt A."), FakeLogger()
        )
        assert isinstance(env.messages[1], AssistantMessage)
        # Nhung no KHONG duoc moi nguoi dung hoi lai — do la cho da gay ra vong lap.
        assert "hỏi gì" not in env.messages[1].content
