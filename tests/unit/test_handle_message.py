"""Duong ong chay duoc HOAN TOAN khong can Postgres, Redis hay API key.

Do la ly do ton tai cua agents/ports — neu test nay bat dau can Docker thi mot rang
buoc kien truc da bi pha o dau do.
"""

from typing import Any

from agents.domain.errors import UpstreamError, UpstreamTimeout, is_retryable
from agents.pipeline.handle_message import (
    Deps,
    Failed,
    Handled,
    ReactLimits,
    ReplyModel,
    handle_message,
)
from agents.pipeline.stages.budget_guard import BUDGET_EXCEEDED_TEXT
from agents.pipeline.stages.generate import CONFIG_ERROR_TEXT, FALLBACK_TEXT
from agents.pipeline.stages.mention import help_text
from agents.policy.access import AccessRules
from agents.ports.llm import LlmResult, LlmUsage
from tho.sinh import SO_BAN

from .fakes import (
    FakeChannel,
    FakeLlm,
    FakeLogger,
    FakeMemory,
    FakeRateLimit,
    FakeTools,
    answer,
    make_msg,
)

BOT = "CP_Assistant,CP"


def make_deps(**over: Any) -> Deps:
    base: dict[str, Any] = {
        "llm": FakeLlm(replies=[answer("Deadline la ngay 30/11.")]),
        "memory": FakeMemory(),
        "channel": FakeChannel(),
        "rate_limit": FakeRateLimit(),
        "logger": FakeLogger(),
        "tools": FakeTools(definitions=()),
        "access_rules": AccessRules(
            group_policy="open", dm_policy="open", allowed_threads=frozenset()
        ),
        "bot_name": BOT,
        "reply": ReplyModel(max_tokens=16_000, effort="low"),
        "react": ReactLimits(max_iterations=5, deadline_ms=60_000),
    }
    base.update(over)
    return Deps(**base)


class TestDuongHanhPhuc:
    async def test_tra_loi_va_ghi_ca_cau_hoi_lan_cau_tra_loi(self) -> None:
        deps = make_deps()

        result = await handle_message(make_msg(), deps)

        assert result == Handled(replied=True)
        assert deps.channel.sent == ["Deadline la ngay 30/11."]  # type: ignore[attr-defined]
        # Thieu ban ghi from_bot thi L2 sau nay se nen mot doan doc thoai.
        appended = deps.memory.appended  # type: ignore[attr-defined]
        assert [(a.text, a.from_bot) for a in appended] == [
            ("deadline bao cao quy 3 la ngay nao", False),
            ("Deadline la ngay 30/11.", True),
        ]

    async def test_ten_nguoi_gui_la_ten_CHINH_khong_phai_ca_danh_sach(self) -> None:
        deps = make_deps()

        await handle_message(make_msg(), deps)

        bot_record = deps.memory.appended[1]  # type: ignore[attr-defined]
        assert bot_record.sender_name == "CP_Assistant"


class TestDungSom:
    async def test_thread_ngoai_allowlist_thi_IM_LANG(self) -> None:
        deps = make_deps(
            access_rules=AccessRules(
                group_policy="allowlist", dm_policy="allowlist", allowed_threads=frozenset()
            )
        )

        result = await handle_message(make_msg(), deps)

        assert result == Handled(replied=False)
        assert deps.channel.sent == []  # type: ignore[attr-defined]
        assert deps.llm.calls == []  # type: ignore[attr-defined]

    async def test_trong_nhom_khong_mention_thi_dung(self) -> None:
        deps = make_deps()

        result = await handle_message(
            make_msg("chao ca nha", is_group=True, mentioned_bot=False), deps
        )

        assert result == Handled(replied=False)
        assert deps.llm.calls == []  # type: ignore[attr-defined]

    async def test_mention_xong_rong_thi_tra_huong_dan_khong_goi_model(self) -> None:
        deps = make_deps()

        result = await handle_message(
            make_msg("@CP_Assistant", is_group=True, mentioned_bot=True), deps
        )

        assert result == Handled(replied=True)
        assert deps.channel.sent == [help_text(BOT)]  # type: ignore[attr-defined]
        assert deps.llm.calls == []  # type: ignore[attr-defined]

    async def test_het_ngan_sach_thi_tu_choi_TRUOC_khi_goi_model(self) -> None:
        deps = make_deps(rate_limit=FakeRateLimit(budget_ok=False))

        result = await handle_message(make_msg(), deps)

        assert result == Handled(replied=True)
        assert deps.channel.sent == [BUDGET_EXCEEDED_TEXT]  # type: ignore[attr-defined]
        assert deps.llm.calls == []  # type: ignore[attr-defined]

    async def test_budget_guard_chay_TRUOC_persist(self) -> None:
        deps = make_deps(rate_limit=FakeRateLimit(budget_ok=False))

        await handle_message(make_msg(), deps)

        # Het ngan sach thi khong duoc ghi tin nao.
        assert deps.memory.appended == []  # type: ignore[attr-defined]


class TestLoi:
    async def test_model_loi_gui_fallback_chu_KHONG_im_lang(self) -> None:
        deps = make_deps(llm=FakeLlm(error=Exception("connection timeout")))

        result = await handle_message(make_msg(), deps)

        assert deps.channel.sent == [FALLBACK_TEXT]  # type: ignore[attr-defined]
        assert isinstance(result, Failed)
        assert result.error == UpstreamTimeout(service="llm")

    async def test_api_key_sai_noi_that_KHONG_bao_thu_lai_sau(self) -> None:
        error = Exception("401 Incorrect API key provided")
        error.status = 401  # type: ignore[attr-defined]  # mo phong hinh dang loi cua SDK
        deps = make_deps(llm=FakeLlm(error=error))

        result = await handle_message(make_msg(), deps)

        # Bao "thu lai sau" cho mot khoa sai la noi doi: thu bao nhieu lan cung hong.
        assert deps.channel.sent == [CONFIG_ERROR_TEXT]  # type: ignore[attr-defined]
        assert isinstance(result, Failed)
        assert result.error == UpstreamError(service="llm", status=401)
        assert is_retryable(result.error) is False

    async def test_loi_5xx_bao_thu_lai_sau_va_DUOC_retry(self) -> None:
        error = Exception("503 service unavailable")
        error.status = 503  # type: ignore[attr-defined]
        deps = make_deps(llm=FakeLlm(error=error))

        result = await handle_message(make_msg(), deps)

        assert deps.channel.sent == [FALLBACK_TEXT]  # type: ignore[attr-defined]
        assert isinstance(result, Failed)
        assert is_retryable(result.error) is True

    async def test_model_tra_chuoi_rong_coi_la_loi_khong_gui_tin_rong(self) -> None:
        empty = LlmResult(
            text="   ",
            tool_calls=(),
            usage=LlmUsage(
                input_tokens=10, output_tokens=0, cache_read_tokens=0, cache_write_tokens=0
            ),
            finish_reason="stop",
        )
        deps = make_deps(llm=FakeLlm(replies=[empty]))

        result = await handle_message(make_msg(), deps)

        assert isinstance(result, Failed)
        assert deps.channel.sent == [FALLBACK_TEXT]  # type: ignore[attr-defined]

    async def test_ghi_tin_TRUOC_khi_goi_model(self) -> None:
        deps = make_deps(llm=FakeLlm(error=Exception("500 upstream")))

        await handle_message(make_msg(), deps)

        # Cau hoi phai con trong lich su du model hong.
        appended = deps.memory.appended  # type: ignore[attr-defined]
        assert [(a.text, a.from_bot) for a in appended] == [
            ("deadline bao cao quy 3 la ngay nao", False)
        ]


class TestTyping:
    async def test_typing_khong_duoc_chan_duong_phan_hoi(self) -> None:
        deps = make_deps(channel=FakeChannel(typing_hangs=True))

        result = await handle_message(make_msg(), deps)

        assert result == Handled(replied=True)
        assert len(deps.channel.sent) == 1  # type: ignore[attr-defined]

    async def test_typing_loi_khong_lam_hong_ca_luot(self) -> None:
        deps = make_deps(channel=FakeChannel(typing_error=Exception("kenh khong ho tro typing")))

        result = await handle_message(make_msg(), deps)

        assert result == Handled(replied=True)
        assert len(deps.channel.sent) == 1  # type: ignore[attr-defined]


class TestRetryVaCoDaTraLoi:
    """Cau fallback va co "da tra loi" phai khop nhau, neu khong retry thanh vo nghia.

    Ban truoc: moi that bai deu dat co `replied:`, nen lan retry vao worker gap co do
    va thoat ngay. `max_tries = 3` chua bao gio thu lai lan nao.
    """

    async def test_con_luot_retry_thi_KHONG_gui_gi(self) -> None:
        deps = make_deps(llm=FakeLlm(error=Exception("500 upstream")), is_final_attempt=False)

        result = await handle_message(make_msg(), deps)

        assert isinstance(result, Failed)
        assert is_retryable(result.error)
        # Chua gui gi -> worker khong dat co -> lan retry con chay lai duoc.
        assert result.replied is False
        assert deps.channel.sent == []  # type: ignore[attr-defined]

    async def test_lan_thu_cuoi_thi_gui_fallback(self) -> None:
        deps = make_deps(llm=FakeLlm(error=Exception("500 upstream")), is_final_attempt=True)

        result = await handle_message(make_msg(), deps)

        assert isinstance(result, Failed)
        assert result.replied is True
        assert deps.channel.sent == [FALLBACK_TEXT]  # type: ignore[attr-defined]

    async def test_loi_KHONG_retry_duoc_thi_tra_loi_ngay_du_con_luot(self) -> None:
        """Khoa API sai: thu lai ba lan van sai ba lan. Bat nguoi dung cho la vo ich."""

        class KhoaSaiError(Exception):
            status_code = 401

        deps = make_deps(llm=FakeLlm(error=KhoaSaiError("unauthorized")), is_final_attempt=False)

        result = await handle_message(make_msg(), deps)

        assert isinstance(result, Failed)
        assert not is_retryable(result.error)
        assert result.replied is True
        assert deps.channel.sent == [CONFIG_ERROR_TEXT]  # type: ignore[attr-defined]

    async def test_timeout_khong_retry_nen_van_tra_loi_ngay(self) -> None:
        deps = make_deps(llm=FakeLlm(error=Exception("connection timeout")), is_final_attempt=False)

        result = await handle_message(make_msg(), deps)

        assert isinstance(result, Failed)
        assert isinstance(result.error, UpstreamTimeout)
        assert deps.channel.sent == [FALLBACK_TEXT]  # type: ignore[attr-defined]


LUC_BAT_DUNG = (
    "Trâu ơi ta bảo trâu này\n"
    "Trâu ra ngoài ruộng trâu cày với ta\n"
    "Cấy cày vốn nghiệp nông gia\n"
    "Ta đây trâu đấy ai mà quản công"
)


class TestLamTho:
    """Stage 9b: yeu cau lam tho di DUONG RIENG, khong qua vong ReAct.

    Lam tho la bai toan NGUOC voi phan con lai cua bot. Luat he thong la "KHONG tra
    loi tu tri nho, moi cau hoi co du kien deu phai tra tai lieu TRUOC", va chan 7
    trong generate.py cuong che luat do. Mot bai tho khong co tai lieu nao de tra —
    de no di qua vong ReAct thi no kich hoat chan 7 va ton MOT LUOT GOI MODEL thua
    cho moi bai tho, dung luc tinh nang nay dat muc tieu giam do tre.
    """

    async def test_yeu_cau_lam_tho_tra_ve_BAI_THO(self) -> None:
        channel = FakeChannel()
        deps = make_deps(llm=FakeLlm(replies=[answer(LUC_BAT_DUNG)]), channel=channel)

        result = await handle_message(make_msg(text="làm cho mình bài lục bát về công cha"), deps)

        assert isinstance(result, Handled)
        assert channel.sent == [LUC_BAT_DUNG]

    async def test_KHONG_khai_cong_cu_nao_cho_luot_lam_tho(self) -> None:
        """Khai cong cu la mo duong cho model di tra tai lieu ve "mua thu" — vo nghia,
        va cong them do tre.
        """
        llm = FakeLlm(replies=[answer(LUC_BAT_DUNG)])
        deps = make_deps(llm=llm, tools=FakeTools())

        await handle_message(make_msg(text="viết giúp mình bài thơ lục bát"), deps)

        assert llm.calls[0]["tools"] == ()

    async def test_dung_prompt_RIENG_chu_khong_phai_SYSTEM_PROMPT(self) -> None:
        """Luot DAU la giai doan chon chu van; luot viet bai dung prompt tho rieng.

        Ca hai deu KHONG duoc dung SYSTEM_PROMPT chinh: tang `system` dang o
        12.948/12.960 ky tu, va luat tho chi phuc vu mot route.
        """
        llm = FakeLlm(replies=[answer(LUC_BAT_DUNG)])
        deps = make_deps(llm=llm)

        await handle_message(make_msg(text="làm bài lục bát về mùa thu"), deps)

        assert "LÀM THƠ LỤC BÁT" in llm.calls[0]["system"]

    async def test_bai_SAI_LUAT_thi_bot_sua_lai(self) -> None:
        """Chan cung bang CODE, khong phai cau chu trong prompt.

        Luot dau sinh `SO_BAN` ban SONG SONG. TAT CA deu sai khung thi moi sua mot
        vong — tong `SO_BAN + 1` luot goi, nhung DO TRE chi bang hai luot, vi cac ban
        dau chay cung luc.

        Bam vao hang so `SO_BAN` chu khong ghim con so: ban truoc test nay ghim "3" va
        no do ngay khi `SO_BAN` len 8, trong khi dieu no muon chung minh khong doi.

        Giai doan "chon chu van truoc" DA TAT mac dinh (do duoc: no keo tong tu
        69,7 xuong 57,1/100) — xem CHON_VAN_TRUOC trong tho/sinh.py.
        """
        sai = "Công cha như núi Thái Sơn cao" + chr(10) + "Nghĩa mẹ như nước trong nguồn chảy ra"
        # FakeLlm tra ve replies[min(len(calls) - 1, len(replies) - 1)]: moi ban dau
        # deu sai, luot sau do ra ban dung.
        llm = FakeLlm(replies=[answer(sai)] * SO_BAN + [answer(LUC_BAT_DUNG)])
        channel = FakeChannel()
        deps = make_deps(llm=llm, channel=channel)

        await handle_message(make_msg(text="làm bài lục bát"), deps)

        assert len(llm.calls) == SO_BAN + 1
        assert channel.sent == [LUC_BAT_DUNG]

    async def test_mot_trong_cac_ban_DUNG_thi_KHONG_ton_vong_sua(self) -> None:
        """Cho sinh song song an: chi can MOT ban dat la xong.

        So ban la `tho.sinh.SO_BAN`, nang 3 -> 4 ngay 11/09/2026 sau khi do duoc ti le
        mot ban dung KHUNG 6-8 la 65%. Cac ban chay song song nen ban thu tu khong cong
        do tre; test nay ghim rang co dung ban dat thi KHONG ton them vong sua nao.
        """
        sai = "Công cha như núi Thái Sơn cao" + chr(10) + "Nghĩa mẹ như nước trong nguồn chảy ra"
        llm = FakeLlm(replies=[answer(sai)] * (SO_BAN - 1) + [answer(LUC_BAT_DUNG)])
        channel = FakeChannel()
        deps = make_deps(llm=llm, channel=channel)

        await handle_message(make_msg(text="làm bài lục bát"), deps)

        assert len(llm.calls) == SO_BAN
        assert channel.sent == [LUC_BAT_DUNG]

    async def test_cau_hoi_THUONG_van_di_duong_cu(self) -> None:
        """Ca am quan trong nhat: nhan nham thi bot lam tho khi nguoi ta hoi quy dinh."""
        llm = FakeLlm(replies=[answer("Deadline la 30/11.")])
        deps = make_deps(llm=llm)

        await handle_message(make_msg(text="deadline bao cao quy 3 la ngay nao"), deps)

        assert "LÀM THƠ" not in llm.calls[0]["system"]
        assert deps.channel.sent == ["Deadline la 30/11."]  # type: ignore[attr-defined]
