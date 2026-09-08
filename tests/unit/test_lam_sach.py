"""Lam sach van ban trich xuat + bao cao chat luong truoc khi nap.

Rui ro lon nhat cua ca module `clean.py` KHONG phai lam sach thieu, ma la lam sach
QUA TAY: nuot mat noi dung that roi khong ai biet. Nen phan lon test o day la CA AM —
kiem tra thu KHONG duoc dung toi.

Khong I/O.
"""

import pytest

from knowledge.ingest.clean import Trang, ghep, lam_sach, trang_cua


class TestSoTrang:
    async def test_bo_so_trang_va_GIU_LAI_no(self) -> None:
        """Do duoc tren tep that: 88/88 trang bat dau bang chinh so trang do.

        Bo di la het nhieu; giu lai la dien duoc cot `page` von luon NULL.
        """
        trang = lam_sach([f"{i}\nNoi dung trang {i}." for i in range(1, 9)])

        assert [t.so for t in trang] == list(range(1, 9))
        assert all(not t.noi_dung.startswith(str(t.so)) for t in trang)

    async def test_nhan_ra_DO_LECH_giua_so_in_va_vi_tri_vat_ly(self) -> None:
        """Sach co bia va loi noi dau thi so in ra lech so vat ly. Gia dinh
        "trang vat ly 1 = trang in 1" se lam ca co che truot.
        """
        trang = lam_sach([f"{i + 10}\nThan trang." for i in range(1, 9)])

        assert [t.so for t in trang] == list(range(11, 19))

    async def test_KHONG_dung_toi_dong_bat_dau_bang_so_ma_co_chu(self) -> None:
        """Ca am quan trong: "1 cp coarsely chopped celery" bat dau bang chu so
        nhung KHONG phai so trang.
        """
        trang = lam_sach([f"1 cp bot mi\nTron deu buoc {i}." for i in range(8)])

        assert all(t.so is None for t in trang)
        # Dong dau giong nhau tren MOI trang van bi coi la header — dung theo dinh
        # nghia. Cai can chung minh o day la khong co so trang nao bi doc nham.
        assert all("Tron deu buoc" in t.noi_dung for t in trang)

    async def test_khong_co_quy_luat_thi_khong_bo_gi(self) -> None:
        tho = ["Trang mot.", "42\nTrang hai.", "Trang ba."] * 3
        trang = lam_sach(tho)

        assert all(t.so is None for t in trang)


class TestNoiDongGay:
    async def test_noi_dong_bi_PDF_ngat_giua_cau(self) -> None:
        """Do duoc tren tep that: 1.209 cho. Dong ngat nay lam chunker cat sai cho,
        vi no coi '\\n' la ranh gioi uu tien cao hon cau.
        """
        trang = lam_sach(
            ["1\nDocumentation License at the end\nof this document."]
            + [f"{i}\nTrang khac {i}." for i in range(2, 6)]
        )

        assert "end of this document" in trang[0].noi_dung

    @pytest.mark.parametrize(
        "giu_nguyen",
        [
            "1 cp celery\n5 or 6 carrots",  # dong sau bat dau bang CHU SO
            "INSTRUCTIONS:\ntron deu",  # dong truoc ket thuc bang ':'
            "Xong roi.\nbuoc tiep theo",  # dong truoc ket thuc bang '.'
            "Danh sach:\n- mot\n- hai",  # gach dau dong
        ],
    )
    async def test_KHONG_noi_khi_xuong_dong_la_co_y(self, giu_nguyen: str) -> None:
        """Danh sach nguyen lieu moi dong mot mon. Noi chung lai la pha cau truc ma
        buoc chunk dua vao.
        """
        trang = lam_sach(
            [f"1\n{giu_nguyen}"] + [f"{i}\nTrang khac {i}." for i in range(2, 6)]
        )

        assert trang[0].noi_dung.count("\n") == giu_nguyen.count("\n")


class TestChuCaiDoc:
    async def test_gop_chu_cai_dat_doc(self) -> None:
        trang = lam_sach(
            ["1\nC\nO\nN\nT\nE\nN\nT\nS\nContents"]
            + [f"{i}\nTrang khac {i}." for i in range(2, 6)]
        )

        assert "CONTENTS" in trang[0].noi_dung

    async def test_KHONG_gop_danh_sach_ngan(self) -> None:
        """Toi thieu bon dong. "A\\nB\\nC" co the la mot danh sach that."""
        trang = lam_sach(
            ["1\nA\nB\nC"] + [f"{i}\nTrang khac {i}." for i in range(2, 6)]
        )

        assert "ABC" not in trang[0].noi_dung


class TestHeaderFooter:
    async def test_bo_dong_lap_tren_da_so_trang(self) -> None:
        tho = [f"{i}\nSo tay noi bo 2026\nNoi dung {i}." for i in range(1, 11)]

        trang = lam_sach(tho)

        assert all("So tay noi bo 2026" not in t.noi_dung for t in trang)
        assert all(f"Noi dung {i}" in trang[i - 1].noi_dung for i in range(1, 11))

    async def test_KHONG_bo_dong_chi_xuat_hien_vai_lan(self) -> None:
        tho = [f"{i}\n" + ("Lap lai" if i <= 2 else f"Rieng {i}") for i in range(1, 11)]

        trang = lam_sach(tho)

        assert "Lap lai" in trang[0].noi_dung


class TestItTrang:
    """Tai lieu it trang KHONG duoc di qua bo do header/footer.

    Luat "lap tren >60% so trang" dung mot cach tam thuong khi co qua it trang: mot
    trang thi dong dau cua no luon dat 100%. Bug that: tai lieu mot trang bi bo mat
    ca dong dau lan dong cuoi — mat noi dung that, khong loi nao bao.
    """

    async def test_mot_trang_khong_bi_bo_dong_nao(self) -> None:
        trang = lam_sach(["1\nDong dau.\nDong giua.\nDong cuoi."])

        assert "Dong dau." in trang[0].noi_dung
        assert "Dong cuoi." in trang[0].noi_dung

    async def test_ba_trang_van_chua_do_header(self) -> None:
        trang = lam_sach([f"{i}\nTieu de chung\nThan {i}." for i in range(1, 4)])

        assert all("Tieu de chung" in t.noi_dung for t in trang)


class TestBanDoTrang:
    async def test_ghep_cho_ra_ban_do_dung(self) -> None:
        trang = [Trang(so=5, noi_dung="aaa"), Trang(so=6, noi_dung="bbb")]

        text, ban_do = ghep(trang)

        assert text == "aaa\n\nbbb"
        assert ban_do == [(0, 5), (5, 6)]

    async def test_tra_dung_so_trang_theo_vi_tri(self) -> None:
        ban_do = [(0, 5), (5, 6), (10, 7)]

        assert trang_cua(ban_do, 0) == 5
        assert trang_cua(ban_do, 4) == 5
        assert trang_cua(ban_do, 5) == 6
        assert trang_cua(ban_do, 99) == 7

    async def test_bo_qua_trang_rong_de_khong_lech_ban_do(self) -> None:
        text, ban_do = ghep([Trang(so=1, noi_dung="aa"), Trang(so=2, noi_dung="")])

        assert text == "aa"
        assert ban_do == [(0, 1)]
