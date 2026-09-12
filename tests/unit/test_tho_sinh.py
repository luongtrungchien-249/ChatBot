"""Vong sinh tho co kiem tra. Khong mang: `goi_model` la mot ham gia.

Ba rang buoc phai duoc CHUNG MINH, khong phai tin la co:
  1. gioi han so lan sinh lai  (muc tieu cua ca tinh nang la GIAM latency)
  2. noi RO sai o dau khi sinh lai
  3. KHONG BAO GIO im lang khi van con sai
"""

from tho.luat import kiem_luc_bat
from tho.prompt import nhac_sua, nhac_sua_be_chu, system_prompt, yeu_cau
from tho.sinh import (
    LOI_KHUNG,
    GoiModel,
    _cat_ve_khung_dung,
    doc_diem_chon,
    sinh_tho,
    so_cau_chep,
    tra_loi,
)

DUNG_LUAT = (
    "Trâu ơi ta bảo trâu này\n"
    "Trâu ra ngoài ruộng trâu cày với ta\n"
    "Cấy cày vốn nghiệp nông gia\n"
    "Ta đây trâu đấy ai mà quản công"
)
THUA_TIENG = (
    "Trâu ơi ta bảo trâu này nhé\n"
    "Trâu ra ngoài ruộng trâu cày với ta"
)


#: KHUNG 6-8 dung, chi SAI VAN: 'này' (tieng 6 cau luc) khong hiep van 'ta'
#: (tieng 6 cau bat). Dung de chung minh vong sua danh RIENG cho khung khong
#: dong vao khi khung da dung.
#:
#: KHONG dung «Công cha như núi Thái Sơn»: bai do nam trong bai mau cua prompt,
#: nen bo chan chep (`so_cau_chep`) se day no xuong cuoi bang xep hang.
SAI_VAN = (
    "Trâu ơi ta bảo trâu này\n"
    "Trâu ra ngoài ruộng cùng ta sớm chiều"
)


def model_tra(*ban: str) -> tuple[GoiModel, list[list[str]]]:
    """Ham gia: tra ve lan luot cac ban duoc dua vao, ghi lai moi luot."""
    lich_su: list[list[str]] = []

    async def goi(sys_prompt: str, luot: list[str]) -> str:
        lich_su.append(list(luot))
        return ban[min(len(lich_su) - 1, len(ban) - 1)]

    return goi, lich_su


def model_tra_nhieu(ban: list[str]) -> tuple[GoiModel, list[int]]:
    """Ham gia cho SINH SONG SONG: moi lan goi tra ve mot ban khac nhau."""
    dem = [0]

    async def goi(sys_prompt: str, luot: list[str]) -> str:
        i = dem[0]
        dem[0] += 1
        return ban[min(i, len(ban) - 1)]

    return goi, dem


class TestDuongHanhPhuc:
    async def test_dung_luat_ngay_lan_dau_thi_KHONG_sua(self) -> None:
        """Sua khi da dung la cong thang latency ma khong duoc gi.

        `chon_van_truoc=False` o ca lop nay: cac test o day kiem duong SINH va SUA,
        con giai doan chon van co lop rieng ben duoi.
        """
        goi, lich_su = model_tra(DUNG_LUAT)

        kq = await sinh_tho("luc_bat", "công cha nghĩa mẹ", goi, so_ban=1, chon_van_truoc=False)

        assert kq.bai_tho == DUNG_LUAT
        assert kq.con_loi == ()
        assert kq.so_lan_goi == 1
        assert len(lich_su) == 1

    async def test_sai_roi_sua_duoc_o_vong_sua(self) -> None:
        goi, _ = model_tra(THUA_TIENG, DUNG_LUAT)

        kq = await sinh_tho("luc_bat", "", goi, so_ban=1, chon_van_truoc=False)

        assert kq.con_loi == ()
        assert kq.so_lan_goi == 2

    async def test_SINH_SONG_SONG_lay_ban_it_loi_nhat(self) -> None:
        """Ba ban sinh cung luc, chon ban tot nhat — do tre bang MOT luot, khong ba."""
        te = "một hai ba" + chr(10) + "bốn năm"
        goi, _ = model_tra_nhieu([te, DUNG_LUAT, te])

        kq = await sinh_tho("luc_bat", "", goi, so_ban=3, so_lan_sua=0, chon_van_truoc=False)

        assert kq.bai_tho == DUNG_LUAT
        assert kq.so_lan_goi == 3


class TestGioiHanSoLan:
    async def test_KHONG_sinh_qua_so_lan_cho_phep(self) -> None:
        """Tran luot goi = so_ban + so_lan_sua + so_lan_sua_khung.

        Day la ngan sach latency cua tinh nang nay, khong phai mot con so tuy tien.
        """
        goi, _ = model_tra(THUA_TIENG)

        kq = await sinh_tho(
            "luc_bat", "", goi, so_ban=1, so_lan_sua=2, so_lan_sua_khung=0,
            chon_van_truoc=False,
        )

        assert kq.so_lan_goi == 3

    async def test_vong_KHUNG_chi_bung_ra_khi_khung_con_sai(self) -> None:
        """Khung la luat BAT BUOC nen no duoc cap rieng mot vong sua.

        THUA_TIENG sai KHUNG va model tra mai mot bai -> vong phu PHAI chay:
        1 ban + 1 vong thuong + 1 vong khung = 3 luot.
        """
        goi, _ = model_tra(THUA_TIENG)

        kq = await sinh_tho(
            "luc_bat", "", goi, so_ban=1, so_lan_sua=1, so_lan_sua_khung=1,
            chon_van_truoc=False,
        )

        assert kq.so_lan_goi == 3

    async def test_chi_con_loi_VAN_thi_KHONG_sua(self) -> None:
        """Sua loi van ton ~2 giay/bai de doi +0,3/20 diem ky vong. Xem `SUA_LOI_VAN`.

        Do theo CAP 11/09/2026 tren 10 bai: tot hon 1, khong doi 3, TE HON 6. Luat
        "giu ban tot nhat" chan duoc 6 ca te hon, nhung khong chan duoc do tre.
        """
        goi, _ = model_tra(SAI_VAN)

        kq = await sinh_tho("luc_bat", "", goi, so_ban=1, chon_van_truoc=False)

        # 1 ban, khong vong sua nao: khung da dung, chi con loi van.
        assert kq.so_lan_goi == 1
        assert kq.con_loi != ()
        assert all(x.loai not in LOI_KHUNG for x in kq.con_loi)

    async def test_loi_KHUNG_thi_VAN_sua(self) -> None:
        """Khung la luat bat buoc — o do mot vong goi model them la dang gia."""
        goi, _ = model_tra(THUA_TIENG)

        kq = await sinh_tho("luc_bat", "", goi, so_ban=1, chon_van_truoc=False)

        assert kq.so_lan_goi > 1

    async def test_khung_da_DUNG_thi_KHONG_vong_sua_nao_chay(self) -> None:
        """Ca vong thuong lan vong phu deu dung khi khung da dung.

        Vong phu danh RIENG cho khung. Vong thuong thi bi `SUA_LOI_VAN=False` tat —
        sua loi van ton ~2 giay/bai de doi +0,3/20 diem ky vong.

        Nen du cap ca hai vong, khong vong nao chay: dung mot luot goi.
        """
        goi, _ = model_tra(SAI_VAN)

        kq = await sinh_tho(
            "luc_bat", "", goi, so_ban=1, so_lan_sua=1, so_lan_sua_khung=1,
            chon_van_truoc=False,
        )

        assert kq.so_lan_goi == 1
        assert all(x.loai not in LOI_KHUNG for x in kq.con_loi)

    async def test_so_lan_bang_khong_thi_chi_goi_mot_lan(self) -> None:
        goi, _ = model_tra(THUA_TIENG)

        kq = await sinh_tho(
            "luc_bat", "", goi, so_ban=1, so_lan_sua=0, so_lan_sua_khung=0,
            chon_van_truoc=False,
        )

        assert kq.so_lan_goi == 1


class TestNoiRoSaiODau:
    async def test_luot_sinh_lai_mang_theo_TUNG_LOI_cu_the(self) -> None:
        """"cau 1 co 7 tieng, cau luc can 6" manh hon han "sai luat, lam lai"."""
        goi, lich_su = model_tra(THUA_TIENG, DUNG_LUAT)

        await sinh_tho("luc_bat", "", goi, so_ban=1, chon_van_truoc=False)

        nhac = lich_su[1][-1]
        assert "Câu 1" in nhac
        assert "7 tiếng" in nhac
        assert "cần 6" in nhac

    async def test_luot_sinh_lai_mang_theo_BAI_VUA_SAI(self) -> None:
        """Khong co bai cu thi model khong biet minh vua viet gi de ma sua."""
        goi, lich_su = model_tra(THUA_TIENG, DUNG_LUAT)

        await sinh_tho("luc_bat", "", goi, so_ban=1, chon_van_truoc=False)

        assert THUA_TIENG in lich_su[1]


class TestKhongImLang:
    async def test_het_luot_van_sai_thi_NOI_RA(self) -> None:
        """Tha mot bai sai luat ra ma noi la dung con te hon khong lam tho."""
        goi, _ = model_tra(THUA_TIENG)

        kq = await sinh_tho("luc_bat", "", goi, so_ban=1, chon_van_truoc=False)
        van_ban = tra_loi(kq)

        assert kq.con_loi != ()
        # Sai KHUNG thi phai noi la CHUA DUNG THE, khong noi giam thanh "chua chinh
        # duoc het luat": mot "cau bat" 7 tieng khong phai cau bat, va nguoi dung se
        # tuong minh dang cam mot bai luc bat.
        assert "CHƯA đúng thể lục bát" in van_ban

    async def test_dung_luat_thi_KHONG_them_ghi_chu(self) -> None:
        """Ca am: them ghi chu vao mot bai dung la lam nguoi dung nghi no sai."""
        goi, _ = model_tra(DUNG_LUAT)

        kq = await sinh_tho("luc_bat", "", goi, so_ban=1, chon_van_truoc=False)

        assert tra_loi(kq) == DUNG_LUAT

    async def test_giu_ban_IT_LOI_NHAT_chu_khong_phai_ban_cuoi(self) -> None:
        """Sinh lai khong bao dam tot hon. Tra ve ban te hon ban truoc la lam nguoi
        dung thiet.
        """
        te_hon = "một hai ba\nbốn năm"
        goi, _ = model_tra(THUA_TIENG, te_hon, te_hon)

        kq = await sinh_tho("luc_bat", "", goi, so_ban=1, chon_van_truoc=False)

        assert kq.bai_tho == THUA_TIENG


class TestPrompt:
    async def test_prompt_neu_LUAT_kem_VI_DU_va_VI_DU_SAI(self) -> None:
        """Vi du day manh hon luat — ket luan da do duoc cua du an nay. Va voi tho thi
        vi du phan dien dac biet quan trong: loi hay gap nhat la thua mot tieng.
        """
        p = system_prompt("luc_bat")

        assert "6 tiếng" in p and "8 tiếng" in p
        assert "Bài mẫu đúng luật" in p
        assert "VÍ DỤ SAI" in p
        # Loi dan chong chep. Bo CUONG CHE nam o `so_cau_chep` — day chi la lop ngoai,
        # va mot minh no khong du: xem `TestChanChepBaiMau`.
        assert "ĐỪNG chép" in p

    async def test_prompt_day_DU_LUAT_theo_dac_ta(self) -> None:
        """Dac ta luat luc bat cua nguoi dung, 12/09/2026 — day du trong prompt.

        Phep do KHONG ung ho ma cung khong bac bo. A/B n=40 moi ben, HAI luot, gop
        n=80: khong chi so luat nao nhich len co y nghia (`bang-trac 0 loi` 6/80 ->
        12/80, p=0,21), con `van` lech am o ca hai luot (-1,25). Do tre thi tot hon
        (-291 ms). Nguoi dung biet va van chon giu — day la dac ta cua ho.

        DUNG GO RA vi "do cho thay khong an". Xem ghi chu day du o tho/prompt.py.
        """
        p = system_prompt("luc_bat")

        # Muc 2 dac ta: so do van, VE RA thay vi mo ta bang loi.
        assert "x x x x x A x B" in p
        # Muc 2: van cung nhom, khong can trung khit.
        assert "sông - hồng - trong" in p
        # Muc 3: nhi tu luc phan minh — CA tieng 2, thu ban cu thieu.
        assert "nhị tứ lục phân minh" in p
        assert "nhất tam ngũ bất luận" in p
        # Muc 3: cau bat tieng 6 va 8 phai khac NHOM thanh.
        assert "KHÁC NHÓM" in p
        # Muc 4: nhip 2/4 cho cau luc (dac ta moi), 4/4 cho cau bat.
        assert "2/2/2 hoặc 2/4" in p
        assert "2/2/2/2 hoặc 4/4" in p
        # Muc 5: tieu doi — va no cung giai thich cac ngoai le tieng 2 trong Kieu.
        assert "TIỂU ĐỐI" in p
        assert "Mai cốt cách, tuyết tinh thần" in p

    async def test_prompt_co_CAU_DAT_va_CAM_XUC(self) -> None:
        """Muc 10 dac ta nguoi dung (cau dat) va cam xuc.

        CO TRONG PROMPT THEO QUYET DINH CUA NGUOI DUNG, sau khi da do va bao cao gia.
        A/B n=40 moi ben: hai muc nham vao khong nhuc nhich (`sang tao` +0,20 ± 0,34;
        `cam xuc` +0,05 ± 0,21), con `ngon ngu` -1,18 ± 0,74 [THAT] va do tre +552 ms
        [THAT].

        DUNG GO RA vi "do cho thay no khong an" — muon go thi phai hoi nguoi dung.
        Xem ghi chu day du o tho/prompt.py.
        """
        p = system_prompt("luc_bat")

        assert "CÂU ĐẮT" in p
        assert "CẢM XÚC" in p
        # Chong lai dung kieu hong da do: model dung chu la de "ra ve tho".
        assert "Cái đắt nằm ở Ý, không ở chữ" in p

    async def test_cau_vi_du_CAU_DAT_nam_trong_bo_chan_chep(self) -> None:
        """Them tho vao prompt ma khong chan thi model chep no.

        Prompt v3 da day: bon bai ca dao lam mau, model chep nguyen, va muc tang
        "ngon ngu +1,60" hoa ra la diem cua ca dao. Xem `TestChanChepBaiMau`.
        """
        from tho.prompt import CAU_DAT_MAU

        assert so_cau_chep(CAU_DAT_MAU) == 1

    async def test_prompt_ep_DO_DAI_bon_cau(self) -> None:
        """Bai 8 cau co BAY moi van, bai 4 cau chi co BA.

        Moi moi van la mot co hoi that bai doc lap, nen bai cang dai cang kho giu sach
        ca bai. Do HAI luot doc lap, n=40 moi luot moi ben, gop lai n=80:

                            8 cau        4 cau       p (Fisher)
            SACH ca van     1/80 =  1%   13/80 = 16%   0,0012  THAT
            dung KHUNG     79/80 = 99%   78/80 = 98%   1,0     khong mat gi

        "Sach" la thu nguoi dung THAY: bai sach gui thang, bai con loi kem mot cau
        xin loi.
        """
        p = system_prompt("luc_bat")

        assert "ĐỘ DÀI" in p
        assert "ĐÚNG 4 câu" in p

    async def test_DA_THU_bon_bai_mau_va_DA_QUAY_VE_MOT(self) -> None:
        """Prompt v3.1 — bon bai ca dao lam mau + "DÙNG CHỮ THƯỜNG" — DA THU VA DA BO.

        Gia thuyet nghe rat co ly: v2 DA CO "Ý → hình ảnh → chữ → vần" va DA CO vi du
        sai "tròn vương cuộc đời" ma `ngon ngu` van thap, nen thu day bang VI DU thay
        vi bang LOI DAN.

        A/B n=20 moi ben, cung bo chu de, chay HAI lan:

                               lan 1 (chua chan chep)  lan 2 (da chan chep)
            ngon ngu v2              4,65                    5,20
            ngon ngu v3              6,25                    3,75
            chenh                  +1,60 [THAT]            -1,45 [THAT]

        v2 giua hai lan cach nhau 0,55 — trong khoang tin cay. v3 cach nhau 2,50 —
        vuot xa. Thu duy nhat doi voi RIENG v3 giua hai lan: cac ban CHEP ca dao khong
        con duoc chon nua.

        Ca dao that thi tat nhien duoc `ngon ngu` cao. Muc tang cua v3 la diem cua ca
        dao, khong phai cua bot. Xem `TestChanChepBaiMau`.
        """
        from tho.prompt import _MAU_LUC_BAT

        assert len(_MAU_LUC_BAT) == 1

    async def test_bai_mau_trong_prompt_phai_DUNG_LUAT(self) -> None:
        """Ca am quan trong nhat cua tep prompt: day model bang mot bai mau sai luat
        la day no sai. Kiem bang chinh bo kiem tra.

        Duyet TUNG bai trong `_MAU_LUC_BAT` chu khong boc chuoi tu prompt: boc chuoi
        thi doi cach trinh bay la test im lang bo qua het cac bai mau.
        """
        from tho import kiem_luc_bat, kiem_that_ngon_tu_tuyet
        from tho.prompt import _MAU_LUC_BAT, _MAU_TNTT

        for bai in _MAU_LUC_BAT:
            assert kiem_luc_bat(bai) == [], bai
            # Va phai co mat trong prompt that — mot bai mau khong duoc chen vao thi
            # no chi la mot hang so dep.
            assert bai in system_prompt("luc_bat"), bai

        assert [
            x for x in kiem_that_ngon_tu_tuyet(_MAU_TNTT) if x.loai in {"so_tieng", "so_cau"}
        ] == []

    async def test_yeu_cau_co_va_khong_co_chu_de(self) -> None:
        assert "mùa thu" in yeu_cau("mùa thu")
        assert yeu_cau("") == "Làm một bài thơ."

    async def test_nhac_sua_VE_RA_cho_sai_chu_khong_chi_mo_ta(self) -> None:
        """Ban truoc chi liet ke mo ta, va do duoc 0/5 sau du ba vong sua. Ve ra thi
        model chi con MOT viec thuan ngu nghia.
        """
        from tho import kiem_luc_bat

        bai = "Xa xôi phương trời lạ nơi" + chr(10) + "Đêm đêm nhớ mẹ nhớ thời ấu thơ"
        loi = kiem_luc_bat(bai)

        nhac = nhac_sua(bai, loi)

        assert "huyền" in nhac
        assert "^" in nhac
        assert "Thanh BẰNG là ngang và huyền" in nhac
        assert "viết lại TOÀN BỘ" in nhac

    async def test_nhac_sua_loi_SO_TIENG_thi_khong_can_ve(self) -> None:
        from tho import Loi

        nhac = nhac_sua("một hai ba", [Loi(cau=1, loai="so_tieng", mo_ta="có 3 tiếng, cần 6")])

        assert "có 3 tiếng, cần 6" in nhac


class TestKhongEpBangTrac:
    """Bang-trac duoc KIEM nhung KHONG CHAN. Ket luan da do duoc, khong phai de tinh.

    Bo kiem tra bang-trac DUNG: 0% bao loi gia tren Truyen Kieu va ca dao. Van de nam
    o phia model. Do 11/09/2026, mot luot sinh moi bai:

                           so tieng   + van    + bang-trac
        gpt-4o-mini (n=8)    6/8       0/8       0/8
        gpt-5-mini  (n=1)    1/1       1/1       0/1

    KHONG model nao lam duoc — 0/9 tren ca hai. Neu van ep thi MOI bai deu ton du 3
    luot goi roi VAN sai: 3 lan chi phi, 3 lan do tre, doi lay mot cau "chua chinh
    duoc het luat". Do la san pham te hon han, va no danh thang vao muc tieu giam do
    tre cua chinh tinh nang nay.
    """

    SAI_BANG_TRAC = (
        # Dung so tieng, dung van, nhung tieng 4 cau 1 la thanh BANG (luat can trac).
        "Xa xôi phương trời lạ nơi\n"
        "Đêm đêm nhớ mẹ nhớ thời ấu thơ"
    )

    async def test_sai_bang_trac_thi_KHONG_bat_sinh_lai(self) -> None:
        goi, _ = model_tra(self.SAI_BANG_TRAC)

        kq = await sinh_tho("luc_bat", "", goi, so_ban=1, chon_van_truoc=False)

        assert kq.con_loi == ()
        assert kq.so_lan_goi == 1

    async def test_nhung_VAN_dem_loi_bang_trac_de_theo_doi(self) -> None:
        """Con so duy nhat noi duoc khi nao bat lai duoc tang luat nay."""
        goi, _ = model_tra(self.SAI_BANG_TRAC)

        kq = await sinh_tho("luc_bat", "", goi, so_ban=1, chon_van_truoc=False)

        assert len(kq.loi_bang_trac) > 0

    async def test_KHONG_them_ghi_chu_vi_loi_bang_trac(self) -> None:
        """Bang-trac khong chan thi cung khong duoc lam nguoi dung tuong bai bi sai."""
        goi, _ = model_tra(self.SAI_BANG_TRAC)

        kq = await sinh_tho("luc_bat", "", goi, so_ban=1, chon_van_truoc=False)

        assert tra_loi(kq) == self.SAI_BANG_TRAC

    async def test_sai_SO_TIENG_thi_VAN_chan(self) -> None:
        """Ca am: ha mot tang khong duoc lam hai tang kia thanh vo dung."""
        goi, _ = model_tra(THUA_TIENG)

        assert (await sinh_tho("luc_bat", "", goi, so_ban=1, chon_van_truoc=False)).con_loi != ()


class TestKhungLaLuatCung:
    """Khung 6-8 la luat BAT BUOC, khong phai mot muc diem tru.

    Mot "cau bat" 7 tieng khong phai cau bat — bai do khong con la luc bat. Sai van
    thi bai VAN la luc bat, chi doc khong xuoi. Hai muc do khac han nhau, nen moi phep
    chon ban deu xep hang (loi KHUNG, loi con lai) thay vi dem gop.
    """

    async def test_ban_DUNG_KHUNG_thang_ban_it_loi_hon_ma_sai_khung(self) -> None:
        """Day la loi da CHAY THAT ngay 11/09/2026.

        Cho chon ban dem gop moi loai loi lam mot. Ket qua tren 6 bai chay qua duong
        ong that: 0/6 bai dung khung — trong khi 65% so ban sinh ra von DA dung khung.
        Ta co san ban dat va da tu chon ban hong.
        """
        # SAI_VAN: dung khung, 1 loi van. THUA_TIENG: 1 loi khung, 0 loi van.
        # Dem gop thi hoa, va `min` se lay ban dau tien — tuc ban SAI KHUNG neu no
        # dung truoc. Xep hang theo khung thi SAI_VAN thang chac chan.
        goi, _ = model_tra_nhieu([THUA_TIENG, SAI_VAN])

        kq = await sinh_tho(
            "luc_bat", "", goi, so_ban=2, so_lan_sua=0, so_lan_sua_khung=0,
            chon_van_truoc=False,
        )

        assert kq.bai_tho == SAI_VAN
        assert all(x.loai not in LOI_KHUNG for x in kq.con_loi)

    async def test_vong_sua_KHONG_doi_lay_ban_sai_khung_du_it_loi_hon(self) -> None:
        """Vong sua tra ve mot ban sai khung nhung tong so loi it hon -> phai BO."""
        # Ban dau: dung khung, sai van. Ban sua: sai khung, khong loi nao khac.
        goi, _ = model_tra_nhieu([SAI_VAN, THUA_TIENG])

        kq = await sinh_tho(
            "luc_bat", "", goi, so_ban=1, so_lan_sua=1, so_lan_sua_khung=0,
            chon_van_truoc=False,
        )

        assert kq.bai_tho == SAI_VAN


class TestLuoiCuoiCungChoKhung:
    """Sinh nhieu ban chi cho ra XAC SUAT; cat thi TAT DINH.

    Do 11/09/2026: 65% moi ban dung khung -> 4 ban cho ~98,5%, va luot chay that cho
    5/6. Voi mot luat BAT BUOC thi 98,5% khong du — no van co nghia la thinh thoang
    nguoi dung nhan ve mot thu khong phai luc bat.

    Luc bat khong co do dai co dinh, nen bo di nhung cap hong va giu lai nhung cap
    dung van cho ra mot bai DUNG THE. Cai gia: bai ngan hon, mach y co the dut.
    """

    def test_bo_cap_sai_giu_cap_dung(self) -> None:
        # Cap 2 sai: cau luc chi co 5 tieng.
        bai = (
            "Lá rơi vàng ngập phố phường" + chr(10)
            + "Gió heo may nhè nhẹ vờn bay cao" + chr(10)
            + "Café nóng ấm bên nhau" + chr(10)
            + "Đường xưa bảng lảng sương mờ ước ao" + chr(10)
            + "Sắc trời tím lại mộng mơ" + chr(10)
            + "Người đi xa mãi vẫn chờ về đây"
        )

        ra = _cat_ve_khung_dung(bai)

        assert ra is not None
        assert "Café nóng ấm bên nhau" not in ra
        assert kiem_luc_bat(ra, kiem_bang_trac=False) == [] or all(
            x.loai not in LOI_KHUNG for x in kiem_luc_bat(ra, kiem_bang_trac=False)
        )

    def test_mot_dong_thua_o_DAU_lam_lech_het_cac_cap(self) -> None:
        """Model hay them mot dong tua de. Ghep cap tu cau 1 thi hong het ca bai.

        Nen phai thu ca hai cach ghep — tu cau 1 va tu cau 2 — roi lay cach cuu duoc
        nhieu cau hon.
        """
        bai = (
            "Thu Hà Nội" + chr(10)
            + "Lá vàng rơi xuống phố phường" + chr(10)
            + "Hà Nội thu đến, trời sang mây mù" + chr(10)
            + "Gió heo may nhẹ bên ru" + chr(10)
            + "Khẽ đưa hương cốm nồng nàn cà phê"
        )

        ra = _cat_ve_khung_dung(bai)

        assert ra is not None
        assert ra.split(chr(10))[0] == "Lá vàng rơi xuống phố phường"
        assert len(ra.split(chr(10))) == 4

    def test_duoi_hai_cap_thi_KHONG_cuu(self) -> None:
        """Cat mot bai xuong con hai cau la tra ve mot thu khong ai xin.

        Duoi nguong thi tha noi that la chua lam duoc — xem `CON_LOI_KHUNG`.
        """
        assert _cat_ve_khung_dung("Một câu sai" + chr(10) + "Hai câu cũng sai luôn") is None

    async def test_bai_khong_cuu_duoc_thi_VAN_noi_that(self) -> None:
        """Cat khong duoc thi KHONG im lang, va phai noi dung muc: chua dung THE."""
        goi, _ = model_tra(THUA_TIENG)

        kq = await sinh_tho(
            "luc_bat", "", goi, so_ban=1, so_lan_sua=0, so_lan_sua_khung=0,
            chon_van_truoc=False,
        )

        assert any(x.loai in LOI_KHUNG for x in kq.con_loi)
        assert "CHƯA đúng thể lục bát" in tra_loi(kq)


#: Khung 6-8 dung, sai dung MOT moi van — giong SAI_VAN nhung khac chu hoan toan.
#: Dung de tao mot the HOA ve diem luat, cho nguoi cham la nguoi quyet dinh.
SAI_VAN_2 = (
    "Chiều rơi trên bến sông xa" + chr(10)
    + "Con đò lặng lẽ trôi vào hoàng mây"
)


def nguoi_cham(diem: str) -> tuple[GoiModel, list[int]]:
    """Ham gia cho NGUOI CHAM. Tra ve `diem`, ghi lai so lan duoc goi.

    Tach hoan toan khoi `goi_model`: tu 11/09/2026 nguoi cham la mot MODEL KHAC — dung
    chung `gpt-4o-mini` thi no khong phan biet duoc bai nao hon bai nao. Xem
    `CHON_BANG_NGUOI_CHAM` trong tho/sinh.py.
    """
    dem = [0]

    async def cham(sys_prompt: str, luot: list[str]) -> str:
        dem[0] += 1
        return diem

    return cham, dem


class TestChonBangNguoiCham:
    """Xep hang cac ban bang THANG 100, khong chi dem loi luat.

    VI SAO: cho chon ban truoc day MU hoan toan voi `ngon ngu` va `sang tao`. Nang
    SO_BAN 4 -> 8 da lam lo dieu do ra — ep chon manh hon tren luat thi no chon dung
    nhung bai hy sinh nghia de lay van:

                     SO_BAN=4    SO_BAN=8
        van            12,4/20     17,1/20
        ngon ngu        5,5/10      3,7/10
        TONG           69,1/100    68,9/100

    Day la CHON, khong phai SUA — dung co che da do duoc la an.
    """

    async def test_nguoi_cham_quyet_dinh_khi_diem_luat_HOA(self) -> None:
        """Hai ban cung sai mot moi van. Nguoi cham cho ban 2 diem cao hon -> lay ban 2."""
        goi, _ = model_tra_nhieu([SAI_VAN, SAI_VAN_2])
        cham, _ = nguoi_cham("1|3|5" + chr(10) + "2|0|40")

        kq = await sinh_tho(
            "luc_bat",
            "",
            goi,
            so_ban=2,
            chon_van_truoc=False,
            chon_bang_nguoi_cham=True,
            cham_model=cham,
        )

        assert kq.bai_tho == SAI_VAN_2

    async def test_dao_diem_thi_dao_lua_chon(self) -> None:
        """Ca doi chung: doi diem thi ket qua phai doi theo, khong phai trung hop."""
        goi, _ = model_tra_nhieu([SAI_VAN, SAI_VAN_2])
        cham, _ = nguoi_cham("1|0|40" + chr(10) + "2|3|5")

        kq = await sinh_tho(
            "luc_bat",
            "",
            goi,
            so_ban=2,
            chon_van_truoc=False,
            chon_bang_nguoi_cham=True,
            cham_model=cham,
        )

        assert kq.bai_tho == SAI_VAN

    async def test_nguoi_cham_HONG_thi_giu_lua_chon_theo_luat(self) -> None:
        """Su co ha tang KHONG duoc bien thanh mot bai tho te.

        Nguoi cham tra ve rac -> `doc_diem_chon` tra None -> giu ban da chon theo luat.
        """
        goi, _ = model_tra_nhieu([SAI_VAN, DUNG_LUAT])
        cham, _ = nguoi_cham("xin loi minh khong cham duoc")

        kq = await sinh_tho(
            "luc_bat",
            "",
            goi,
            so_ban=2,
            chon_van_truoc=False,
            chon_bang_nguoi_cham=True,
            cham_model=cham,
        )

        assert kq.bai_tho == DUNG_LUAT
        assert kq.con_loi == ()

    async def test_KHONG_co_cham_model_thi_BO_QUA_buoc_chon(self) -> None:
        """Khong truyen nguoi cham thi khong co lua chon nao — giu xep hang theo luat.

        Quan trong voi test va voi moi noi goi `sinh_tho` ma khong co nguoi cham: buoc
        nay phai im lang bo qua, khong duoc no.
        """
        goi, _ = model_tra_nhieu([SAI_VAN, DUNG_LUAT])

        kq = await sinh_tho(
            "luc_bat", "", goi, so_ban=2, chon_van_truoc=False, chon_bang_nguoi_cham=True
        )

        assert kq.bai_tho == DUNG_LUAT

    async def test_MOT_ban_sach_khung_thi_KHONG_goi_nguoi_cham(self) -> None:
        """Mot ban thi khong co gi de chon — goi nguoi cham la lang phi thuan."""
        goi, _ = model_tra_nhieu([DUNG_LUAT])
        cham, dem = nguoi_cham("1|0|40")

        await sinh_tho(
            "luc_bat",
            "",
            goi,
            so_ban=1,
            chon_van_truoc=False,
            chon_bang_nguoi_cham=True,
            cham_model=cham,
        )

        assert dem[0] == 0

    async def test_KHUNG_van_la_bo_loc_CUNG(self) -> None:
        """Ban sai khung khong duoc vao vong cham, du nguoi cham co thich no den may.

        Mot ban khong phai luc bat thi hay den may cung khong dung duoc.
        """
        goi, _ = model_tra_nhieu([THUA_TIENG, SAI_VAN])
        cham, dem = nguoi_cham("1|0|40" + chr(10) + "2|9|0")

        kq = await sinh_tho(
            "luc_bat",
            "",
            goi,
            so_ban=2,
            chon_van_truoc=False,
            chon_bang_nguoi_cham=True,
            cham_model=cham,
        )

        assert kq.bai_tho == SAI_VAN
        # Chi con MOT ban sach khung -> khong co gi de chon.
        assert dem[0] == 0


class TestDocDiemChon:
    """Doc `n|<diem>`. Doi DU so dong — thieu mot dong la nguoi cham bo qua mot ban."""

    def test_doc_dung(self) -> None:
        assert doc_diem_chon("1|1|30" + chr(10) + "2|0|12", 2) == [30.0, 12.0]

    def test_thieu_mot_dong_tra_None(self) -> None:
        """Doan lay phan con lai se cho ra mot bang xep hang trong nhu that."""
        assert doc_diem_chon("1|1|30", 2) is None

    def test_rac_tra_None(self) -> None:
        assert doc_diem_chon("minh khong cham duoc", 2) is None

    def test_kep_vao_thang(self) -> None:
        """Nguoi cham hay tu bia thang rieng roi cho 100 o muc toi da 40."""
        assert doc_diem_chon("1|0|100" + chr(10) + "2|1|12", 2) == [40.0, 12.0]

    def test_diem_AM_lam_hong_ca_luot_cham(self) -> None:
        """`-5` khong dung dinh dang, nen ca luot cham bi coi la khong doc duoc.

        CO Y chat nhu vay: mot dong lac cho nghia la nguoi cham dang khong lam dung
        viec duoc giao, va tin phan con lai la doan mo. Tra None thi `sinh_tho` giu
        lua chon theo luat — mot lua chon te hon mot chut, nhung khong phai mot bang
        xep hang bia ra.
        """
        assert doc_diem_chon("1|1|30" + chr(10) + "2|0|-5", 2) is None


class TestChonBangNguoiChamDaTat:
    """Buoc "chon bang nguoi cham" DA THU BA LAN VA DA TAT. Test nay ghim viec do.

    Nguong nghiem thu: `ngon ngu >= 6,5`, `sang tao >= 2,5`, `p50 <= 3.500 ms`.

                                  ngon ngu  sang tao  van   TONG   p50
        khong chon (SO_BAN=8)        3,7      1,2    17,1   68,9   1.750 ms
        cham gpt-4o-mini "nghiem"    4,0      1,7    14,8   69,4   3.156 ms
        cham gpt-5-mini              4,8      1,5    11,0   67,2  24.609 ms

    Truot ca ba nguong. Va con so quan trong hon: NGAY CA khi nguoi cham phan biet
    duoc, `ngon ngu` cung chi len 4,8 — doi lay 6,1 diem van va 23 giay.

    Chon khong tao ra duoc chat luong khong co san trong cac ban.
    """

    def test_mac_dinh_TAT(self) -> None:
        from tho.sinh import CHON_BANG_NGUOI_CHAM

        assert CHON_BANG_NGUOI_CHAM is False


class TestChanChepBaiMau:
    """Bon bai ca dao trong prompt day duoc "dung chu thuong" — nhung model CHEP chung.

    Do 11/09/2026 tren 10 chu de voi prompt v3.1:

        chu de "cha mẹ"          -> chep 4/4 cau cua bai mau, giong 100%
        chu de "công ơn cha mẹ"  -> chep 4/4 cau, giong 100%
        tam chu de con lai       -> khong chep (giong nhat 58%, trung tu binh thuong)

    Chep CHI xay ra khi de bai trung chu de voi mot bai mau — nhung luc do no chep
    NGUYEN BAI, va bai do cham duoc 76,4/100. Tra ve nhu tho bot vua lam la noi doi.

    Prompt CO cau "đừng chép", nhung prompt khong cuong che duoc gi. Cuong che nam o
    code, y het luat tho nam o `luat.py` chu khong nam trong cau chu.
    """

    def test_dem_duoc_cau_chep_nguyen(self) -> None:
        from tho.prompt import _MAU_LUC_BAT

        assert so_cau_chep(_MAU_LUC_BAT[0]) == 4

    def test_doi_MOT_chu_van_la_chep(self) -> None:
        """Ca that: model tra ve bai mau voi "chảy ra" doi thanh "tuôn ra"."""
        bai = (
            "Công cha như núi Thái Sơn" + chr(10)
            + "Nghĩa mẹ như nước trong nguồn tuôn ra"
        )

        assert so_cau_chep(bai) == 2

    def test_tho_that_thi_KHONG_bi_bao_nham(self) -> None:
        """Bao nham thi ta loai chinh nhung bai tot — kieu hong im lang."""
        assert so_cau_chep(DUNG_LUAT) == 0
        assert so_cau_chep(SAI_VAN) == 0

    async def test_ban_CHEP_thua_ban_khong_chep_du_sai_van(self) -> None:
        """Mot bai chep lai ca dao khong phai bai bot lam ra.

        SAI_VAN sai mot moi van; ban chep thi dung luat tuyet doi. Xep hang van phai
        chon SAI_VAN — sai luat thi con la bai cua no, chep thi khong.
        """
        from tho.prompt import _MAU_LUC_BAT

        goi, _ = model_tra_nhieu([_MAU_LUC_BAT[0], SAI_VAN])

        kq = await sinh_tho(
            "luc_bat", "", goi, so_ban=2, so_lan_sua=0, so_lan_sua_khung=0,
            chon_van_truoc=False,
        )

        assert kq.bai_tho == SAI_VAN


#: Khung 6-8 dung, van dung, nhung co CHU BI BE: "ngọt ngao" thay vi "ngọt ngào".
#: Day la ca THAT tu luot do 12/09/2026 — bai chua no duoc cham VAN 20/20 tuyet doi.
BE_CHU = (
    "Như dòng nước chảy trong veo\n"
    "Tỏa hương thanh khiết ngọt ngao nụ cười"
)

#: Cung khung, cung van, nhung KHONG be chu nao.
KHONG_BE = (
    "Như dòng nước chảy trong veo\n"
    "Tỏa hương thanh khiết dịu dàng nụ cười"
)


class TestChuBiBeKhongDuocChon:
    """"Chi duoc chon lua cac tu co y nghia" — ban be chu bi LOAI, khong phai xep sau.

    Kieu hong: model lay mot tu that roi be no cho khop van.

        "ngọt ngào" -> "ngọt ngao"      "trong veo" -> "trong cao"

    Bai chua chung duoc cham VAN 20/20 TUYET DOI — tuc thang diem dang THUONG cho dung
    hanh vi pha nghia, va khau chon cung vay. Ba tang xu ly, giong het cach khung 6-8
    da len 100%: LOC -> SUA goi dich danh -> noi that.
    """

    async def test_ban_KHONG_be_thang_ban_be(self) -> None:
        goi, _ = model_tra_nhieu([BE_CHU, KHONG_BE])

        kq = await sinh_tho(
            "luc_bat", "", goi, so_ban=2, so_lan_sua=0, so_lan_sua_khung=0,
            so_lan_sua_be=0, chon_van_truoc=False,
        )

        assert kq.bai_tho == KHONG_BE

    async def test_dao_thu_tu_thi_ket_qua_KHONG_doi(self) -> None:
        """Ca doi chung: lua chon phai do CHU BI BE quyet dinh, khong do thu tu."""
        goi, _ = model_tra_nhieu([KHONG_BE, BE_CHU])

        kq = await sinh_tho(
            "luc_bat", "", goi, so_ban=2, so_lan_sua=0, so_lan_sua_khung=0,
            so_lan_sua_be=0, chon_van_truoc=False,
        )

        assert kq.bai_tho == KHONG_BE

    async def test_MOI_ban_deu_be_thi_goi_vong_SUA(self) -> None:
        """Loc khong con gi de chon thi phai sua, va loi nhac goi DICH DANH chu bi be."""
        goi, lich_su = model_tra_nhieu([BE_CHU, BE_CHU, KHONG_BE])

        kq = await sinh_tho(
            "luc_bat", "", goi, so_ban=2, so_lan_sua=0, so_lan_sua_khung=0,
            chon_van_truoc=False,
        )

        assert kq.bai_tho == KHONG_BE
        assert lich_su[0] == 3  # 2 ban + 1 vong sua

    async def test_loi_nhac_goi_DICH_DANH_tu_that(self) -> None:
        """Bao "co cum vo nghia" thi model phai tu doan. Ta BIET CHAC tu that la gi."""
        nhac = nhac_sua_be_chu(BE_CHU, [("ngọt ngao", "ngọt ngào")])

        assert "ngọt ngao" in nhac
        assert "ngọt ngào" in nhac
        # Va phai noi ro: va mot chu thi hong van, nen viet lai CA CAU.
        assert "VIẾT LẠI CẢ CÂU" in nhac


class TestBangVanGoiY:
    """Bang chu CO THAT, dua cho model chon khi bi tu van.

    Nguyen nhan goc cua viec be chu khong phai sai chinh ta: model viet toi vi tri van
    thi khong co san chu that nao vua hop van vua hop nghia, nen no be chu gan nhat.

    A/B n=40: khong hai gi (van -0,11 ± 2,04; do tre -180 ms; cum bi be 0 -> 0). Loi ich
    KHONG do duoc, vi cum bi be da la 0 o ca hai ben — bo loc ba tang da don sach moi ca
    DO DUOC. Bang van chi giup cho nhung ca KHONG do duoc ("rực rao", "trong cao").
    """

    async def test_prompt_luc_bat_co_bang_van(self) -> None:
        p = system_prompt("luc_bat")

        assert "CHỮ VẦN CÓ THẬT" in p
        # Dung nhung van tung bi be phai co mat.
        assert "-ao:" in p and "-ang:" in p

    async def test_dien_dat_la_GOI_Y_chu_khong_phai_rang_buoc(self) -> None:
        """Day la khac biet duy nhat giua bang nay va "chon van truoc" da lam sap diem
        tu 69,7 xuong 57,1/100. Cai do ep dung NHUNG chu do o DUNG nhung vi tri do.

        Do 12/09: ti le chu van nam trong bang chi nhich 60% -> 62%, khong vot len gan
        100% — model dang coi day la goi y. Neu con so do vot len thi phai doi cach viet
        hoac bo han; xem docs/plan-chon-tu-co-nghia.md muc 6.
        """
        p = system_prompt("luc_bat")

        assert "chỉ là vài ví dụ" in p
        assert "Dùng vần nào cũng được" in p

    async def test_KHONG_ghep_cho_that_ngon_tu_tuyet(self) -> None:
        """Tu tuyet co cau truc van khac (cuoi cau 1-2-4), va chua do duoc gi tren no."""
        assert "CHỮ VẦN CÓ THẬT" not in system_prompt("that_ngon_tu_tuyet")

    def test_bang_van_chi_chua_chu_THANH_BANG(self) -> None:
        """Van luc bat la van bang. Mot chu trac trong bang la day model gieo van sai."""
        from tho.bang_van import CHU_THEO_VAN
        from tho.luat import la_bang

        for van, ds in CHU_THEO_VAN.items():
            for chu in ds:
                assert la_bang(chu), f"{chu} (vần {van}) là thanh trắc"

    def test_bang_van_du_lon_de_co_lua_chon(self) -> None:
        """Mot nhom hai ba chu khong cho model lua chon gi.

        Tieu chi plan muc 5: >= 30 nhom co >= 8 chu. Do duoc 39/53.
        """
        from tho.bang_van import CHU_THEO_VAN

        assert sum(1 for ds in CHU_THEO_VAN.values() if len(ds) >= 8) >= 30
