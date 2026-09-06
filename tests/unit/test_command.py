"""Lenh khong duoc nhan dien se roi vao LLM.

Nghia la nguoi dung go "quen het" roi nhan mot cau tra loi than mat, con memory
thi khong bi xoa. Do la loi im lang — khong co thong bao nao — nen phai chot bang
test, dac biet o cap CO DAU / KHONG DAU da tung lam hong regex mention mot lan.
"""

import pytest

from agents.policy.command import (
    Forget,
    ForgetAll,
    Help,
    NoCommand,
    ShowMemory,
    parse_command,
)


class TestLenhChinhXac:
    @pytest.mark.parametrize("text", ["memory", "bo nho", "bộ nhớ", "  Bộ Nhớ  ", "MEMORY"])
    def test_xem_memory(self, text: str) -> None:
        assert parse_command(text) == ShowMemory()

    @pytest.mark.parametrize("text", ["quen het", "quên hết", "Quên Hết"])
    def test_quen_het_nhan_ca_hai_cach_go(self, text: str) -> None:
        # Nguoi Viet go khong dau la chuyen thuong. Chi nhan ban co dau thi mot nua
        # so lan go se truot xuong LLM.
        assert parse_command(text) == ForgetAll()

    @pytest.mark.parametrize("text", ["help", "huong dan", "hướng dẫn"])
    def test_huong_dan(self, text: str) -> None:
        assert parse_command(text) == Help()


class TestQuenCoNoiDung:
    def test_boc_dung_phan_noi_dung(self) -> None:
        assert parse_command("quên deadline quý 3") == Forget(pattern="deadline quý 3")

    def test_ban_khong_dau(self) -> None:
        assert parse_command("quen so dien thoai cua toi") == Forget(
            pattern="so dien thoai cua toi"
        )

    def test_quen_het_KHONG_bi_hieu_thanh_quen_voi_pattern_het(self) -> None:
        # "quen het" phai khop bang truoc regex, neu khong no thanh Forget("het") va
        # nguoi dung se thay bot hoi "co phai ban muon xoa fact chua chu 'het'?".
        assert parse_command("quen het") == ForgetAll()


class TestKhongPhaiLenh:
    @pytest.mark.parametrize(
        "text",
        [
            "deadline báo cáo quý 3 là ngày nào",
            "quên",  # thieu noi dung -> khong du de xoa gi
            "",
            "memory cua nhom minh the nao",  # co tu 'memory' nhung la cau hoi
        ],
    )
    def test_cau_hoi_thuong_di_tiep_vao_LLM(self, text: str) -> None:
        assert parse_command(text) == NoCommand()
