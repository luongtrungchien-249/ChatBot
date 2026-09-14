"""CHE DO 10 BUOC: cam be chu, di qua 10 buoc, va KHAI NGHIA tung chu van.

DANG BAT (QUY_TRINH_10_BUOC=True) — can thiep vao prompt DAU TIEN trong 8 lan co ket
qua LAP LAI DUOC o ca hai luot do. Con so day du nam canh hang so do trong sinh.py.

Tep nay ghim hai thu:
  1. ONG CAT dung — day la cho de hong am tham nhat. Model in mot phan NHAP truoc bai
     tho; cat sai thi `kiem_luc_bat` dem tung dong nhap thanh mot cau sai so tieng va
     MOI ban deu bi loai, tuc che do trong nhu lam tho te han trong khi ta chi doc nham.
  2. Sai dinh dang thi SAI AN TOAN, khong bao gio tra ve bai tho rong.
"""

import pytest

from tho.muoi_buoc import (
    CAM_BE_CHU,
    MOC,
    bo_dong_nhap,
    doc_cau_dat,
    doc_khai_nghia,
    tach_bai,
)
from tho.prompt import system_prompt
from tho.sinh import CAU_DAT, QUY_TRINH_10_BUOC, sinh_tho

from .test_tho_sinh import DUNG_LUAT

DAY_DU = f"""Ý: Cội nguồn → Cha ông → Hy sinh → Hòa bình → Nhớ nguồn
HÌNH ẢNH: mái đình, bến sông, luống cày, tiếng ve
CHỮ VẦN:
nguồn = nơi nước chảy ra
sông = dòng nước lớn
SOÁT: sạch
{MOC}
{DUNG_LUAT}"""


class TestOngCat:
    def test_cat_dung_phan_tho(self) -> None:
        assert tach_bai(DAY_DU) == DUNG_LUAT

    def test_KHONG_co_moc_thi_tra_NGUYEN_VAN_chu_khong_tra_rong(self) -> None:
        """Model quen in moc nhung van lam tho dung se xay ra.

        Bien no thanh mot bai tho rong la doi mot loi DINH DANG thanh mot SU CO.
        """
        assert tach_bai(DUNG_LUAT) == DUNG_LUAT

    @pytest.mark.parametrize("moc", ["BÀI THƠ:", "BAI THO:", "bài thơ:", "BÀI THƠ"])
    def test_nhan_moc_du_viet_hoa_thuong_hay_thieu_dau(self, moc: str) -> None:
        assert tach_bai(f"Ý: a → b\n{moc}\n{DUNG_LUAT}") == DUNG_LUAT

    def test_lay_moc_CUOI_CUNG(self) -> None:
        """Model doi khi nhac lai moc trong phan nhap. Lay moc cuoi moi dung."""
        raw = f"Ý: sẽ ghi sau {MOC} ở dưới\nHÌNH ẢNH: x\n{MOC}\n{DUNG_LUAT}"

        assert tach_bai(raw) == DUNG_LUAT

    def test_bo_dong_nhap_con_sot_giua_bai(self) -> None:
        """Mot dong nhap lot vao phan tho se bi dem thanh cau sai so tieng."""
        lan = f"CHỮ VẦN: nguồn = nơi nước ra\n{DUNG_LUAT}"

        assert bo_dong_nhap(lan) == DUNG_LUAT


class TestKhaiNghia:
    def test_doc_duoc_khai_nghia(self) -> None:
        assert doc_khai_nghia(DAY_DU) == {
            "nguồn": "nơi nước chảy ra",
            "sông": "dòng nước lớn",
        }

    def test_KHONG_nuot_phan_SOAT_vao_khai_nghia(self) -> None:
        assert "soát" not in doc_khai_nghia(DAY_DU)

    def test_khong_khai_thi_tra_RONG(self) -> None:
        assert doc_khai_nghia(DUNG_LUAT) == {}


class TestCamBeChu:
    @pytest.mark.parametrize(
        "cum", ["sơn hong", "giữ dào", "ngọt ngao", "không bao"]
    )
    def test_neu_dich_danh_bon_loi_THAT_da_do_duoc(self, cum: str) -> None:
        """Vi du BIA thi model coi la truong hop khong lien quan; vi du THAT thi no
        dung dang cai model vua lam."""
        assert cum in CAM_BE_CHU

    def test_co_luat_THOAT_chu_khong_chi_co_lenh_cam(self) -> None:
        """Cam ma khong chi duong ra thi model se be chu o cho khac."""
        assert "viết lại CẢ CÂU TRƯỚC" in CAM_BE_CHU


class TestPrompt:
    def test_TAT_thi_prompt_khong_doi_mot_chu(self) -> None:
        assert system_prompt("luc_bat", muoi_buoc=False) == system_prompt("luc_bat")

    def test_BAT_thi_them_ca_cam_be_chu_lan_quy_trinh(self) -> None:
        p = system_prompt("luc_bat", muoi_buoc=True)

        assert "CẤM BẺ CHỮ" in p
        assert "BƯỚC 5b" in p
        assert MOC in p


class TestChayThat:
    def test_dang_BAT(self) -> None:
        assert QUY_TRINH_10_BUOC is True

    async def test_sinh_tho_cat_dung_va_ghi_khai_nghia_vao_vet(self) -> None:
        async def goi(sys_prompt: str, luot: list[str]) -> str:
            return DAY_DU

        kq = await sinh_tho("luc_bat", "cha mẹ", goi, so_ban=1, muoi_buoc=True)
        buoc8 = next(v for v in kq.vet if v.buoc == "kiem_noi_dung")
        khai = next(c for c in buoc8.chi_tiet if c.ten == "khai nghĩa chữ vần")

        assert kq.bai_tho == DUNG_LUAT
        assert not kq.con_loi
        assert khai.dat is True
        assert "nguồn" in khai.tom_tat

    async def test_TAT_thi_vet_ghi_None_chu_khong_ghi_dat(self) -> None:
        """Che do tat thi khong co gi de khai — bao "dat" hay "khong dat" deu sai."""

        async def goi(sys_prompt: str, luot: list[str]) -> str:
            return DUNG_LUAT

        kq = await sinh_tho("luc_bat", "cha mẹ", goi, so_ban=1, muoi_buoc=False)
        buoc8 = next(v for v in kq.vet if v.buoc == "kiem_noi_dung")
        khai = next(c for c in buoc8.chi_tiet if c.ten == "khai nghĩa chữ vần")

        assert khai.dat is None

    async def test_model_KHONG_theo_dinh_dang_thi_van_lam_tho_duoc(self) -> None:
        """Sai an toan: khong co moc thi coi ca cau tra loi la bai tho."""

        async def goi(sys_prompt: str, luot: list[str]) -> str:
            return DUNG_LUAT

        kq = await sinh_tho("luc_bat", "cha mẹ", goi, so_ban=1, muoi_buoc=True)

        assert kq.bai_tho == DUNG_LUAT
        assert not kq.con_loi


class TestBuoc6bCauDat:
    """BUOC 6b — bat model viet CAU DAT truoc roi xay bai quanh no.

    VI SAO NHAM VAO DAY. `sang tao` la muc THAP NHAT cua ca he thong (1,15/5 = 23%), va
    tieu chi cham ghi thang "CHO DIEM TOI DA khi bai co mot CAU DAT" — tuc muc do thuc
    chat la mot bo do cau dat. Hieu chuan 14/09 tren tho kinh dien cho tran ~2,75/5.

    Va phep do phuong sai (buoc 0 cua plan) cho thay CHON KHONG CUU DUOC: 4 ban cua
    cung mot chu de co bien do sang tao trung binh chi 1,0 diem, va chon ban tot nhat
    theo THAN cung chi len 2,00 — van thieu 0,75 so voi ca dao, ma phai tra >= 4,8 giay.
    Nen phai nang chinh PHAN BO, va day la cach lam dieu do.
    """

    def test_TAT_thi_phieu_KHONG_co_buoc_6b(self) -> None:
        p = system_prompt("luc_bat", muoi_buoc=True, cau_dat=False)

        assert "BƯỚC 6b" not in p
        assert "CÂU ĐẮT:" not in p

    def test_BAT_thi_co_ca_buoc_lan_dong_dinh_dang(self) -> None:
        p = system_prompt("luc_bat", muoi_buoc=True, cau_dat=True)

        assert "BƯỚC 6b" in p
        assert "CÂU ĐẮT: <một câu 8 tiếng>" in p
        assert "ĐẮT Ở CHỖ:" in p

    def test_KHONG_con_cho_giu_cho_nao_lot_ra_prompt(self) -> None:
        """`_QUY_TRINH` la f-string co thoat `{{...}}`. Thoat sai thi nguoi doc prompt
        se thay `{buoc_6b}` nam giua phieu."""
        for c in (True, False):
            p = system_prompt("luc_bat", muoi_buoc=True, cau_dat=c)

            assert "{buoc_6b}" not in p
            assert "{dinh_dang_6b}" not in p

    def test_doc_duoc_cau_dat_va_ly_do(self) -> None:
        raw = (
            "CHỮ VẦN:\nnguồn = nơi nước ra\n"
            "CÂU ĐẮT: Người đi để lại bóng mình trên sân\n"
            "ĐẮT Ở CHỖ: cái bóng ở lại khi người đã đi\n"
            f"SOÁT: sạch\n{MOC}\n{DUNG_LUAT}"
        )

        assert doc_cau_dat(raw) == (
            "Người đi để lại bóng mình trên sân",
            "cái bóng ở lại khi người đã đi",
        )

    def test_khong_khai_thi_tra_RONG_ca_hai(self) -> None:
        assert doc_cau_dat(DUNG_LUAT) == ("", "")

    def test_CAU_DAT_khong_bi_nuot_vao_khai_nghia(self) -> None:
        """`CÂU ĐẮT:` dung ngay sau khoi CHU VAN — no phai DONG khoi do lai."""
        raw = (
            "CHỮ VẦN:\nnguồn = nơi nước ra\n"
            "CÂU ĐẮT: Người đi để lại bóng mình trên sân\n"
            f"SOÁT: sạch\n{MOC}\n{DUNG_LUAT}"
        )

        assert doc_khai_nghia(raw) == {"nguồn": "nơi nước ra"}

    def test_dong_CAU_DAT_lot_vao_bai_tho_thi_bi_bo(self) -> None:
        """Neu khong bo, `kiem_luc_bat` dem no thanh mot cau sai so tieng."""
        lan = f"CÂU ĐẮT: một câu nào đó\nĐẮT Ở CHỖ: vì nó hay\n{DUNG_LUAT}"

        assert bo_dong_nhap(lan) == DUNG_LUAT

    async def test_cau_dat_hien_trong_VET_buoc_8(self) -> None:
        raw = (
            "CHỮ VẦN:\nnày = chỉ cái ở gần\n"
            "CÂU ĐẮT: Người đi để lại bóng mình trên sân\n"
            "ĐẮT Ở CHỖ: cái bóng ở lại khi người đã đi\n"
            f"SOÁT: sạch\n{MOC}\n{DUNG_LUAT}"
        )

        async def goi(sys_prompt: str, luot: list[str]) -> str:
            return raw

        kq = await sinh_tho("luc_bat", "cha mẹ", goi, so_ban=1, muoi_buoc=True)
        buoc8 = next(v for v in kq.vet if v.buoc == "kiem_noi_dung")
        cd = next(c for c in buoc8.chi_tiet if c.ten == "câu đắt (bước 6b)")

        assert cd.dat is True
        assert "bóng mình trên sân" in cd.tom_tat


class TestBuoc6bDaDoVaDaTat:
    """Ket qua A/B 14/09 — ghim lai de khong ai bat lai ma khong doc con so."""

    def test_CAU_DAT_dang_TAT(self) -> None:
        """Truot ca hai cong: `sang tao` AM o ca hai luot, va hinh thuc tut that."""
        assert CAU_DAT is False

    def test_con_so_do_duoc_ghi_ngay_canh_co(self) -> None:
        import inspect

        import tho.sinh

        khoi = inspect.getsource(tho.sinh).split("CAU_DAT = False")[0]

        for dau_hieu in ("luot 1", "luot 2", "sang tao", "TRUOT CA HAI CONG"):
            assert dau_hieu in khoi, f"thiếu {dau_hieu!r} trong ghi chú của CAU_DAT"

    def test_mac_dinh_phieu_KHONG_con_buoc_6b(self) -> None:
        assert "BƯỚC 6b" not in system_prompt("luc_bat", muoi_buoc=True, cau_dat=CAU_DAT)
