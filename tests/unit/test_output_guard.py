"""OUTPUT RAILS — lop chan cuoi cung truoc khi cau tra loi roi he thong.

Truoc 08/09/2026 tang nay khong ton tai: moi lop phong thu deu nam o dau vao hoac
trong prompt, tuc la deu dua vao viec model chiu nghe loi. Da chung minh bang mot lan
chay that: go "so dien thoai cua toi la 0912345678, ban nhac lai giup toi" -> bot doc
lai nguyen van.

Bo test nay giu bon luat, VA giu ca hai bay da sap phai o lan viet dau tien:
thu tu chay, va backreference trong thay the bang ham.
"""

from agents.policy.output_guard import bo_markdown, co_markdown, kiem_dau_ra

KHOA = "sk-proj-abc123def456ghi789jkl"
DIEN_THOAI = "0912345678"
EMAIL = "nam@congty.vn"


class TestBiMat:
    """Khong co truong hop hop le nao de bot doc mot khoa API ra giua nhom chat."""

    async def test_khoa_api_bi_che(self) -> None:
        v = kiem_dau_ra(f"Theo tai lieu, khoa la {KHOA} nhe.")

        assert KHOA not in v.text
        assert "bi-mat" in v.da_can_thiep
        assert "khoa-sk" in v.loai_bi_mat

    async def test_che_CUNG_ke_ca_khi_nguoi_dung_tu_go_ra(self) -> None:
        """Khac han thong tin ca nhan: bi mat khong co ngoai le.

        Nguoi dung dan nham khoa vao khung chat la mot su co; bot doc lai la su co thu
        hai, va lan nay no nam trong lich su hoi thoai cua ca nhom.
        """
        v = kiem_dau_ra(f"Khoa cua ban la {KHOA}.", van_ban_nguoi_dung=f"khoa cua toi: {KHOA}")

        assert KHOA not in v.text

    async def test_chuoi_ket_noi_bi_che_ca_user_lan_pass(self) -> None:
        v = kiem_dau_ra("Dat postgres://bot:matkhauthat@db:5432/chatbot roi chay.")

        assert "matkhauthat" not in v.text
        assert "db:5432/chatbot" in v.text  # phan khong bi mat thi giu lai

    async def test_khoa_rieng_PEM(self) -> None:
        pem = "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----"
        assert "abc" not in kiem_dau_ra(f"Day: {pem}").text

    async def test_cau_sach_thi_khong_can_thiep_gi(self) -> None:
        v = kiem_dau_ra("Don hoan tien duoc xu ly trong 7 ngay lam viec.")

        assert v.da_can_thiep == ()
        assert v.text == "Don hoan tien duoc xu ly trong 7 ngay lam viec."


class TestThongTinCaNhan:
    """Che CO DIEU KIEN. Che tat ca se cho ra "so dien thoai cua ban la [so da an]" —
    bot tro nen vo dung, va nguoi dung se thoi dung no.
    """

    async def test_PII_bot_lay_tu_cho_khac_thi_CHE(self) -> None:
        v = kiem_dau_ra(
            f"Lien he anh Nam qua so {DIEN_THOAI} hoac {EMAIL}.",
            van_ban_nguoi_dung="cho minh so lien he bo phan ky thuat",
        )

        assert DIEN_THOAI not in v.text
        assert EMAIL not in v.text
        assert "ca-nhan" in v.da_can_thiep

    async def test_PII_cua_CHINH_nguoi_dung_thi_duoc_nhac_lai(self) -> None:
        """Day la ca lam mot bo loc mu tro nen vo dung."""
        v = kiem_dau_ra(
            f"Minh ghi nho so dien thoai cua ban la {DIEN_THOAI}.",
            van_ban_nguoi_dung=f"so dien thoai cua toi la {DIEN_THOAI}",
        )

        assert DIEN_THOAI in v.text
        assert v.da_can_thiep == ()

    async def test_chi_che_so_LA_trong_cung_mot_cau(self) -> None:
        """Nguoi dung go so cua minh; bot tra ve ca so do LAN mot so tu tai lieu."""
        khac = "0987654321"
        v = kiem_dau_ra(
            f"So cua ban la {DIEN_THOAI}, con cua anh Nam la {khac}.",
            van_ban_nguoi_dung=f"so cua toi la {DIEN_THOAI}",
        )

        assert DIEN_THOAI in v.text
        assert khac not in v.text

    async def test_can_cuoc_12_so(self) -> None:
        assert "001234567890" not in kiem_dau_ra("Can cuoc 001234567890 nhe.").text

    async def test_so_ngan_KHONG_bi_che_nham(self) -> None:
        """Nam chu so khong phai so dien thoai. Che nham thi moi con so trong tai lieu
        deu bien mat, va bot khong con tra loi duoc cau hoi nao co so lieu.
        """
        v = kiem_dau_ra("Ngan sach la 20000 dong, deadline 30/11, phong 502.")

        assert v.da_can_thiep == ()


class TestDinhDang:
    """Zalo khong render markdown: nguoi dung se thay `**dam**` nguyen van."""

    async def test_bo_dau_sao_giu_noi_dung(self) -> None:
        assert bo_markdown("**Quy trinh** gom ba buoc") == "Quy trinh gom ba buoc"

    async def test_gach_dau_dong_doi_thanh_dau_cham(self) -> None:
        ra = bo_markdown("- Truong nhom duyet\n- Ke toan kiem tra")

        assert "- " not in ra
        assert "Truong nhom duyet" in ra
        assert "Ke toan kiem tra" in ra

    async def test_bo_tieu_de_va_khoi_ma(self) -> None:
        assert "#" not in bo_markdown("## Muc hai\nnoi dung")
        assert "```" not in bo_markdown("```python\nx = 1\n```")

    async def test_van_xuoi_thuong_khong_bi_dong_toi(self) -> None:
        cau = "Thoi han la 7 ngay (theo So tay 2026, muc Hoan tien)."
        assert not co_markdown(cau)
        assert bo_markdown(cau) == cau


class TestThuTuChay:
    """BAY DA SAP PHAI o lan viet dau tien, giu lai de khong ai dao thu tu lai.

    Ban dau che truoc roi bo markdown sau. Dau che luc do la '***', va bo loc markdown
    coi '**' la chu dam nen no BOC MAT chinh cac dau che: 'sk-***' thanh 'sk-', va
    'postgres://***:***@' thanh 'postgres://:@'. Cau tra loi ra ngoai trong nhu bi cat
    xen, con bi mat thi da bi che that — nen loi nay khong lam lo gi, no chi lam cau
    tra loi vo nghia mot cach kho hieu.
    """

    async def test_che_bi_mat_KHONG_bi_bo_loc_markdown_an_mat(self) -> None:
        v = kiem_dau_ra(f"**Chu y**: khoa la {KHOA}")

        assert KHOA not in v.text
        assert "da an" in v.text
        assert "Chu y" in v.text

    async def test_dau_che_khong_dung_ky_hieu_markdown(self) -> None:
        """Dau che phai la thu bo loc markdown khong dong toi."""
        v = kiem_dau_ra(f"khoa {KHOA} va so {DIEN_THOAI}")

        assert "*" not in v.text

    async def test_thay_the_KHONG_de_lot_dau_tham_chieu(self) -> None:
        """Thay the bang HAM thi Python tra ve chuoi nguyen van, khong noi suy tham
        chieu nhom. Da troi that: nguoi dung nhan duoc "hoac @\\1 nhe".
        """
        v = kiem_dau_ra(f"Mail: {EMAIL}", van_ban_nguoi_dung="")

        assert chr(92) + "1" not in v.text


class TestTrichDan:
    """Ghi nhan, KHONG chan: mot cau tra loi dung nhung quen trich dan van huu ich hon
    mot cau bi nuot.
    """

    async def test_co_tai_lieu_ma_khong_neu_nguon_thi_bi_ghi_nhan(self) -> None:
        v = kiem_dau_ra("Thoi han la 7 ngay lam viec.", co_tai_lieu=True)

        assert v.thieu_trich_dan is True
        # Nhung cau tra loi van di ra nguyen ven.
        assert v.text == "Thoi han la 7 ngay lam viec."

    async def test_co_neu_nguon_thi_khong_ghi_nhan(self) -> None:
        v = kiem_dau_ra(
            "Thoi han la 7 ngay (theo So tay 2026, muc Hoan tien).", co_tai_lieu=True
        )
        assert v.thieu_trich_dan is False

    async def test_KHONG_co_tai_lieu_thi_khong_doi_trich_dan(self) -> None:
        """Cau chao hoi hay cau tra loi tu kien thuc chung khong can nguon."""
        assert kiem_dau_ra("Chao ban!", co_tai_lieu=False).thieu_trich_dan is False
