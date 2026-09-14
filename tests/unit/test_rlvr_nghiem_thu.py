"""Cot GIU cua nghiem thu RLVR — phan bat "dung luat nhung vo hon".

VI SAO TEP NAY QUAN TRONG HON VE NGOAI CUA NO: toi uu thang vao mot bo do tat dinh se
HY SINH nhung thu bo do khong nhin thay. Model hoan toan co the hoc ra nhung bai dung
luat tuyet doi ma vo hon — va verifier se cham chung diem tuyet doi, vi no chi biet dem
tieng va do van.

Cot GIU la thu duy nhat bat duoc dieu do. Neu chinh no hong thi ca phep nghiem thu chi
con mot nua, va nua con lai la nua DE bi lach nhat.
"""

import sys
from pathlib import Path

import pytest

GOC = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(GOC / "rlvr"))
sys.path.insert(0, str(GOC / "src"))

from nghiem_thu import (  # noqa: E402
    MUC_NOI_DUNG,
    NGUONG_TUT,
    TI_LE_CHAM_HONG_TOI_DA,
    do_tat_dinh,
    fisher,
    kiem_cot_giu,
)

SACH = (
    "Trâu ơi ta bảo trâu này\n"
    "Trâu ra ngoài ruộng trâu cày với ta\n"
    "Cấy cày vốn nghiệp nông gia\n"
    "Ta đây trâu đấy ai mà quản công"
)
CHEP = (
    "Công cha như núi Thái Sơn\n"
    "Nghĩa mẹ như nước trong nguồn chảy ra\n"
    "Một lòng thờ mẹ kính cha\n"
    "Cho tròn chữ hiếu mới là đạo con"
)
BE_CHU = "Như dòng nước chảy trong cao\nTỏa hương thanh khiết ngọt ngao nụ cười"


def _noi(**doi: float) -> dict[str, float]:
    """Diem noi dung nen, cho phep doi tung muc."""
    return {m: 6.0 + doi.get(m, 0.0) for m in MUC_NOI_DUNG}


class TestCotGiuBatDuocCacKieuHong:
    def test_khong_vi_pham_gi_thi_tra_RONG(self) -> None:
        td = do_tat_dinh([SACH])

        assert kiem_cot_giu(td, td, _noi(), _noi()) == []

    def test_bat_duoc_CHEP(self) -> None:
        """Chep ca dao la cach re nhat de an diem luat tuyet doi ma khong sang tac gi."""
        goc, moi = do_tat_dinh([SACH]), do_tat_dinh([CHEP])

        vi_pham = kiem_cot_giu(goc, moi, _noi(), _noi())

        assert any("chép" in v for v in vi_pham)

    def test_bat_duoc_CUM_BI_BE_TANG(self) -> None:
        """Be chu LAM TANG diem van, tuc duoc ham thuong tra cong TRUC TIEP."""
        goc, moi = do_tat_dinh([SACH]), do_tat_dinh([BE_CHU])

        vi_pham = kiem_cot_giu(goc, moi, _noi(), _noi())

        assert any("cụm bị bẻ" in v for v in vi_pham)

    @pytest.mark.parametrize("muc", MUC_NOI_DUNG)
    def test_bat_duoc_TUNG_MUC_noi_dung_tut(self, muc: str) -> None:
        """Day la kieu hong ma ca cot GIU ton tai de bat: dung luat hon nhung vo hon."""
        td = do_tat_dinh([SACH])

        vi_pham = kiem_cot_giu(td, td, _noi(), _noi(**{muc: -(NGUONG_TUT + 0.1)}))

        assert any(muc in v for v in vi_pham)

    def test_tut_DUOI_nguong_thi_khong_bao(self) -> None:
        td = do_tat_dinh([SACH])

        assert kiem_cot_giu(td, td, _noi(), _noi(ngon_ngu=-(NGUONG_TUT - 0.1))) == []

    def test_noi_dung_TANG_thi_khong_bao(self) -> None:
        td = do_tat_dinh([SACH])

        assert kiem_cot_giu(td, td, _noi(), _noi(sang_tao=+2.0)) == []


class TestKhongDoDuocNoiDungThiKHONGKetLuan:
    """`None` = nguoi cham hong, KHONG phai 0 diem.

    Neu coi None nhu 0 thi cot GIU se bao "noi dung tut" o MOI lan chay — ke ca nhung
    lan no khong tut. Va nguoc lai, im lang bo qua thi mot lan chay thieu nua phep do
    van duoc bao la DAT.
    """

    def test_thieu_diem_GOC_thi_bao_la_chua_ket_luan_duoc(self) -> None:
        td = do_tat_dinh([SACH])

        vi_pham = kiem_cot_giu(td, td, None, _noi())

        assert any("KHÔNG đo được" in v for v in vi_pham)

    def test_thieu_diem_MOI_thi_bao_la_chua_ket_luan_duoc(self) -> None:
        td = do_tat_dinh([SACH])

        vi_pham = kiem_cot_giu(td, td, _noi(), None)

        assert any("KHÔNG đo được" in v for v in vi_pham)

    def test_nguong_cham_hong_duoc_ghim(self) -> None:
        assert 0.0 < TI_LE_CHAM_HONG_TOI_DA <= 0.25


class TestFisher:
    def test_khong_chenh_thi_p_bang_mot(self) -> None:
        assert fisher(50, 50, 50, 50) == pytest.approx(1.0)

    def test_chenh_lon_thi_p_nho(self) -> None:
        assert fisher(10, 90, 90, 10) < 0.001

    def test_bang_rong_khong_nem_loi(self) -> None:
        assert fisher(0, 0, 0, 0) == 1.0


class TestDoTatDinh:
    def test_dem_dung_bai_sach(self) -> None:
        assert do_tat_dinh([SACH, BE_CHU])["sạch luật"] == 2

    def test_thuong_trung_binh_nam_trong_khoang(self) -> None:
        assert 0.0 <= do_tat_dinh([SACH, BE_CHU])["thưởng TB"] <= 1.0


class TestHamThuongCuaGRPO:
    """`ham_thuong` la thu TRL goi moi buoc. Sai o day thi ca lan huan luyen hong.

    mypy bat duoc HAI loi kieu o ham nay ngay khi `rlvr/` duoc dua vao pham vi kiem —
    truoc do no nam ngoai va khong ai kiem.
    """

    def test_khong_co_the_tho_thi_mac_dinh_luc_bat(self) -> None:
        from huan_luyen import ham_thuong

        assert ham_thuong([SACH]) == [pytest.approx(1.0)]

    def test_nhan_DANH_SACH_the_tho_song_song_voi_ban_sinh(self) -> None:
        """TRL truyen cac cot cua tap du lieu vao duoi dang list song song."""
        from huan_luyen import ham_thuong

        d = ham_thuong([SACH, SACH], the_tho=["luc_bat", "luc_bat"])

        assert d == [pytest.approx(1.0), pytest.approx(1.0)]

    def test_nhan_duoc_ca_MOT_CHUOI_chung(self) -> None:
        from huan_luyen import ham_thuong

        assert ham_thuong([SACH, SACH], the_tho="luc_bat") == [
            pytest.approx(1.0),
            pytest.approx(1.0),
        ]

    def test_LECH_DO_DAI_thi_NEM_RA_chu_khong_cham_nham(self) -> None:
        """Cham nham the tho cho diem gan 0 cho MOI ban — va se chay IM LANG."""
        from huan_luyen import ham_thuong

        with pytest.raises(ValueError, match="the_tho"):
            ham_thuong([SACH, SACH], the_tho=["luc_bat"])

    def test_moi_diem_nam_trong_khoang_0_1(self) -> None:
        from huan_luyen import ham_thuong

        for d in ham_thuong([SACH, BE_CHU, CHEP, ""]):
            assert 0.0 <= d <= 1.0
