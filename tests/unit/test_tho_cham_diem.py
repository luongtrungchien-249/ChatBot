"""Thang 100 diem — phan TAT DINH (45 diem). Thuan, khong mang, khong model.

Tap kiem thu vang van la tho DA DUOC THUA NHAN: Truyen Kieu phai duoc 45/45. Bao thap
hon o do gan nhu chac chan la BO CHAM SAI, khong phai Nguyen Du sai.
"""

from tho import cham_tat_dinh
from tho.cham_diem import DIEM_BANG_TRAC, DIEM_THE, DIEM_VAN, TONG_TAT_DINH

KIEU = (
    "Trăm năm trong cõi người ta\n"
    "Chữ tài chữ mệnh khéo là ghét nhau\n"
    "Trải qua một cuộc bể dâu\n"
    "Những điều trông thấy mà đau đớn lòng"
)


class TestThoChuanMuc:
    async def test_Truyen_Kieu_duoc_diem_TUYET_DOI(self) -> None:
        d = cham_tat_dinh(KIEU)

        assert d.tong == TONG_TAT_DINH
        assert d.the == DIEM_THE
        assert d.van == DIEM_VAN
        assert d.bang_trac == DIEM_BANG_TRAC

    async def test_ca_dao_cung_gan_tuyet_doi(self) -> None:
        """Ca dao nay co tieng 2 cau 2 la thanh trac ('mẹ'), tuc le luat theo ban dac
        ta. CHAM thi tru vai diem — do la dung. CHAN thi khong: `kiem_luc_bat()` co y
        khong ep tieng 2, vi ep se loai nham chinh cau nay.
        """
        bai = (
            "Công cha như núi Thái Sơn\n"
            "Nghĩa mẹ như nước trong nguồn chảy ra\n"
            "Một lòng thờ mẹ kính cha\n"
            "Cho tròn chữ hiếu mới là đạo con"
        )

        d = cham_tat_dinh(bai)

        assert d.the == DIEM_THE
        assert d.van == DIEM_VAN
        assert d.bang_trac < DIEM_BANG_TRAC  # tru vi tieng 2
        assert d.tong > 42


class TestTruDiem:
    async def test_sai_so_tieng_thi_tru_diem_THE(self) -> None:
        bai = "Trăm năm trong cõi người ta đây\nChữ tài chữ mệnh khéo là ghét nhau"

        d = cham_tat_dinh(bai)

        assert d.the < DIEM_THE

    async def test_KET_THUC_bang_cau_luc_cung_tru_diem_THE(self) -> None:
        """Ket thuc dung cach la mot phan cua "dung the", khong phai mot luat rieng."""
        du = cham_tat_dinh(KIEU)
        thieu = cham_tat_dinh("\n".join(KIEU.split("\n")[:3]))

        assert thieu.the < du.the

    async def test_sai_van_thi_tru_diem_VAN(self) -> None:
        bai = "Trăm năm trong cõi người ta\nChữ tài chữ mệnh khéo buồn ghét nhau"

        assert cham_tat_dinh(bai).van < DIEM_VAN

    async def test_tieng_6_va_8_cung_thanh_thi_tru_BANG_TRAC(self) -> None:
        du = cham_tat_dinh(KIEU)
        # "lòng" (huyen) -> "trông" (ngang): tieng 8 cung thanh voi tieng 6 "đau"?
        sai = KIEU.replace("mà đau đớn lòng", "mà đau đớn đông")

        assert cham_tat_dinh(sai).bang_trac < du.bang_trac


class TestCaAm:
    async def test_bai_TRONG_duoc_0_diem_chu_khong_phai_diem_toi_da(self) -> None:
        """Ca am quan trong nhat cua ca tep. Khong co cho nao de xet thi de chia cho
        khong roi tra ve diem toi da la kieu tu lua ma ca du an nay chong: mot bai
        rong KHONG phai mot bai hoan hao.
        """
        d = cham_tat_dinh("")

        assert d.tong == 0.0
        assert d.van == 0.0

    async def test_mot_cau_duy_nhat_khong_co_moi_van_nao(self) -> None:
        d = cham_tat_dinh("Trăm năm trong cõi người ta")

        assert d.chi_tiet_van == (0, 0)
        assert d.van == 0.0

    async def test_chi_tiet_giai_thich_duoc_diem(self) -> None:
        """Diem tran trui thi khong sua duoc gi. Ti le noi ro no bi tru o dau."""
        d = cham_tat_dinh(KIEU)

        assert d.chi_tiet_the[0] == d.chi_tiet_the[1]
        assert d.chi_tiet_van == (3, 3)
