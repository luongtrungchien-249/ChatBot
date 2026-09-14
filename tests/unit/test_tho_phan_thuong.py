"""HAM THUONG VERIFIABLE cho RLVR. Xem docs/plan-rlvr-tho.md lop 2.

TEP NAY KHAT KHE HON MOI TEP TEST KHAC TRONG DU AN, co ly do:

Mot bo LOC bao nham thi loai oan mot bai tot — kho chiu, khong tich luy.
Mot ham THUONG bao nham thi DAY MODEL hoc sai, va sai lech tich luy qua tung buoc cap
nhat. Moi ke ho o day deu tro thanh muc tieu toi uu cua model.

Nen ba nhom test duoi day khong phai "kiem tra cho chac", ma la nhung LO HONG CU THE
ma mot model duoc toi uu se tim ra.
"""

import pytest

from tho.phan_thuong import NGUONG_LAP, TRONG_SO, phan_thuong, thuong

SACH = (
    "Trâu ơi ta bảo trâu này\n"
    "Trâu ra ngoài ruộng trâu cày với ta\n"
    "Cấy cày vốn nghiệp nông gia\n"
    "Ta đây trâu đấy ai mà quản công"
)
QUA_DEO_NGANG = (
    "Bước tới Đèo Ngang bóng xế tà\n"
    "Cỏ cây chen đá lá chen hoa\n"
    "Lom khom dưới núi tiều vài chú\n"
    "Lác đác bên sông chợ mấy nhà\n"
    "Nhớ nước đau lòng con quốc quốc\n"
    "Thương nhà mỏi miệng cái gia gia\n"
    "Dừng chân đứng lại trời non nước\n"
    "Một mảnh tình riêng ta với ta"
)


class TestThangDo:
    def test_trong_so_cong_lai_bang_mot(self) -> None:
        assert sum(TRONG_SO.values()) == pytest.approx(1.0)

    def test_tho_chuan_duoc_diem_toi_da(self) -> None:
        assert thuong(SACH) == pytest.approx(1.0)

    def test_bat_cu_chuan_duoc_diem_toi_da(self) -> None:
        assert thuong(QUA_DEO_NGANG, "that_ngon_bat_cu") == pytest.approx(1.0)

    def test_bai_trong_duoc_khong(self) -> None:
        assert thuong("") == 0.0

    def test_luon_nam_trong_khoang_0_1(self) -> None:
        for b in (SACH, QUA_DEO_NGANG, "", "xyz", "a\nb\nc"):
            for t in ("luc_bat", "that_ngon_bat_cu", "that_ngon_tu_tuyet"):
                assert 0.0 <= thuong(b, t) <= 1.0


class TestThuongDacKhongThua:
    """Nhi phan thi model goc gan nhu luon duoc 0 — GRPO khong co gradient de di."""

    def test_sai_it_hon_thi_duoc_diem_cao_hon(self) -> None:
        nang = "Một hai ba bốn năm sáu bảy\nTám chín mười"
        nhe = "Trâu ơi ta bảo trâu này nhé\nTrâu ra ngoài ruộng trâu cày với ta"

        assert thuong(nhe) > thuong(nang) > 0.0

    def test_thu_tu_dung_tren_bon_muc_hong(self) -> None:
        sai_van = "Trâu ơi ta bảo trâu này\nTrâu ra ngoài ruộng cùng ta sớm chiều"
        khung_nhe = "Trâu ơi ta bảo trâu này nhé\nTrâu ra ngoài ruộng trâu cày với ta"
        khung_nang = "Một hai ba bốn năm sáu bảy\nTám chín mười"

        assert thuong(SACH) > thuong(sai_van) > thuong(khung_nhe) > thuong(khung_nang)


class TestSaiKhungKhongDuocDiemMienPhi:
    """LO HONG NGHIEM TRONG NHAT, bat duoc ngay lan chay thu dau tien.

    Moi bo kiem deu BO QUA van/thanh tren cau sai so tieng (tranh loi gia day chuyen).
    Voi ham THUONG thi do thanh: khong loi nao duoc bao o nhom do -> ti le thoa 1,0 ->
    DIEM TUYET DOI cho thu chua he duoc kiem.

    Do that truoc khi sua: bai hai cau 7/3 tieng an 0,800/1,0.
    """

    HONG = "Một hai ba bốn năm sáu bảy\nTám chín mười"

    def test_khong_an_diem_van_khi_khung_da_hong(self) -> None:
        r = phan_thuong(self.HONG)

        assert r.van == 0.0
        assert r.thanh == 0.0
        assert r.doi == 0.0

    def test_diem_tong_thap_han(self) -> None:
        assert phan_thuong(self.HONG).tong < 0.2

    def test_VAN_con_gradient_de_sua_khung(self) -> None:
        """Khung duoc cham theo ti le, nen sai it van hon sai nhieu."""
        assert phan_thuong(self.HONG).tong > 0.0


class TestChongLach:
    """Toi uu thang vao bo do thi moi ke ho cua no deu thanh muc tieu."""

    def test_CHEP_bai_mau_thi_thuong_bang_khong(self) -> None:
        """Chep ca dao la cach re nhat de an diem luat tuyet doi ma khong sang tac gi.

        Nhan voi 0 chu khong tru: tru thi bai chep van giu duoc diem duong.
        """
        chep = (
            "Công cha như núi Thái Sơn\n"
            "Nghĩa mẹ như nước trong nguồn chảy ra\n"
            "Một lòng thờ mẹ kính cha\n"
            "Cho tròn chữ hiếu mới là đạo con"
        )
        r = phan_thuong(chep)

        assert r.tong == 0.0
        assert r.khung == 1.0, "bài vẫn đúng luật — điểm 0 là do PHẠT, không do luật"
        assert any("chép" in x for x in r.ly_do_phat)

    def test_BE_CHU_bi_phat_du_van_dung(self) -> None:
        """Lo hong nguy hiem nhat: be chu LAM TANG diem van, tuc duoc thuong TRUC TIEP."""
        be = "Như dòng nước chảy trong cao\nTỏa hương thanh khiết ngọt ngao nụ cười"
        r = phan_thuong(be)

        assert r.van == 1.0, "vần vẫn 'đúng' — đó chính là vấn đề"
        assert r.he_so_phat < 1.0
        assert any("bẻ chữ" in x for x in r.ly_do_phat)

    def test_bai_LAP_suy_bien_bi_phat(self) -> None:
        lap = "\n".join(["Ta ta ta ta ta ta", "Ta ta ta ta ta ta ta ta"] * 2)
        r = phan_thuong(lap)

        assert r.he_so_phat < 1.0
        assert any("lặp" in x for x in r.ly_do_phat)

    def test_lap_NGHE_THUAT_cua_tho_chuan_KHONG_bi_phat(self) -> None:
        """«Qua Đèo Ngang» lap "chen", "quoc quoc", "gia gia", "ta voi ta" — CO Y."""
        r = phan_thuong(QUA_DEO_NGANG, "that_ngon_bat_cu")

        assert r.he_so_phat == 1.0
        assert NGUONG_LAP > 0.34, "ngưỡng phải chừa chỗ cho lặp nghệ thuật"

    def test_bai_NGAN_khong_tu_dong_duoc_diem_cao_hon(self) -> None:
        """Chuan hoa theo SO RANG BUOC: neu khong, bai ngan an diem de hon."""
        ngan = "Trâu ơi ta bảo trâu này\nTrâu ra ngoài ruộng trâu cày với ta"

        assert thuong(ngan) == pytest.approx(thuong(SACH))


class TestChiTietDeGoLoi:
    def test_tach_bach_tung_phan(self) -> None:
        r = phan_thuong(SACH)

        assert (r.khung, r.van, r.thanh) == (1.0, 1.0, 1.0)
        assert r.ly_do_phat == ()
