"""Nhan dien yeu cau lam tho. Thuan, khong mang, khong model.

Bo nay phai SAI AN TOAN: khong nhan ra thi roi ve luong cu (bot van tra loi duoc),
con nhan nham thi bot di lam tho khi nguoi ta hoi quy dinh — te hon nhieu.

Nen so ca AM o day nhieu hon so ca DUONG, va do la co y.
"""

from tho.y_dinh import KhongPhaiTho, YeuCauTho, nhan_dien


class TestNhanRaYeuCauTho:
    async def test_noi_ro_the_luc_bat(self) -> None:
        y = nhan_dien("làm cho mình bài lục bát về mùa thu Hà Nội")

        assert isinstance(y, YeuCauTho)
        assert y.the_tho == "luc_bat"
        assert y.chu_de == "mùa thu Hà Nội"

    async def test_noi_ro_the_that_ngon_tu_tuyet(self) -> None:
        y = nhan_dien("viết giúp mình một bài thất ngôn tứ tuyệt về tiễn bạn đi xa")

        assert isinstance(y, YeuCauTho)
        assert y.the_tho == "that_ngon_tu_tuyet"

    async def test_chi_noi_tu_tuyet_cung_duoc(self) -> None:
        y = nhan_dien("sáng tác một bài tứ tuyệt nhé")

        assert isinstance(y, YeuCauTho)
        assert y.the_tho == "that_ngon_tu_tuyet"

    async def test_khong_noi_the_thi_mac_dinh_LUC_BAT(self) -> None:
        """Luc bat la the pho thong nhat voi nguoi Viet. Chon mac dinh thay vi hoi
        lai: SYSTEM_PROMPT cam hoi lai gan nhu tuyet doi, va o day ta co mot mac dinh
        hop ly chu khong phai dang bi ket.
        """
        y = nhan_dien("làm cho mình một bài thơ về cà phê sáng")

        assert isinstance(y, YeuCauTho)
        assert y.the_tho == "luc_bat"

    async def test_THE_CU_THE_thang_mau_chung(self) -> None:
        """"lam bai tho luc bat" phai ra luc_bat qua nhanh cu the, khong phai qua
        nhanh mac dinh — hai duong khac nhau, va se khac nhau hon khi them the moi.
        """
        y = nhan_dien("làm bài thơ thất ngôn tứ tuyệt")

        assert isinstance(y, YeuCauTho)
        assert y.the_tho == "that_ngon_tu_tuyet"

    async def test_chu_de_rong_khi_khong_noi(self) -> None:
        y = nhan_dien("làm cho mình một bài lục bát")

        assert isinstance(y, YeuCauTho)
        assert y.chu_de == ""


class TestKhongNhanNham:
    """Ca AM. Nhan nham te hon khong nhan ra."""

    async def test_hoi_ve_tho_KHONG_phai_yeu_cau_lam_tho(self) -> None:
        assert isinstance(nhan_dien("bài thơ này hay quá"), KhongPhaiTho)
        assert isinstance(nhan_dien("lục bát là thể thơ gì?"), KhongPhaiTho)

    async def test_cau_hoi_tai_lieu_KHONG_roi_vao_nhanh_tho(self) -> None:
        """Kieu hong te nhat: bot lam tho khi nguoi ta hoi quy dinh."""
        assert isinstance(nhan_dien("quy định nghỉ phép năm bao nhiêu ngày?"), KhongPhaiTho)
        assert isinstance(nhan_dien("làm sao cho chuối xanh bớt chát?"), KhongPhaiTho)
        assert isinstance(nhan_dien("luộc khoai sọ trong bao lâu?"), KhongPhaiTho)

    async def test_dong_tu_sang_tac_MA_KHONG_co_tu_tho(self) -> None:
        assert isinstance(nhan_dien("viết giúp mình email xin nghỉ"), KhongPhaiTho)
        assert isinstance(nhan_dien("làm cho mình bảng tổng hợp doanh thu"), KhongPhaiTho)

    async def test_tu_tho_MA_KHONG_co_dong_tu_sang_tac(self) -> None:
        """Khong co nhom dong tu thi "quy dinh ve tho ca cong ty" cung roi vao nhanh
        lam tho.
        """
        assert isinstance(nhan_dien("trong tài liệu có bài thơ nào không"), KhongPhaiTho)

    async def test_chuoi_rong(self) -> None:
        assert isinstance(nhan_dien(""), KhongPhaiTho)
        assert isinstance(nhan_dien("   \n "), KhongPhaiTho)

    async def test_KHOANG_CACH_qua_xa_thi_khong_tinh(self) -> None:
        """Dong tu va ten the tho cach nhau qua xa thi gan nhu chac chan khong phai
        mot yeu cau — no la mot cau ke co ca hai tu.
        """
        cau = "làm việc ở công ty này đã ba năm và mình rất thích đọc thể lục bát"

        assert isinstance(nhan_dien(cau), KhongPhaiTho)
