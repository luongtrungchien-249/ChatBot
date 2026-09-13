"""BUOC 8 muc ba — bo do MACH NOI DUNG bang luat. DA DO VA DANG KHONG DUOC DUNG.

Tep nay ghim hai thu:
  1. hanh vi cua bo do (de ai do lam lai con biet no tung lam duoc gi)
  2. rang no KHONG duoc noi vao duong chon bai — vi 19,50% bao nham

Xem docstring tho/mach_y.py de biet bon cach da thu va so do cua tung cach.
"""

import inspect

from tho import sinh
from tho.mach_y import SO_CAU_TOI_THIEU, cau_lac_mach, truong_cua_cau

CA_DAO = (
    "Công cha như núi Thái Sơn\n"
    "Nghĩa mẹ như nước trong nguồn chảy ra\n"
    "Một lòng thờ mẹ kính cha\n"
    "Cho tròn chữ hiếu mới là đạo con"
)
LAC = (
    "Cha già tóc bạc như mây\n"
    "Ngoài kia biển cả sóng đầy trùng khơi\n"
    "Thầy cô lớp học bảng vôi\n"
    "Mùa thu lá rụng bên trời xa xăm"
)


class TestKHONGDuocNoiVaoDuongChonBai:
    """Rang buoc quan trong nhat cua tep nay.

    Bo do bao nham 19,50% tren tho DUNG CHUAN, trong khi `cum_nghi_be` — bo do duy nhat
    duoc phep tham gia xep hang — o muc 1,60%. Noi no vao `_xep_hang` la phat mot phan
    nam so bai TOT.
    """

    def test_xep_hang_KHONG_goi_toi_mach_y(self) -> None:
        assert "mach_y" not in inspect.getsource(sinh._xep_hang)
        assert "cau_lac_mach" not in inspect.getsource(sinh._xep_hang)

    def test_sinh_tho_KHONG_nhap_mach_y(self) -> None:
        assert not hasattr(sinh, "cau_lac_mach")


class TestBatDuocCaNguoiDungNeu:
    def test_bai_nhay_chu_de_thi_bat_duoc(self) -> None:
        """Dung ca nguoi dung mo ta: cau 1 cha, cau 3 dot nhien sang chuyen khac."""
        lac = cau_lac_mach(LAC)

        assert [i for i, _ in lac] == [2, 3]

    def test_ca_dao_dung_mach_thi_SACH(self) -> None:
        assert cau_lac_mach(CA_DAO) == []



class TestBaChoThanTrong:
    """Ba cho than trong o dau tho/mach_y.py. Ca ba deu la bai hoc da tra gia."""

    def test_cau_KHONG_nhan_ra_truong_nao_thi_khong_bao_gio_bi_bao(self) -> None:
        """"Khong biet" phai ra "khong biet", khong duoc ra "sai" — luat cua kiem_nhip."""
        bai = "Lơ thơ tơ liễu buông mành\nXập xè én liệng lầu không\nDặm ngàn nước thẳm"

        for so_cau, _ in cau_lac_mach(bai):
            assert truong_cua_cau(bai.split("\n")[so_cau - 1])

    def test_bai_duoi_ba_cau_thi_KHONG_xet(self) -> None:
        """Hai cau thi "chia truong voi cau khac" thanh "giong het cau kia"."""
        cap = "Cha già tóc bạc như mây\nNgoài kia biển cả sóng đầy trùng khơi"

        assert len(cap.split("\n")) < SO_CAU_TOI_THIEU
        assert cau_lac_mach(cap) == []

    def test_bai_trong_khong_nem_loi(self) -> None:
        assert cau_lac_mach("") == []
        assert cau_lac_mach("\n\n") == []


class TestTruongCuaCau:
    def test_nhan_ra_tu_GHEP_hai_tieng(self) -> None:
        """"cội nguồn" la mot muc trong bang; nhan theo tung tieng se bo sot."""
        assert "gia đình" in truong_cua_cau("Nhớ về cội nguồn xa xưa")

    def test_bo_dau_cau_truoc_khi_tra(self) -> None:
        assert truong_cua_cau("Mẹ ơi, con nhớ!") == truong_cua_cau("Mẹ ơi con nhớ")

    def test_mot_tu_o_NHIEU_truong_lam_bot_bao_nham(self) -> None:
        """"giếng" vua que huong vua song nuoc — cho chong lan nay la co chu dich."""
        t = truong_cua_cau("Giếng nước trong veo")

        assert {"quê hương", "sông nước"} <= t

    def test_cau_khong_co_gi_trong_bang_thi_tra_RONG(self) -> None:
        assert truong_cua_cau("Xyz qrst uvw") == set()
