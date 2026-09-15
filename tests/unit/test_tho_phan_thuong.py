"""HAM THUONG VERIFIABLE cho RLVR. Xem docs/plan-rlvr-tho.md lop 2.

TEP NAY KHAT KHE HON MOI TEP TEST KHAC TRONG DU AN, co ly do:

Mot bo LOC bao nham thi loai oan mot bai tot — kho chiu, khong tich luy.
Mot ham THUONG bao nham thi DAY MODEL hoc sai, va sai lech tich luy qua tung buoc cap
nhat. Moi ke ho o day deu tro thanh muc tieu toi uu cua model.

Nen ba nhom test duoi day khong phai "kiem tra cho chac", ma la nhung LO HONG CU THE
ma mot model duoc toi uu se tim ra.
"""

import pytest

from tho.phan_thuong import NGUONG_LAP, TRONG_SO_GOC, phan_thuong, thuong, trong_so

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
    @pytest.mark.parametrize(
        "the", ["luc_bat", "that_ngon_bat_cu", "that_ngon_tu_tuyet"]
    )
    def test_trong_so_cong_lai_bang_mot_o_MOI_the(self, the: str) -> None:
        assert sum(trong_so(the).values()) == pytest.approx(1.0)

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


class TestDongGopPhuongSai:
    """Loai test ma 33 test truoc KHONG co — va vi the mot loi that da lot qua.

    Cac test kia kiem GIA TRI: bai nay duoc bao nhieu diem. Nhung thu GRPO dung khong
    phai gia tri, ma la PHUONG SAI TRONG NHOM: advantage = (r_i - mean) / std. Mot thanh
    phan luon bang nhau o moi ban thi trong so cua no la mot con so chet; mot thanh phan
    lap lai thanh phan khac thi trong so cua no la khuech dai nguy trang.

    LOI DA CHAY THAT: luc bat khong co luat DOI, nhung `doi` van mang trong so 0,10. Do
    15/09 tren 10 nhom x 8 ban that: `doi` co phuong sai CAO NHAT bang (std 0,4704) va
    chiem 15,6% phuong sai cua R_total — de LAP LAI dung cai `khung` da noi.

    `R_total` that su khi do la 0,40·khung + 0,35·van + 0,25·thanh, khong phai bang da
    ghi trong code.
    """

    @pytest.mark.parametrize("the", ["luc_bat", "that_ngon_tu_tuyet"])
    def test_the_KHONG_co_luat_doi_thi_doi_KHONG_co_trong_so(self, the: str) -> None:
        assert trong_so(the)["doi"] == 0.0

    def test_bat_cu_CO_luat_doi_thi_doi_VAN_co_trong_so(self) -> None:
        """Sua cho the kia khong duoc lam mat cho the nay."""
        assert trong_so("that_ngon_bat_cu")["doi"] > 0.0

    def test_doi_KHONG_the_lam_doi_diem_cua_luc_bat(self) -> None:
        """Ghim dung ca da hong: `doi` bam theo `khung`, nen neu con trong so thi no
        cong them mot lan nua vao dung tin hieu khung.
        """
        r = phan_thuong(SACH)
        ts = trong_so("luc_bat")
        tong_ba_phan = sum(ts[k] * getattr(r, k) for k in ("khung", "van", "thanh"))

        assert r.tong == pytest.approx(tong_ba_phan)

    def test_trong_so_SUY_TU_so_rang_buoc_chu_khong_ghi_cung(self) -> None:
        """Ghi hai bang cung thi chung se lech nhau vao ngay them mot the tho."""
        import inspect

        from tho import phan_thuong as mod

        nguon = inspect.getsource(mod.trong_so)

        assert "_dem_rang_buoc" in nguon

    def test_dung_so_cau_CHUAN_chu_khong_so_cau_cua_BAI(self) -> None:
        """Dung so cau quan sat duoc thi bai suy bien tu duoc chuan hoa co loi.

        Bai mot cau -> khong co cap van nao -> bo trong so cua `van` -> con moi `khung`
        -> va no an diem cao hon mot bai bon cau chi lech mot van.
        """
        mot_cau = "Trâu ơi ta bảo trâu này"
        sai_van = "Trâu ơi ta bảo trâu này\nTrâu ra ngoài ruộng cùng ta sớm chiều"

        assert thuong(sai_van) > thuong(mot_cau)

    def test_ti_le_giua_ba_thanh_phan_GIU_NGUYEN_sau_khi_chuan_hoa(self) -> None:
        """Bo `doi` chi duoc doi DO LON, khong duoc doi THU TU uu tien."""
        ts = trong_so("luc_bat")
        goc = TRONG_SO_GOC

        assert ts["van"] > ts["khung"] > ts["thanh"]
        assert ts["van"] / ts["khung"] == pytest.approx(goc["van"] / goc["khung"])
