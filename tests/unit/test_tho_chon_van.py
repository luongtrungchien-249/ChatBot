"""Giai doan 1: chon CHU VAN truoc, viet cau sau.

Bao model "dung ep van" da thu BON lan, bon cach, cung mot tran (`ngon ngu` 44%).
Van de nam o CO CHE SINH: model viet trai sang phai, toi vi tri van thi ca cau da
viet xong nen no khong con tu do chon NGHIA, chi con chon mot chu vua VAN.

Doi thu tu sinh thi o giai doan 1 model chi co MOT viec — chon chu co nghia. Va ta
kiem duoc ket qua do bang code TRUOC khi ton luot thu hai.
"""

from tho.chon_van import BoVan, doc_bo_van, yeu_cau_viet_bai


class TestDocBoVan:
    async def test_doc_duoc_bo_van_hop_le(self) -> None:
        bo = doc_bo_van("1|ta, hoa\n2|sương, vương, thương")

        assert bo == BoVan(nhom1=("ta", "hoa"), nhom2=("sương", "vương", "thương"))

    async def test_KIEM_BANG_CODE_va_loai_bo_van_khong_hiep(self) -> None:
        """Cho dat gia nhat cua ca thiet ke: mot bo van hong con TE HON khong co bo
        van nao, vi no ep model dat nhung chu KHONG hiep van vao dung vi tri van.
        Kiem o day mien phi, va no chan truoc khi ton luot goi thu hai.
        """
        assert doc_bo_van("1|sen, hồng\n2|sương, vương, thương") is None

    async def test_loai_khi_NHOM_HAI_co_mot_chu_lac(self) -> None:
        assert doc_bo_van("1|ta, hoa\n2|sương, vương, nắng") is None

    async def test_thieu_chu_thi_tra_None(self) -> None:
        assert doc_bo_van("1|ta\n2|sương, vương, thương") is None
        assert doc_bo_van("1|ta, hoa\n2|sương, vương") is None

    async def test_khong_doc_duoc_thi_tra_None(self) -> None:
        assert doc_bo_van("mình chọn: ta và hoa nhé") is None
        assert doc_bo_van("") is None

    async def test_bo_dau_cau_thua_va_khoang_trang(self) -> None:
        bo = doc_bo_van("1| ta , hoa .\n2| sương, vương , thương ")

        assert bo is not None
        assert bo.nhom1 == ("ta", "hoa")

    async def test_loai_cum_NHIEU_TU(self) -> None:
        """Vi tri van la MOT tieng. Mot cum hai tu dat vao do la sai so tieng."""
        assert doc_bo_van("1|ta, bông hoa\n2|sương, vương, thương") is None


class TestYeuCauVietBai:
    BO = BoVan(nhom1=("ta", "hoa"), nhom2=("sương", "vương", "thương"))

    async def test_chi_RO_chu_nao_o_vi_tri_nao(self) -> None:
        """Khong de model tu suy vi tri — do la mot buoc nua de sai."""
        y = yeu_cau_viet_bai(self.BO, "hoa sen")

        assert "câu 1, tiếng thứ 6" in y
        assert "câu 2, tiếng thứ 8" in y
        assert "ta" in y and "sương" in y

    async def test_noi_ro_DUNG_DOI_cac_chu_do(self) -> None:
        """Neu model duoc phep doi thi ta quay ve dung cho cu."""
        y = yeu_cau_viet_bai(self.BO, "hoa sen")

        assert "đừng đổi chúng" in y

    async def test_neu_LY_DO_chu_khong_chi_ra_lenh(self) -> None:
        """Model tuan mot lenh co ly do tot hon lenh tran — ket luan da do duoc."""
        assert "đã được chọn vì nghĩa" in yeu_cau_viet_bai(self.BO, "x")


class TestDaTatMacDinh:
    """Gia thuyet "chon van truoc" DA THU VA DA TAT. Test nay ghim viec do.

    Do 11/09/2026 tren 5 bai «hoa sen», gpt-4o-mini, thang 100 diem:

                      mot giai doan   hai giai doan
        tat dinh         38,7/45         27,9/45
        TONG            69,7/100        57,1/100
        ngon ngu          4,4/10          4,6/10
        sang tao          1,8/5           1,0/5

    Nguong nghiem thu la `ngon ngu >= 6,5` va `sang tao >= 2,5`. Truot xa, va con keo
    sap ca phan tat dinh: bai sinh ra dai 6 cau thay vi 4, cac chu van dat sai vi tri.
    Ep dung DUNG nhung chu do o DUNG nhung cho do la them mot rang buoc CUNG vao mot
    viec model von da lam khong xong — no buong ca hai.

    Code duoc giu lai vi gia thuyet van co ly voi model manh hon. Nhung bat lai mac
    dinh ma khong do lai thi test nay se do.
    """

    async def test_mac_dinh_TAT(self) -> None:
        from tho.sinh import CHON_VAN_TRUOC

        assert CHON_VAN_TRUOC is False
