"""Ho so tai lieu: nhan dien cau truc va sua ky tu bi trich xuat sai.

Bo test nay canh hai rui ro doi nhau, va rui ro thu hai moi la cai dang so:

  1. Khong nhan ra tai lieu co cau truc -> `section` NULL, trich dan khong noi duoc
     muc nao.
  2. Nhan ra NHAM, hoac sua NHAM -> lam hong mot van ban von dung. Doi mot loi hien
     thanh mot loi im lang la huong nguoc voi ca du an nay.

Khong I/O: moi thu chay tren chuoi dung san.
"""

import re

import pytest

from knowledge.ingest.chunk import chunk_document
from knowledge.ingest.profiles import (
    COOKBOOK_SLASHDOT,
    HO_SO,
    HoSo,
    ap_sua_ky_tu,
    nhan_dien,
)


def cong_thuc(ten: str, than: str = "INGREDIENTS:\n1 cp bot\nINSTRUCTIONS:\n1. Tron deu.") -> str:
    return f"\n{ten}\nfrom the test-only dept.\n{than}\n"


SACH = "Loi noi dau khong thuoc mon nao.\n" + "".join(
    cong_thuc(f"Mon so {i}") for i in range(1, 9)
)


class TestNhanDien:
    async def test_nhan_ra_sach_nau_an(self) -> None:
        assert nhan_dien(SACH) is COOKBOOK_SLASHDOT

    async def test_DUOI_NGUONG_thi_KHONG_nhan(self) -> None:
        """Luat trung tam cua ca module.

        Mot mau tinh co xuat hien vai lan trong tai lieu khac khong duoc phep doi
        cach cat cua ca tep. Nguong mac dinh la 5.
        """
        it = "".join(cong_thuc(f"Mon {i}") for i in range(3))

        assert COOKBOOK_SLASHDOT.so_lan_khop(it) == 3
        assert nhan_dien(it) is None

    async def test_van_ban_thuong_khong_khop_ho_so_nao(self) -> None:
        assert nhan_dien("Quy trinh duyet chi gom ba buoc. Buoc mot: lap de nghi.") is None

    async def test_rong(self) -> None:
        assert nhan_dien("") is None

    async def test_moi_ho_so_deu_bat_duoc_TEN_muc(self) -> None:
        """Group(1) di thang vao cot `section`. Ho so nao quen dat group se lam
        `section` thanh None ma khong bao loi — dung loai hong im lang.
        """
        for h in HO_SO:
            assert h.moc.groups >= 1, h.ten


class TestSuaKyTu:
    """Font `MrsEavesFractions` khai ToUnicode dong nhat, nen G/H/I/J/N/O la phan so
    bi doc thanh chu cai. Khong trinh trich xuat nao sua duoc — phai co bang tay.
    """

    @pytest.mark.parametrize(
        "vao,ra",
        [
            ("G cp butter", "¼ cp butter"),
            ("8 tbsp H cp", "8 tbsp ½ cp"),
            ("5 tbsp + 1 tsp N cp", "5 tbsp + 1 tsp ⅓ cp"),
            ("Dash/Pinch < J tsp", "Dash/Pinch < ⅛ tsp"),
            ("O cp (170 mL) cocoa", "⅔ cp (170 mL) cocoa"),
            ("I cp lukewarm milk", "¾ cp lukewarm milk"),
        ],
    )
    async def test_doi_dung_phan_so(self, vao: str, ra: str) -> None:
        assert ap_sua_ky_tu(vao, COOKBOOK_SLASHDOT)[0] == ra

    async def test_bat_duoc_ca_dang_dinh_lien_so(self) -> None:
        """"1H cp" = 1 1/2 cup. Khong co ranh gioi tu giua '1' va 'H', nen `\\b`
        khong du — phai dung `(?<![A-Za-z])`.
        """
        assert ap_sua_ky_tu("1H cp sizes", COOKBOOK_SLASHDOT)[0] == "1½ cp sizes"

    @pytest.mark.parametrize(
        "nguyen_ven",
        [
            "Vitamin H tablets",  # co chu trong bang, nhung KHONG co don vi do
            "Hepatitis G research",
            "Muc N cua chinh sach",
            "Nhom O duoc uu tien",
            "The letter H stands alone",
        ],
    )
    async def test_KHONG_dung_vao_chu_cai_that(self, nguyen_ven: str) -> None:
        """Ca quan trong nhat cua ca bo test.

        Chu 'H' trong van ban thuong la chu H that. Sua bua o day la lam hong mot
        van ban von dung, va khong ai phat hien ra.
        """
        assert ap_sua_ky_tu(nguyen_ven, COOKBOOK_SLASHDOT) == (nguyen_ven, 0)

    async def test_dem_dung_so_cho_da_sua(self) -> None:
        _, n = ap_sua_ky_tu("G cp bot, H tsp muoi, va mot chu H binh thuong", COOKBOOK_SLASHDOT)
        assert n == 2

    async def test_ho_so_khong_co_bang_thi_khong_doi_gi(self) -> None:
        tron = HoSo(ten="tron", moc=re.compile(r"(x)"), sua_ky_tu={})
        assert ap_sua_ky_tu("G cp butter", tron) == ("G cp butter", 0)


class TestCatMucTheoHoSo:
    async def test_section_mang_TEN_MON(self) -> None:
        chunks = chunk_document(SACH)
        ten = {c.section for c in chunks if c.section}

        assert "Mon so 1" in ten
        assert "Mon so 8" in ten

    async def test_phan_truoc_moc_dau_tien_KHONG_bi_mat(self) -> None:
        """Loi noi dau, muc luc, cac chuong khong phai cong thuc van phai duoc nap.
        Bo di la mat mot phan tai lieu ma khong ai bao.
        """
        assert any("Loi noi dau" in c.content for c in chunk_document(SACH))

    async def test_khong_chunk_nao_lan_sang_mon_khac(self) -> None:
        """Do duoc tren tep that: 17% -> 0%. Day la ly do ca thay doi nay ton tai."""
        chunks = chunk_document(SACH)
        for c in chunks:
            if c.section:
                assert c.content.count("from the test-only dept.") <= 1

    async def test_TIEU_DE_MARKDOWN_van_thang(self) -> None:
        """Markdown la cau truc TUONG MINH do nguoi viet dat ra; moc ho so la cau
        truc SUY RA. Cai tuong minh phai thang, neu khong mot tai liệu .md co lan
        cum 'from the ... dept.' se bi cat sai.
        """
        md = "# Chuong 1\n\nThan chuong mot.\n" + SACH

        chunks = chunk_document(md)

        assert any(c.section == "Chuong 1" for c in chunks)

    async def test_tai_lieu_thuong_giu_nguyen_hanh_vi_cu(self) -> None:
        thuong = "Doan mot noi ve quy trinh.\n\nDoan hai noi ve han muc."

        chunks = chunk_document(thuong)

        assert chunks
        assert all(c.section is None for c in chunks)
