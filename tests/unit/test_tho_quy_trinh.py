"""VET cua 10 buoc lam tho. Khong mang: `goi_model` la mot ham gia.

BA LUAT phai duoc CHUNG MINH chu khong phai tin la co — ca ba la luat ghi o dau
`tho/quy_trinh.py`, va ca ba deu sinh ra tu loi da tung mac trong du an nay:

  1. KHONG GIA VO CO   — buoc chua thi cong phai ghi `da_chay=False` kem ly do
  2. KHONG NHAM "khong biet" voi "dat"  — `dat=None` khac han `dat=True`
  3. SO LUOT GOI TRONG VET = SO LUOT GOI THAT

Luat 3 la cai de hong am tham nhat: no dung hom nay, va se sai vao ngay ai do them
mot luot goi ma quen ghi vet. Nen no co test rieng chay tren nhieu cau hinh.
"""

import pytest

from tho.quy_trinh import THU_TU, SoVet, bang_vet, vet_kiem_luat
from tho.sinh import sinh_tho
from tho.y_dinh import YeuCauTho, nhan_dien

from .test_tho_sinh import DUNG_LUAT, SAI_VAN, THUA_TIENG, model_tra, model_tra_nhieu

#: Bai dung luat, CO dau phay dat dung cho ngat chan (sau tieng 2 va tieng 4).
CO_PHAY = (
    "Trâu ơi, ta bảo trâu này\n"
    "Trâu ra ngoài ruộng trâu cày với ta\n"
    "Cấy cày vốn nghiệp nông gia\n"
    "Ta đây trâu đấy ai mà quản công"
)


class TestDu10Buoc:
    async def test_du_10_vet_dung_thu_tu(self) -> None:
        goi, _ = model_tra(DUNG_LUAT)

        kq = await sinh_tho("luc_bat", "cha mẹ", goi, so_ban=1, chon_van_truoc=False)

        assert tuple(v.buoc for v in kq.vet) == THU_TU

    async def test_du_10_vet_ke_ca_khi_phai_SUA(self) -> None:
        """Duong sua la duong dai nhat. Vet khong duoc rung o giua."""
        goi, _ = model_tra(THUA_TIENG, DUNG_LUAT)

        kq = await sinh_tho("luc_bat", "", goi, so_ban=1, chon_van_truoc=False)

        assert tuple(v.buoc for v in kq.vet) == THU_TU

    async def test_du_10_vet_khi_sinh_SONG_SONG(self) -> None:
        goi, _ = model_tra_nhieu([THUA_TIENG, DUNG_LUAT, SAI_VAN])

        kq = await sinh_tho("luc_bat", "", goi, so_ban=3, so_lan_sua=0, chon_van_truoc=False)

        assert tuple(v.buoc for v in kq.vet) == THU_TU


class TestKhongGiaVoCo:
    """Luat 1: buoc chua thi cong phai NOI ra la chua, khong im lang bo qua."""

    async def test_buoc_lap_y_ghi_dung_la_CHUA_chay(self) -> None:
        goi, _ = model_tra(DUNG_LUAT)

        kq = await sinh_tho("luc_bat", "", goi, so_ban=1, chon_van_truoc=False)
        lap_y = next(v for v in kq.vet if v.buoc == "lap_y")

        assert lap_y.da_chay is False
        assert lap_y.tom_tat, "bước chưa thi công phải kèm lý do"
        assert lap_y.so_lan_goi == 0

    async def test_mach_noi_dung_ghi_dat_None_chu_khong_True(self) -> None:
        """Chua co bo do nao cho mach noi dung. Bao "dat" o day la noi doi."""
        goi, _ = model_tra(DUNG_LUAT)

        kq = await sinh_tho("luc_bat", "", goi, so_ban=1, chon_van_truoc=False)
        buoc8 = next(v for v in kq.vet if v.buoc == "kiem_noi_dung")
        mach = next(c for c in buoc8.chi_tiet if c.ten == "mạch nội dung")

        assert mach.dat is None


class TestSoLuotGoiKhopThucTe:
    """Luat 3. Vet lech voi thuc te con hai hon khong co vet."""

    @pytest.mark.parametrize(
        ("ban", "so_ban", "so_lan_sua"),
        [
            ([DUNG_LUAT], 1, 1),
            ([THUA_TIENG, DUNG_LUAT], 1, 1),
            ([THUA_TIENG, THUA_TIENG, DUNG_LUAT], 2, 1),
            ([DUNG_LUAT, SAI_VAN, THUA_TIENG], 3, 0),
        ],
    )
    async def test_tong_trong_vet_bang_so_lan_goi(
        self, ban: list[str], so_ban: int, so_lan_sua: int
    ) -> None:
        goi, _ = model_tra_nhieu(ban)

        kq = await sinh_tho(
            "luc_bat", "", goi, so_ban=so_ban, so_lan_sua=so_lan_sua, chon_van_truoc=False
        )

        assert sum(v.so_lan_goi for v in kq.vet) == kq.so_lan_goi

    async def test_buoc_4_KHONG_dem_ba_lan_cho_mot_luot_goi(self) -> None:
        """Buoc 4, 5, 6 chay chung mot luot goi. Chi buoc 4 duoc mang so luot goi."""
        goi, _ = model_tra(DUNG_LUAT)

        kq = await sinh_tho("luc_bat", "", goi, so_ban=2, chon_van_truoc=False)
        vet = {v.buoc: v for v in kq.vet}

        assert vet["sinh_cau"].so_lan_goi == 2
        assert vet["gieo_van"].so_lan_goi == 0
        assert vet["noi_mach"].so_lan_goi == 0
        assert vet["gieo_van"].da_chay is True, "chạy chung KHÁC với chưa chạy"


class TestBuoc7DuBonMuc:
    async def test_co_du_bon_vet_con(self) -> None:
        goi, _ = model_tra(DUNG_LUAT)

        kq = await sinh_tho("luc_bat", "", goi, so_ban=1, chon_van_truoc=False)
        buoc7 = next(v for v in kq.vet if v.buoc == "kiem_luat")

        assert [c.ten for c in buoc7.chi_tiet] == ["① số tiếng", "② vần", "③ thanh điệu", "④ nhịp"]

    def test_bai_dung_luat_thi_so_tieng_va_van_deu_DAT(self) -> None:
        from tho.luat import kiem_luc_bat

        chi_tiet = vet_kiem_luat(DUNG_LUAT, kiem_luc_bat(DUNG_LUAT, kiem_bang_trac=False), ())

        assert chi_tiet[0].dat is True
        assert chi_tiet[1].dat is True

    def test_KHONG_co_dau_phay_thi_nhip_la_None_chu_khong_phai_DAT(self) -> None:
        """Luat 2. `kiem_nhip` khong kiem duoc nhip noi chung — chi kiem duoc dau phay.

        Goi "khong co dau phay" la "dung nhip" chinh la lop loi `None` vs `0.0` da lam
        hong hai phep do trong du an nay.
        """
        from tho.luat import kiem_luc_bat

        assert "," not in DUNG_LUAT
        chi_tiet = vet_kiem_luat(DUNG_LUAT, kiem_luc_bat(DUNG_LUAT, kiem_bang_trac=False), ())

        assert chi_tiet[3].dat is None
        assert "KHÔNG kiểm được" in chi_tiet[3].tom_tat

    def test_co_dau_phay_dat_dung_cho_thi_nhip_DAT(self) -> None:
        from tho.luat import kiem_luc_bat

        chi_tiet = vet_kiem_luat(CO_PHAY, kiem_luc_bat(CO_PHAY, kiem_bang_trac=False), ())

        assert chi_tiet[3].dat is True


class TestBuoc10TaBaiCuoiCung:
    async def test_vet_buoc_10_khop_voi_bai_that_su_tra_ve(self) -> None:
        """Buoc 7 ta BAN NHAP, buoc 10 ta bai CUOI. Khi co sua, hai cai phai khac nhau."""
        goi, _ = model_tra(THUA_TIENG, DUNG_LUAT)

        kq = await sinh_tho("luc_bat", "", goi, so_ban=1, chon_van_truoc=False)
        vet = {v.buoc: v for v in kq.vet}

        assert vet["kiem_luat"].chi_tiet[0].dat is False, "bản nháp thừa tiếng"
        assert vet["xuat_ban"].chi_tiet[0].dat is True, "bài cuối đã đúng khung"
        assert not kq.con_loi


class TestSoVet:
    def test_do_ghi_vet_ca_khi_than_ham_NEM_RA(self) -> None:
        """Mot buoc hong van la mot buoc da chay — do dung la luc can nhin thay no."""
        so = SoVet()

        with pytest.raises(RuntimeError), so.do("sinh_cau", "model") as g:
            g.so_lan_goi = 2
            raise RuntimeError("model chết")

        (v,) = so.xong()
        assert v.buoc == "sinh_cau"
        assert v.da_chay is True
        assert v.so_lan_goi == 2

    def test_them_goi_cong_vao_vet_DA_ghi(self) -> None:
        so = SoVet()
        with so.do("kiem_noi_dung", "luat") as g:
            g.tom_tat = "lọc cứng"

        so.them_goi("kiem_noi_dung", 1, "người chấm")

        (v,) = so.xong()
        assert v.so_lan_goi == 1
        assert "người chấm" in v.tom_tat

    def test_them_goi_khong_am_tham_nuot_khi_buoc_chua_co(self) -> None:
        so = SoVet()
        so.them_goi("kiem_noi_dung", 3, "x")

        assert so.xong() == ()


class TestBangVet:
    async def test_in_ra_du_10_dong_va_co_tong(self) -> None:
        goi, _ = model_tra(DUNG_LUAT)
        kq = await sinh_tho("luc_bat", "cha mẹ", goi, so_ban=1, chon_van_truoc=False)

        ra = bang_vet(kq.vet)

        for ten in ("Xác định yêu cầu", "Lập ý", "Kiểm tra luật lục bát", "Xuất bản"):
            assert ten in ra
        assert "lượt gọi model" in ra


class TestThongDiep:
    """Buoc 1 tach yeu cau thanh bon phan; day la phan thu tu."""

    @pytest.mark.parametrize(
        ("chu_de", "mong_doi"),
        [
            ("cha mẹ", "công ơn sinh thành, lòng hiếu thảo"),
            ("uống nước nhớ nguồn", "lòng biết ơn, nhớ người đi trước"),
            ("người con gái Việt Nam xưa", "vẻ đẹp và nết người"),
            ("mùa thu", "cảnh vật, và tâm trạng gửi trong cảnh"),
        ],
    )
    def test_suy_duoc_thong_diep(self, chu_de: str, mong_doi: str) -> None:
        assert YeuCauTho(the_tho="luc_bat", chu_de=chu_de).thong_diep == mong_doi

    def test_con_gai_viet_nam_ra_VE_DEP_chu_khong_ra_DAT_NUOC(self) -> None:
        """Thu tu trong `_THONG_DIEP` co y nghia — chu de nay khop CA HAI dong."""
        yc = YeuCauTho(the_tho="luc_bat", chu_de="người con gái Việt Nam xưa")

        assert yc.thong_diep == "vẻ đẹp và nết người"

    @pytest.mark.parametrize("chu_de", ["", "cái máy giặt", "hợp đồng bảo hiểm"])
    def test_khong_khop_thi_tra_RONG_chu_khong_doan_bua(self, chu_de: str) -> None:
        """Mot thong diep sai con te hon khong co thong diep — no dan bai di nham huong."""
        assert YeuCauTho(the_tho="luc_bat", chu_de=chu_de).thong_diep == ""


class TestDanChuDeKhongCon:
    """Chu de KHONG duoc mang theo dan dan ("về", "chủ đề") o dau.

    LOI THAT, chay am tham nhieu ngay: "... lục bát về chủ đề uống nước nhớ nguồn" cho
    ra chu de "chủ đề uống nước nhớ nguồn", va de bai gui len model thanh
    "Chủ đề: chủ đề uống nước nhớ nguồn".

    No lo ra dung luc vet buoc 1 bat dau IN chu de ra man hinh — day la thu ma mot quy
    trinh quan sat duoc dung de lam, va la ly do §4 cua plan duoc lam truoc §5.
    """

    @pytest.mark.parametrize(
        ("cau", "mong_doi"),
        [
            ("Làm cho mình bài thơ lục bát về chủ đề uống nước nhớ nguồn", "uống nước nhớ nguồn"),
            ("Làm bài lục bát nói về chủ đề quê hương", "quê hương"),
            ("Viết bài thơ lục bát về mùa thu", "mùa thu"),
            ("Làm cho mình bài lục bát chủ đề cha mẹ", "cha mẹ"),
            ("Làm bài thơ lục bát tả cảnh mùa thu", "cảnh mùa thu"),
        ],
    )
    def test_cat_het_dan(self, cau: str, mong_doi: str) -> None:
        y = nhan_dien(cau)

        assert isinstance(y, YeuCauTho)
        assert y.chu_de == mong_doi

    @pytest.mark.parametrize(
        ("cau", "mong_doi"),
        [
            ("Làm bài thơ lục bát về tảng đá", "tảng đá"),
            ("Làm bài thơ lục bát về lang thang", "lang thang"),
            ("Làm bài thơ lục bát về vệ đường", "vệ đường"),
        ],
    )
    def test_KHONG_gam_vao_giua_mot_tu(self, cau: str, mong_doi: str) -> None:
        """`tả` trong "tảng", `là` trong "lang" — thieu ranh gioi tu thi chu de bi gam cut."""
        y = nhan_dien(cau)

        assert isinstance(y, YeuCauTho)
        assert y.chu_de == mong_doi
