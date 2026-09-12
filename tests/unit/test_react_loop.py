"""Vong ReAct la cho de bien thanh vong dot tien khong day.

Nam chan cung duoi day phai duoc CHUNG MINH, khong phai tin la co.
"""

from typing import Any

from agents.domain.thread import ThreadScope
from agents.pipeline.stages.generate import (
    NHAC_TRA_TAI_LIEU,
    GenerateDeps,
    ObservationEvent,
    ReactEvent,
    ToolCallEvent,
    generate,
)
from agents.ports.llm import CallContext, LlmResult, UserMessage
from agents.ports.tool import ToolDefinition, ToolRequirements
from agents.prompt.context import ContextEnvelope
from shared.result import Ok

from .fakes import FakeLlm, FakeLogger, FakeRateLimit, FakeTools, answer, wants_tools

CTX = CallContext(
    scope=ThreadScope(platform="web", thread_id="t1"), sender_id="u1", trace_id="tr1"
)
PROMPT = ContextEnvelope(system="SYS", messages=(UserMessage(content="hoi gi do"),))


def make_deps(replies: list[LlmResult], **over: Any) -> tuple[GenerateDeps, list[ReactEvent]]:
    events: list[ReactEvent] = []
    base: dict[str, Any] = {
        "llm": FakeLlm(replies=replies),
        "tools": FakeTools(),
        "rate_limit": FakeRateLimit(),
        "max_tokens": 16_000,
        "effort": "low",
        "max_iterations": 5,
        "deadline_ms": 60_000,
        "on_event": events.append,
    }
    base.update(over)
    return GenerateDeps(**base), events


class TestDuongHanhPhuc:
    async def test_khong_goi_cong_cu_thi_tra_loi_ngay(self) -> None:
        deps, _ = make_deps([answer("Deadline la 30/11.")])

        result = await generate(deps, PROMPT, CTX, FakeLogger())

        assert result == Ok("Deadline la 30/11.")
        assert len(deps.llm.calls) == 1  # type: ignore[attr-defined]
        assert deps.tools.batches == []  # type: ignore[attr-defined]

    async def test_goi_cong_cu_roi_tra_loi_ket_qua_vao_role_tool(self) -> None:
        deps, events = make_deps([wants_tools("web_search"), answer("Ha Noi 30 do.")])

        result = await generate(deps, PROMPT, CTX, FakeLogger())

        assert result == Ok("Ha Noi 30 do.")
        # Luot thu hai phai mang ca luot assistant co tool_calls lan luot tool.
        roles = [m.role for m in deps.llm.calls[1]["messages"]]  # type: ignore[attr-defined]
        assert roles == ["user", "assistant", "tool"]
        assert [e.type for e in events] == ["tool_call", "observation"]

    async def test_parallel_tool_calling_mot_lan_goi_hai_cong_cu(self) -> None:
        deps, events = make_deps([wants_tools("web_search", "paper_search"), answer("Xong.")])

        await generate(deps, PROMPT, CTX, FakeLogger())

        # MOT lan goi voi CA HAI — khong phai hai lan goi tuan tu.
        assert len(deps.tools.batches) == 1  # type: ignore[attr-defined]
        assert len(deps.tools.batches[0]) == 2  # type: ignore[attr-defined]
        # Ca hai ket qua vao CUNG mot luot tiep theo.
        tool_msgs = [m for m in deps.llm.calls[1]["messages"] if m.role == "tool"]  # type: ignore[attr-defined]
        assert len(tool_msgs) == 2

        call_event = next(e for e in events if isinstance(e, ToolCallEvent))
        assert call_event.tools == ("web_search", "paper_search")


class TestSauChanCung:
    async def test_chan_1_het_so_vong(self) -> None:
        deps, _ = make_deps([wants_tools("web_search")], max_iterations=3)

        result = await generate(deps, PROMPT, CTX, FakeLogger())

        assert len(deps.llm.calls) == 3  # type: ignore[attr-defined]
        # Vong cuoi KHONG duoc dua tool nua, de model buoc phai ket luan.
        assert deps.llm.calls[2]["tools"] == ()  # type: ignore[attr-defined]
        assert not isinstance(result, Ok)  # chua co van ban -> bao loi de gui fallback

    async def test_chan_1b_het_vong_nhung_da_co_van_ban(self) -> None:
        deps, _ = make_deps(
            [wants_tools("web_search", text="Minh tim duoc mot phan.")], max_iterations=2
        )

        result = await generate(deps, PROMPT, CTX, FakeLogger())

        assert isinstance(result, Ok)
        assert "Minh tim duoc mot phan." in result.value
        assert "chưa đầy đủ" in result.value

    async def test_chay_DU_moi_loi_goi_model_xin_khong_cat_bot(self) -> None:
        """Truoc day co tran TONG so loi goi cong cu, va no cat ngam.

        Khi cham tran giua mot vong, doan cat vut bot mot phan cac loi goi roi ghi
        vao lich su nhu the model chi xin bay nhieu — model khong biet minh bi cat
        nen van tra loi nhu da co du du lieu. Da gap that: hoi "top video nhieu
        like nhat", model xin tra 5 video mot luot, 3 cai duoc chay, cau tra loi
        noi ve ca 5.

        So vong + deadline + ngan sach ngay moi la thu chan that.
        """
        deps, _ = make_deps([wants_tools("web_search", "paper_search")], max_iterations=5)

        await generate(deps, PROMPT, CTX, FakeLogger())

        batches: list[tuple[object, ...]] = deps.tools.batches  # type: ignore[attr-defined]
        assert batches, "phai co it nhat mot lo duoc chay"
        for lo in batches:
            assert len(lo) == 2, "ca hai cong cu model xin deu phai duoc chay"

    async def test_chan_2_qua_deadline_thi_dung_ngay(self) -> None:
        # Deadline am = da het han san. Dat 1ms khong dung duoc: dong ho monotonic
        # tren Windows khong nhich du giua cac vong toan cai gia, nen vong lap chay
        # het max_iterations truoc khi deadline kip toi.
        deps, _ = make_deps([wants_tools("web_search")], deadline_ms=-1)

        result = await generate(deps, PROMPT, CTX, FakeLogger())

        assert deps.llm.calls == []  # type: ignore[attr-defined]
        assert not isinstance(result, Ok)

    async def test_chan_3_ngan_sach_kiem_tra_lai_moi_vong(self) -> None:
        rate_limit = FakeRateLimit()
        deps, _ = make_deps(
            [wants_tools("web_search"), wants_tools("web_search"), answer("Xong.")],
            rate_limit=rate_limit,
        )

        await generate(deps, PROMPT, CTX, FakeLogger())

        # Ba vong -> ba lan kiem tra. Mot lan o stage budget-guard la khong du.
        assert rate_limit.budget_calls == 3

    async def test_chan_3b_het_ngan_sach_giua_chung_thi_dung(self) -> None:
        rate_limit = FakeRateLimit(budget_sequence=[True, False])
        deps, _ = make_deps(
            [wants_tools("web_search", text="Mot phan ket qua.")], rate_limit=rate_limit
        )

        result = await generate(deps, PROMPT, CTX, FakeLogger())

        assert len(deps.llm.calls) == 1  # type: ignore[attr-defined]
        assert isinstance(result, Ok)
        assert "chưa đầy đủ" in result.value

    async def test_chan_5_nguoi_dung_bam_dung(self) -> None:
        calls = {"n": 0}

        async def should_stop() -> bool:
            calls["n"] += 1
            return calls["n"] > 1  # vong dau chay, vong sau dung

        deps, _ = make_deps(
            [wants_tools("web_search", text="Dang tim...")], should_stop=should_stop
        )

        result = await generate(deps, PROMPT, CTX, FakeLogger())

        assert len(deps.llm.calls) == 1  # type: ignore[attr-defined]
        assert isinstance(result, Ok)
        assert "chưa đầy đủ" in result.value


class TestLoi:
    async def test_cong_cu_that_bai_van_tra_ket_qua_vong_lap_di_tiep(self) -> None:
        deps, events = make_deps(
            [wants_tools("web_search"), answer("Minh chua tra cuu duoc.")],
            tools=FakeTools(ok=False),
        )

        result = await generate(deps, PROMPT, CTX, FakeLogger())

        assert result == Ok("Minh chua tra cuu duoc.")
        assert any(isinstance(e, ObservationEvent) and not e.ok for e in events)

    async def test_401_khong_bi_phan_loai_thanh_timeout(self) -> None:
        error = Exception("401 Incorrect API key")
        setattr(error, "status", 401)  # noqa: B010 — mo phong hinh dang loi cua SDK
        deps, _ = make_deps([answer("x")], llm=FakeLlm(error=error))

        result = await generate(deps, PROMPT, CTX, FakeLogger())

        assert not isinstance(result, Ok)
        assert result.error.status == 401  # type: ignore[union-attr]

    async def test_khong_co_cong_cu_thi_khong_gui_tham_so_tools(self) -> None:
        deps, _ = make_deps(
            [answer("Tra loi bang kien thuc san co.")], tools=FakeTools(definitions=())
        )

        await generate(deps, PROMPT, CTX, FakeLogger())

        assert deps.llm.calls[0]["tools"] == ()  # type: ignore[attr-defined]


KB_TOOL = ToolDefinition(
    name="search_knowledge_base",
    description="tra tai lieu noi bo",
    parameters={"type": "object"},
    requirements=ToolRequirements(rate_limit="-", cost_per_call="-", timeout_ms=1000),
    returns="-",
    failure_modes=(),
)


class TestChanChuaTraDaTraLoi:
    """Chan 7: model dinh tra loi ma chua tra tai lieu lan nao -> NHAC MOT LAN.

    VI SAO PHAI CHAN O TANG NAY chu khong viet them vao prompt: lop cau hoi nay da bi
    danh o ca BA tang cau chu — mo ta cong cu goi ten cam bay "MOT CON SO / MOT CACH
    LAM", SYSTEM_PROMPT co luat cung "KHONG tra loi tu tri nho", ket qua cong cu neu
    hai nhanh — va no VAN chi giu duoc mot nua.

    Do that 11/09/2026, chay lap ba luot hai cau "lam sao cho bot chat" / "cach khu
    mui hoi", qua handle_message that:

        truoc chan nay   3/6 luot co goi cong cu
        sau chan nay     6/6

    Khi khong goi, cau tra loi la kien thuc pho thong thuan tuy ("ngam nuoc voi
    trong", "baking soda") — khong mot chu nao trong tai lieu.

    Chan nay KHONG tu phan loai cau hoi. Mot bo phan loai bang tu khoa se sai theo
    kieu im lang; model thi doc ca doan hoi thoai, nen loi nhac neu ro CA HAI nhanh
    va de no quyet. Do ca am: bon luot khong co du kien (chao, cam on, hoi ten bot,
    nho viet lai cau) deu KHONG bi keo di tra.
    """

    async def test_nhac_khi_chua_tra_tai_lieu(self) -> None:
        deps, _ = make_deps(
            [answer("Luoc khoai so 15 phut."), answer("Theo tai lieu thi 30 phut.")],
            tools=FakeTools(definitions=(KB_TOOL,)),
        )

        result = await generate(deps, PROMPT, CTX, FakeLogger())

        assert result == Ok("Theo tai lieu thi 30 phut.")

    async def test_KHONG_nhac_khi_da_goi_cong_cu_tai_lieu(self) -> None:
        """Da tra roi thi cau tra loi tiep theo khong bi chan nua."""
        deps, _ = make_deps(
            [wants_tools("search_knowledge_base"), answer("30 phut.")],
            tools=FakeTools(definitions=(KB_TOOL,)),
        )

        result = await generate(deps, PROMPT, CTX, FakeLogger())

        assert result == Ok("30 phut.")

    async def test_KHONG_nhac_khi_kho_chua_co_tai_lieu(self) -> None:
        """`search_knowledge_base` chi duoc khai khi da nap tai lieu. Chua co gi de
        tra thi bat tra la dot mot luot goi model cho khong.
        """
        deps, _ = make_deps([answer("Tra loi ngay.")], tools=FakeTools())

        result = await generate(deps, PROMPT, CTX, FakeLogger())

        assert result == Ok("Tra loi ngay.")

    async def test_chi_nhac_DUNG_MOT_LAN(self) -> None:
        """Nhac lai nhieu lan la dung lai dung cai vong lap ma luat 07/09 duoc lap ra
        de chan: bot hoi/nhac mai ma khong lam gi.
        """
        deps, _ = make_deps(
            [answer("Lan mot."), answer("Lan hai."), answer("Lan ba.")],
            tools=FakeTools(definitions=(KB_TOOL,)),
        )

        result = await generate(deps, PROMPT, CTX, FakeLogger())

        assert result == Ok("Lan hai.")

    async def test_KHONG_nhac_o_vong_cuoi(self) -> None:
        """Vong cuoi khong con vong nao de doc ket qua tra ve, nen nhac chi to phi mot
        luot goi model ma van ra dung cau tra loi do.
        """
        deps, _ = make_deps(
            [answer("Cau tra loi.")],
            tools=FakeTools(definitions=(KB_TOOL,)),
            max_iterations=1,
        )

        result = await generate(deps, PROMPT, CTX, FakeLogger())

        assert result == Ok("Cau tra loi.")

    async def test_loi_nhac_CAM_lo_ra_nguoi_dung(self) -> None:
        """Ca am da xay ra that: ban dau loi nhac chi noi "dung nhac toi no", va model
        tra loi CHINH LOI NHAC — hoi "Cam on nhe" thi nhan ve "Minh da hieu: voi cau
        co du kien se goi search_knowledge_base truoc...". Vua vo nghia voi nguoi
        dung, vua lo ten cong cu, tuc pham luat "khong ke chuyen hau truong".
        """
        assert "người dùng KHÔNG nhìn thấy" in NHAC_TRA_TAI_LIEU
        assert "TUYỆT ĐỐI không nhắc tới tin nhắn này" in NHAC_TRA_TAI_LIEU
        assert "không nêu tên công cụ" in NHAC_TRA_TAI_LIEU

    async def test_loi_nhac_neu_CA_HAI_nhanh(self) -> None:
        """Chi neu nhanh "di tra" thi model se tra ca cho loi chao."""
        assert "Nếu đây là câu hỏi CÓ DỮ KIỆN" in NHAC_TRA_TAI_LIEU
        assert "Nếu KHÔNG phải câu có dữ kiện" in NHAC_TRA_TAI_LIEU
