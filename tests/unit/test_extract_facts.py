"""L3 implicit — bot tu trich fact.

Day la tinh nang ghi thong tin ve NGUOI CO TEN ma khong ai bam nut dong y, nen test
o day tap trung vao ba thu: khong gan nham nguoi, khong ghi khi khong chac, va
khong bao gio chay khi chua duoc bat.
"""

import pytest

from memory.jobs.extract_facts import (
    MIN_CONFIDENCE,
    parse_line,
    render_for_extract,
)
from memory.repository.summary_repo import PendingMessage

NAMES = {"nam": "u-nam", "lan": "u-lan"}


def tin(text: str, *, ten: str = "Nam", uid: str = "u-nam", bot: bool = False) -> PendingMessage:
    return PendingMessage(
        message_id="m", sender_id=uid, sender_name=ten, text=text, from_bot=bot
    )


class TestDauVao:
    def test_LOAI_cau_tra_loi_cua_bot(self) -> None:
        """Bot khong phai nguon su that ve nguoi dung.

        No doan, no dien giai, va no lap lai loi nguoi dung theo cach cua no. Trich
        fact tu chinh dau ra cua model la cach nhanh nhat de mot suy doan tro thanh
        "dieu da biet".
        """
        out = render_for_extract(
            [tin("Nam làm backend"), tin("Nam là lập trình viên giỏi", bot=True)]
        )

        assert "Nam làm backend" in out
        assert "lập trình viên giỏi" not in out

    def test_giu_ten_de_model_biet_gan_cho_ai(self) -> None:
        out = render_for_extract([tin("mình làm backend", ten="Hùng", uid="u-hung")])
        assert out.startswith("[Hùng]:")

    def test_toan_tin_cua_bot_thi_ra_chuoi_rong(self) -> None:
        assert render_for_extract([tin("gì đó", bot=True)]) == ""


class TestPhanTichDong:
    def test_dong_dung_dinh_dang(self) -> None:
        assert parse_line("Nam | Nam làm backend Node.js | 0.95", NAMES) == (
            "user:u-nam",
            "Nam làm backend Node.js",
            0.95,
        )

    def test_khong_phan_biet_hoa_thuong_o_ten(self) -> None:
        assert parse_line("NAM | Nam làm backend | 0.9", NAMES) is not None

    def test_ten_KHONG_co_trong_lo_thi_BO_QUA(self) -> None:
        """Cho nguy hiem nhat cua ca tinh nang.

        Model co the nhac mot cai ten no doc duoc dau do trong noi dung tin nhan.
        Gan fact cho mot nguoi khong co mat trong doan hoi thoai vua doc la ghi bua
        vao ho so cua ai do. Mot fact bi bo sot con hon mot fact gan nham nguoi.
        """
        assert parse_line("Hùng | Hùng làm giám đốc | 0.99", NAMES) is None

    @pytest.mark.parametrize(
        "line",
        [
            "Nam làm backend | 0.9",          # thieu ten
            "Nam | Nam làm backend",           # thieu do tin cay
            "Nam | Nam làm backend | cao",     # do tin cay khong phai so
            "Nam | | 0.9",                     # noi dung rong
            "linh tinh",
            "",
        ],
    )
    def test_dong_hong_thi_bo_qua_chu_khong_no(self, line: str) -> None:
        assert parse_line(line, NAMES) is None

    @pytest.mark.parametrize("value", ["-0.1", "1.5"])
    def test_do_tin_cay_ngoai_khoang_0_1_thi_bo_qua(self, value: str) -> None:
        assert parse_line(f"Nam | Nam làm backend | {value}", NAMES) is None


class TestNguongTinCay:
    def test_nguong_khop_ke_hoach_goc(self) -> None:
        # "Chi ghi khi confidence >= 0.8" — nghia la model phai gan nhu chac chan,
        # khong phai "co ve dung".
        assert MIN_CONFIDENCE == 0.8

    def test_duoi_nguong_thi_parse_duoc_nhung_cho_goi_phai_loai(self) -> None:
        # parse_line KHONG loc theo nguong: no chi doc. Viec loc nam o extract_facts
        # de log duoc ly do bo qua.
        parsed = parse_line("Nam | Nam có thể làm backend | 0.5", NAMES)
        assert parsed is not None
        assert parsed[2] < MIN_CONFIDENCE
