"""Verifier THAT NGON BAT CU — so tieng, van, bang-trac, NIEM, DOI THANH.

HIEU CHUAN (ops/hieu_chuan_bat_cu.py) tren 7 bai co dien: 6/7 bai SACH, 1 loi tren 322
rang buoc = 0,31% bao nham. Nguong dat o docs/plan-rlvr-tho.md §4.2 la < 5%.

VI SAO NGUONG NAY KHAT KHE HON MOI BO DO KHAC TRONG DU AN: verifier nay se lam HAM
THUONG cho GRPO. Mot bo loc bao nham 17% thi loai oan 17% bai tot; mot ham THUONG bao
nham 17% thi DAY MODEL tranh nhung cai dung, va sai lech do tich luy qua tung buoc cap
nhat. Xem §3.1 cua plan.
"""

import pytest

from tho.bat_cu import (
    CAP_DOI,
    CAP_NIEM,
    bo_cuc,
    kiem_doi_thanh,
    kiem_niem,
    kiem_that_ngon_bat_cu,
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

THUONG_VO = (
    "Quanh năm buôn bán ở mom sông\n"
    "Nuôi đủ năm con với một chồng\n"
    "Lặn lội thân cò khi quãng vắng\n"
    "Eo sèo mặt nước buổi đò đông\n"
    "Một duyên hai nợ âu đành phận\n"
    "Năm nắng mười mưa dám quản công\n"
    "Cha mẹ thói đời ăn ở bạc\n"
    "Có chồng hờ hững cũng như không"
)


class TestThoChuanThiSACH:
    """Moi lan verifier bao Ba Huyen Thanh Quan sai luat, gan nhu chac chan la NO sai."""

    @pytest.mark.parametrize("bai", [QUA_DEO_NGANG, THUONG_VO])
    def test_khong_bao_loi_nao(self, bai: str) -> None:
        assert kiem_that_ngon_bat_cu(bai) == []


class TestSoTiengSoCau:
    def test_thieu_cau_thi_bao(self) -> None:
        bai = "\n".join(QUA_DEO_NGANG.split("\n")[:6])

        loi = kiem_that_ngon_bat_cu(bai)

        assert any(x.loai == "so_cau" for x in loi)

    def test_thua_tieng_thi_bao(self) -> None:
        cau = QUA_DEO_NGANG.split("\n")
        cau[2] = cau[2] + " thêm"

        loi = kiem_that_ngon_bat_cu("\n".join(cau))

        assert any(x.loai == "so_tieng" and x.cau == 3 for x in loi)

    def test_sai_so_tieng_thi_KHONG_kiem_tiep(self) -> None:
        """Sai so tieng thi "tieng 6" tro vao chu khac — moi phep kiem sau deu cho loi GIA."""
        cau = QUA_DEO_NGANG.split("\n")
        cau[2] = cau[2] + " thêm"

        loi = kiem_that_ngon_bat_cu("\n".join(cau))

        assert {x.loai for x in loi} == {"so_tieng"}

    def test_bai_trong(self) -> None:
        assert [x.loai for x in kiem_that_ngon_bat_cu("")] == ["so_cau"]


class TestNiem:
    def test_tho_chuan_thi_niem_dung(self) -> None:
        assert kiem_niem(QUA_DEO_NGANG) == []

    def test_bat_duoc_that_niem(self) -> None:
        """Doi tieng 2 cua cau 3 sang thanh TRAC -> cap niem 2-3 gay.

        Phai doi sang thanh TRAC that. Ban dau test nay dung "không" thay cho "khom",
        nhung CA HAI deu la thanh BANG — niem van dung, va test do vi mot ly do sai.
        """
        cau = QUA_DEO_NGANG.split("\n")
        cau[2] = "Lom khỏe dưới núi tiều vài chú"

        loi = kiem_niem("\n".join(cau))

        assert any("thất niêm" in x.mo_ta for x in loi)

    def test_dung_bon_cap_niem(self) -> None:
        assert CAP_NIEM == ((1, 8), (2, 3), (4, 5), (6, 7))


class TestDoiThanh:
    """CHI phan thanh. Phan tu loai KHONG lam, va khong duoc vao ham thuong."""

    def test_tho_chuan_doi_thanh_dung(self) -> None:
        assert kiem_doi_thanh(QUA_DEO_NGANG) == []

    def test_hai_cap_doi_la_thuc_va_luan(self) -> None:
        assert CAP_DOI == ((3, 4), (5, 6))

    def test_bat_duoc_khong_doi_thanh(self) -> None:
        cau = QUA_DEO_NGANG.split("\n")
        # Cau 4 lay nguyen thanh cua cau 3 -> khong con doi.
        cau[3] = cau[2]

        loi = kiem_doi_thanh("\n".join(cau))

        assert any("không đối thanh" in x.mo_ta for x in loi)


class TestVanNeoVaoDaSo:
    """Loi thiet ke ma chinh phep HIEU CHUAN bat duoc, ngay lan chay dau tien.

    Ban dau ham neo vao cuoi cau 2. Chay tren «Thu vinh»:  cao · hiu · vào · nào · Đào
    Bon tieng hiep o van "ao", rieng cau 2 lech — va verifier bao BA cau DUNG la sai.
    """

    THU_VINH = (
        "Trời thu xanh ngắt mấy tầng cao\n"
        "Cần trúc lơ phơ gió hắt hiu\n"
        "Nước biếc trông như tầng khói phủ\n"
        "Song thưa để mặc bóng trăng vào\n"
        "Mấy chùm trước giậu hoa năm ngoái\n"
        "Một tiếng trên không ngỗng nước nào\n"
        "Nhân hứng cũng vừa toan cất bút\n"
        "Nghĩ ra lại thẹn với ông Đào"
    )

    def test_chi_bao_dung_cau_LECH_chu_khong_bao_ba_cau_dung(self) -> None:
        loi = [x for x in kiem_that_ngon_bat_cu(self.THU_VINH) if x.loai == "van"]

        assert [x.cau for x in loi] == [2]

    def test_cau_1_that_van_KHONG_tinh_la_loi(self) -> None:
        """"That van" o cau dau la bien the duoc thua nhan."""
        cau = QUA_DEO_NGANG.split("\n")
        cau[0] = "Bước tới Đèo Ngang bóng xế chiều"

        loi = [x for x in kiem_that_ngon_bat_cu("\n".join(cau)) if x.loai == "van"]

        assert loi == []

    def test_mot_cau_giua_lech_van_thi_VAN_bat_duoc(self) -> None:
        cau = QUA_DEO_NGANG.split("\n")
        cau[5] = "Thương nhà mỏi miệng cái gia đình"

        loi = [x for x in kiem_that_ngon_bat_cu("\n".join(cau)) if x.loai == "van"]

        assert [x.cau for x in loi] == [6]


class TestBoCuc:
    def test_cat_dung_bon_phan(self) -> None:
        bc = bo_cuc(QUA_DEO_NGANG)

        assert list(bc) == ["đề", "thực", "luận", "kết"]
        assert bc["đề"].startswith("Bước tới")
        assert bc["kết"].endswith("ta với ta")

    def test_khong_du_tam_cau_thi_tra_RONG(self) -> None:
        assert bo_cuc("một câu") == {}
