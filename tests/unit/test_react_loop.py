"""Vong ReAct la cho de bien thanh vong dot tien khong day.

Nam chan cung duoi day phai duoc CHUNG MINH, khong phai tin la co.
"""

from typing import Any

from agents.domain.thread import ThreadScope
from agents.pipeline.stages.generate import (
    GenerateDeps,
    ObservationEvent,
    ReactEvent,
    ToolCallEvent,
    generate,
)
from agents.ports.llm import CallContext, LlmResult, UserMessage
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
