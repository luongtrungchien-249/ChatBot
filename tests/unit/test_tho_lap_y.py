"""BUOC 2 — lap y thanh mot LUOT GOI RIENG. Co `LAP_Y`, mac dinh TAT.

Bo doc `doc_mach_y` NGHIEM NGAT co chu dich: tra None thi goi y BO QUA buoc nay va viet
mot mach nhu cu. Mot mach y hong con te hon khong co mach y — no chiem cho trong de bai
va dan model di sai. Day la cung bai hoc voi `doc_bo_van` trong chon_van.py.
"""

import pytest

from tho.lap_y import SO_Y, doc_mach_y, huong_dan, yeu_cau_lap_y, yeu_cau_viet_bai
from tho.sinh import LAP_Y, GoiModel, sinh_tho

from .test_tho_sinh import DUNG_LUAT

MACH = "Cội nguồn → Cha ông → Hy sinh → Hòa bình → Nhớ nguồn"


class TestMacDinhTat:
    def test_LAP_Y_dang_TAT(self) -> None:
        """Chua co phep do nao cho co nay. Bat mac dinh ma khong do la dung doan."""
        assert LAP_Y is False

    async def test_tat_thi_KHONG_ton_luot_goi_nao(self) -> None:
        goi, lich_su = model_tra_dem(DUNG_LUAT)

        kq = await sinh_tho("luc_bat", "cha mẹ", goi, so_ban=1, chon_van_truoc=False)
        lap = next(v for v in kq.vet if v.buoc == "lap_y")

        assert lap.da_chay is False
        assert lap.so_lan_goi == 0
        assert len(lich_su) == 1, "chỉ lượt sinh câu"


def model_tra_dem(*ban: str) -> tuple[GoiModel, list[list[str]]]:
    lich_su: list[list[str]] = []

    async def goi(sys_prompt: str, luot: list[str]) -> str:
        lich_su.append([sys_prompt, *luot])
        return ban[min(len(lich_su) - 1, len(ban) - 1)]

    return goi, lich_su


class TestDocMachY:
    def test_doc_duoc_mach_dung_dinh_dang(self) -> None:
        assert doc_mach_y(MACH) == MACH

    def test_chap_nhan_mui_ten_ASCII(self) -> None:
        assert doc_mach_y("Cội nguồn -> Cha ông -> Hy sinh -> Hòa bình -> Nhớ nguồn") == MACH

    def test_bo_dau_gach_dau_dong(self) -> None:
        assert doc_mach_y(f"- {MACH}") == MACH

    def test_tim_duoc_mach_giua_loi_dan_thua(self) -> None:
        raw = f"Đây là mạch ý cho chủ đề:\n{MACH}\nChúc bạn viết tốt!"

        assert doc_mach_y(raw) == MACH

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "Cội nguồn, cha ông, hy sinh",
            "Cội nguồn → Cha ông",
            "A → B → C → D → E → F",
            "Cội nguồn → Cha ông đã hy sinh rất nhiều cho đất nước → C → D → E",
        ],
    )
    def test_tra_None_chu_khong_doan_bua(self, raw: str) -> None:
        """Thieu y, thua y, hoac mot "y" dai ca cau (model dang viet tho chu khong lap y)."""
        assert doc_mach_y(raw) is None

    def test_dung_SO_Y_y(self) -> None:
        kq = doc_mach_y(MACH)

        assert kq is not None
        assert len(kq.split("→")) == SO_Y


class TestDeBaiCoMach:
    def test_mach_vao_de_bai_va_KHONG_ep_dung_het(self) -> None:
        """Ep dung het chinh la co che da lam CHON_VAN_TRUOC hong (69,7 -> 57,1)."""
        de = yeu_cau_viet_bai(MACH, "uống nước nhớ nguồn")

        assert MACH in de
        assert "uống nước nhớ nguồn" in de
        assert "ĐỪNG chép lại" in de
        assert "không bắt buộc dùng hết" in de

    def test_chu_de_rong_van_ra_de_bai_dung(self) -> None:
        de = yeu_cau_viet_bai(MACH, "")

        assert "Làm một bài thơ." in de
        assert MACH in de


class TestKhiBAT:
    async def test_bat_thi_ton_dung_MOT_luot_goi_them(self) -> None:
        goi, _ = model_tra_dem(MACH, DUNG_LUAT)

        kq = await sinh_tho(
            "luc_bat", "uống nước nhớ nguồn", goi, so_ban=1, chon_van_truoc=False, lap_y=True
        )
        lap = next(v for v in kq.vet if v.buoc == "lap_y")

        assert lap.da_chay is True
        assert lap.so_lan_goi == 1
        assert lap.tom_tat == MACH
        assert sum(v.so_lan_goi for v in kq.vet) == kq.so_lan_goi

    async def test_mach_y_thuc_su_di_vao_de_bai_sinh_cau(self) -> None:
        goi, lich_su = model_tra_dem(MACH, DUNG_LUAT)

        await sinh_tho("luc_bat", "cha mẹ", goi, so_ban=1, chon_van_truoc=False, lap_y=True)

        assert MACH in lich_su[1][-1], "lượt sinh câu phải mang theo mạch ý"

    async def test_mach_y_HONG_thi_BO_QUA_chu_khong_lam_hong_bai(self) -> None:
        """Khong doc duoc mach thi de bai quay ve dang cu, bai tho van ra binh thuong."""
        goi, _ = model_tra_dem("xin lỗi tôi không hiểu", DUNG_LUAT)

        kq = await sinh_tho(
            "luc_bat", "cha mẹ", goi, so_ban=1, chon_van_truoc=False, lap_y=True
        )
        lap = next(v for v in kq.vet if v.buoc == "lap_y")

        assert kq.bai_tho == DUNG_LUAT
        assert not kq.con_loi
        assert "BỎ QUA" in lap.tom_tat

    async def test_model_NEM_RA_o_buoc_lap_y_thi_van_lam_tho_duoc(self) -> None:
        lan = [0]

        async def goi(sys_prompt: str, luot: list[str]) -> str:
            lan[0] += 1
            if lan[0] == 1:
                raise RuntimeError("model chết ở bước lập ý")
            return DUNG_LUAT

        kq = await sinh_tho("luc_bat", "cha mẹ", goi, so_ban=1, chon_van_truoc=False, lap_y=True)

        assert kq.bai_tho == DUNG_LUAT
        assert sum(v.so_lan_goi for v in kq.vet) == kq.so_lan_goi


class TestHuongDan:
    def test_neu_dung_SO_Y_trong_chi_dan(self) -> None:
        assert f"Đúng {SO_Y} ý" in huong_dan()

    def test_yeu_cau_mang_chu_de(self) -> None:
        assert "mùa thu" in yeu_cau_lap_y("mùa thu")


class TestKhongNuotMachY:
    """Bat CA HAI co thi mach y KHONG duoc bien mat.

    `chon_van.yeu_cau_viet_bai` dung lai de bai TU DAU tu `chu_de`, nen no xoa mat mach
    y cua buoc 2. Ca hai co deu dang tat, nhung neu ai do bat ca hai thi buoc 2 se ton
    mot luot goi model roi bi nuot im lang — ton tien, khong bao loi, khong ai thay.
    """

    async def test_bat_ca_hai_thi_mach_y_van_toi_duoc_luot_sinh_cau(self) -> None:
        bo_van = "ay: này, cày, bay, hay\nà: ta, xa, hoa, qua"
        goi, lich_su = model_tra_dem(MACH, bo_van, DUNG_LUAT)

        await sinh_tho(
            "luc_bat", "cha mẹ", goi, so_ban=1, chon_van_truoc=True, lap_y=True
        )

        de_bai_sinh_cau = lich_su[-1][-1]
        assert MACH in de_bai_sinh_cau, "mạch ý bị bước 3 nuốt mất"


class TestKetQuaDaDoGhimLai:
    """Ghim ket qua A/B 13/09/2026 de khong ai bat lai ma khong doc con so."""

    def test_van_TAT_sau_khi_da_do(self) -> None:
        """Hai luot doc lap noi NGUOC nhau; do tre +1.000 ms. Xem hang so LAP_Y."""
        assert LAP_Y is False

    def test_con_so_do_duoc_ghi_ngay_canh_co(self) -> None:
        """Mot co tat ma khong ghi VI SAO thi lan sau se co nguoi bat len de thu lai.

        Ca bon co da tat trong tep nay (`SUA_LOI_VAN`, `CHON_VAN_TRUOC`,
        `CHON_BANG_NGUOI_CHAM`, `LAP_Y`) deu mang con so ngay canh chung. Test nay giu
        nep do cho `LAP_Y`.
        """
        import inspect

        import tho.sinh

        khoi = inspect.getsource(tho.sinh).split("LAP_Y = False")[0]

        for dau_hieu in ("luot 1", "luot 2", "DAO DAU", "ngon ngu"):
            assert dau_hieu in khoi, f"thiếu {dau_hieu!r} trong ghi chú của LAP_Y"
