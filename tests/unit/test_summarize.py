"""L2 — nen hoi thoai cu.

Cai de sai nhat khong phai chat luong ban tom tat, ma la MAT DU LIEU: 15 tin bi
danh dau `summarized` ma ban tom tat khong duoc ghi la 15 tin bien mat vinh vien —
khong con trong L1, chua vao L2, va co da bat nen khong ai lay lai.
"""

import pytest

from agents.domain.thread import ThreadScope
from memory.jobs.summarize import BATCH, DRIFT_WARN_GENERATIONS, THRESHOLD
from memory.repository.summary_repo import (
    PendingMessage,
    Summary,
    commit_summary,
    render_for_summary,
    render_previous,
)


def tin(text: str, *, ten: str = "Nam", from_bot: bool = False) -> PendingMessage:
    return PendingMessage(
        message_id="m", sender_id=ten.lower(), sender_name=ten, text=text, from_bot=from_bot
    )


class TestNguong:
    def test_nen_15_giu_lai_du_cho_cua_so_L1(self) -> None:
        # Nen sach thi luot hoi ngay sau do bot mat hoan toan ngu canh gan.
        assert THRESHOLD - BATCH >= 15

    def test_nguong_cao_hon_lo_nen(self) -> None:
        assert THRESHOLD > BATCH


class TestRender:
    def test_giu_ten_nguoi_gui(self) -> None:
        # Mot ban tom tat khong biet AI quyet dinh cai gi thi vo dung trong nhom.
        out = render_for_summary([tin("chốt deadline 30/11", ten="Hùng")])
        assert "Hùng" in out

    def test_danh_dau_ro_cau_cua_BOT(self) -> None:
        # Khong danh dau thi model tuong cau tra loi cua bot cung la loi nguoi dung
        # noi, va ban tom tat se ghi nham nguon cua moi khang dinh.
        out = render_for_summary([tin("deadline là 30/11", from_bot=True)])
        assert "Nam" not in out
        assert "Trợ lý" in out

    def test_giu_dung_thu_tu(self) -> None:
        out = render_for_summary([tin("một"), tin("hai"), tin("ba")])
        assert out.index("một") < out.index("hai") < out.index("ba")

    def test_khong_co_tom_tat_cu_thi_khong_them_the_rong(self) -> None:
        assert render_previous(None) == ""

    def test_co_tom_tat_cu_thi_boc_trong_the(self) -> None:
        out = render_previous(Summary(text="nhóm họp thứ 3", msg_count=15, gen_count=1))
        assert "<tom_tat_cu>" in out and "nhóm họp thứ 3" in out


class TestCanhBaoTroiThongTin:
    def test_nguong_canh_bao_khop_cam_bay_da_biet(self) -> None:
        """Ke hoach goc ghi "sau 5-6 lan nen summary bat dau sai lech" nhung khong
        de xuat cach phat hien. gen_count la cach do.
        """
        assert DRIFT_WARN_GENERATIONS == 6


class TestCommitRong:
    async def test_danh_sach_rong_thi_KHONG_cham_DB(self) -> None:
        """commit_summary([]) phai thoat som.

        Neu no van chay UPDATE ... WHERE message_id = ANY('{}') thi cau lenh vo hai,
        nhung INSERT thread_summary se ghi mot ban tom tat voi 0 tin va gen_count
        tang len — dem the he sai, va canh bao troi thong tin keu nham.
        """
        # Khong co Postgres trong unit test: neu ham nay cham DB, no se nem loi.
        await commit_summary(ThreadScope(platform="cli", thread_id="t1"), "tom tat", [], None)


@pytest.mark.parametrize("gen", [0, 5, 6, 12])
def test_dem_the_he_khong_am(gen: int) -> None:
    s = Summary(text="x", msg_count=gen * BATCH, gen_count=gen)
    assert s.gen_count >= 0
    assert s.msg_count == gen * BATCH
