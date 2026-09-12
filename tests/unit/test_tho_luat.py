"""Luat tho: thuan, khong mang, khong model.

Bo kiem tra nay se duoc dung de CHAM model va de LOC du lieu huan luyen, nen no phai
dung truoc da. Mot bo kiem tra chua hieu chuan se hoac bao loi gia (ep model sinh lai
vo ich -> TANG latency, dung thu dang muon giam), hoac bo lot loi that (tha tho sai
luat ra cho nguoi dung). Ca hai deu im lang.

Tap kiem thu vang o day la tho DA DUOC THUA NHAN — Truyen Kieu va ca dao. Moi lan bo
kiem tra bao mot cau Kieu la sai luat, gan nhu chac chan la BO KIEM TRA SAI, khong
phai Nguyen Du sai.
"""

from tho import (
    Loi,
    danh_so_tieng,
    kiem_luc_bat,
    kiem_nhip,
    kiem_that_ngon_tu_tuyet,
    la_bang,
    lay_van,
    tach_tieng,
    van_nhau,
)
from tho.luat import _tach_van


def _loai(loi: list[Loi]) -> set[str]:
    return {x.loai for x in loi}


class TestTachTieng:
    """Cho da sai mot lan trong nguyen mau, va no sai IM LANG."""

    async def test_doc_dung_nam_thanh_dieu(self) -> None:
        assert tach_tieng("ta")[1] == "ngang"
        assert tach_tieng("là")[1] == "huyen"
        assert tach_tieng("khéo")[1] == "sac"
        assert tach_tieng("trải")[1] == "hoi"
        assert tach_tieng("cõi")[1] == "nga"
        assert tach_tieng("mệnh")[1] == "nang"

    async def test_GIU_dau_mu_rau_trang_vi_chung_thuoc_NGUYEN_AM(self) -> None:
        """Hoi quy that ma test nay chan.

        Ban dau loc bang `unicodedata.category(k) != "Mn"`, tuc xoa MOI dau to hop —
        nuot luon dau mu (â), rau (ơ ư) va trang (ă). Hau qua: `dâu` gop voi `dau`,
        `người` gop voi `ngươi`. Bo kiem tra van khi do bao Truyen Kieu "dung luat"
        o CA che do chat che — dung vi mot ly do SAI.
        """
        assert tach_tieng("dâu")[0] == "dâu"
        assert tach_tieng("nghiêng")[0] == "nghiêng"
        assert tach_tieng("năm")[0] == "năm"
        # "ờ" = ơ + huyen. Bo dau thanh thi con "ơ" — GIU dau rau, bo dau huyen.
        assert tach_tieng("người") == ("ngươi", "huyen")

    async def test_bang_va_trac(self) -> None:
        assert la_bang("ta") is True
        assert la_bang("là") is True
        assert la_bang("khéo") is False
        assert la_bang("cõi") is False


class TestLayVan:
    async def test_bo_phu_am_dau(self) -> None:
        assert lay_van("ta") == "a"
        assert lay_van("nhau") == "au"
        assert lay_van("lòng") == "ong"

    async def test_phu_am_DAI_duoc_cat_truoc(self) -> None:
        """`ngh` phai duoc cat truoc `ng`, neu khong `nghiêng` se ra van `hiêng`."""
        assert lay_van("nghiêng") == "iêng"

    async def test_gi_va_qu_duoc_coi_la_phu_am_dau(self) -> None:
        """Cach phan tich truyen thong. La CHU Y, khong phai sot."""
        assert lay_van("quả") == "a"
        assert lay_van("giả") == "a"

    async def test_tieng_khong_co_phu_am_dau(self) -> None:
        assert lay_van("uống") == "uông"
        assert lay_van("ai") == "ai"


class TestVanNhau:
    async def test_van_chinh(self) -> None:
        assert van_nhau("ta", "là") is True
        assert van_nhau("dâu", "sâu") is True

    async def test_VAN_THONG_phai_duoc_chap_nhan(self) -> None:
        """Neu khong thi bo kiem tra loai thang Truyen Kieu — xem TestTruyenKieu."""
        assert van_nhau("nhau", "dâu") is True
        assert van_nhau("dâu", "đau") is True

    async def test_van_chinh_CHAT_CHE_thi_loai_van_thong(self) -> None:
        """Che do nay chi de nghien cuu, khong de cham."""
        assert van_nhau("nhau", "dâu", thong_van=False) is False

    async def test_KHONG_van_thi_bao_khong_van(self) -> None:
        """Ca am: noi long qua tay thi bo kiem tra thanh vo dung."""
        assert van_nhau("ta", "lòng") is False
        assert van_nhau("người", "đau") is False


class TestTruyenKieu:
    """Tap kiem thu vang. Bao sai o day = bo kiem tra sai."""

    KIEU = (
        "Trăm năm trong cõi người ta\n"
        "Chữ tài chữ mệnh khéo là ghét nhau\n"
        "Trải qua một cuộc bể dâu\n"
        "Những điều trông thấy mà đau đớn lòng"
    )

    async def test_bon_cau_mo_dau_DUNG_LUAT(self) -> None:
        assert kiem_luc_bat(self.KIEU) == []

    async def test_dung_luat_ca_khi_TAT_kiem_bang_trac(self) -> None:
        assert kiem_luc_bat(self.KIEU, kiem_bang_trac=False) == []


class TestCaDao:
    """Ca dao luc bat, cung la tho da duoc thua nhan."""

    async def test_cong_cha_nhu_nui_thai_son(self) -> None:
        bai = (
            "Công cha như núi Thái Sơn\n"
            "Nghĩa mẹ như nước trong nguồn chảy ra\n"
            "Một lòng thờ mẹ kính cha\n"
            "Cho tròn chữ hiếu mới là đạo con"
        )

        assert kiem_luc_bat(bai, kiem_bang_trac=False) == []

    async def test_bau_oi_thuong_lay_bi_cung(self) -> None:
        bai = (
            "Bầu ơi thương lấy bí cùng\n"
            "Tuy rằng khác giống nhưng chung một giàn"
        )

        assert kiem_luc_bat(bai, kiem_bang_trac=False) == []


class TestLucBatSai:
    async def test_thieu_tieng(self) -> None:
        bai = "Trăm năm trong cõi người\nChữ tài chữ mệnh khéo là ghét nhau"

        loi = kiem_luc_bat(bai)

        assert any(x.loai == "so_tieng" and x.cau == 1 for x in loi)

    async def test_thua_tieng(self) -> None:
        bai = "Trăm năm trong cõi người ta đây\nChữ tài chữ mệnh khéo là ghét nhau"

        assert any(x.loai == "so_tieng" and x.cau == 1 for x in kiem_luc_bat(bai))

    async def test_KET_THUC_bang_cau_luc_la_sai(self) -> None:
        """Yeu cau ro rang cua nguoi dung: bai phai ket thuc bang cau 8."""
        bai = (
            "Trăm năm trong cõi người ta\n"
            "Chữ tài chữ mệnh khéo là ghét nhau\n"
            "Trải qua một cuộc bể dâu"
        )

        assert any(x.loai == "so_cau" for x in kiem_luc_bat(bai))

    async def test_sai_van(self) -> None:
        bai = "Trăm năm trong cõi người ta\nChữ tài chữ mệnh khéo buồn ghét nhau"

        assert "van" in _loai(kiem_luc_bat(bai, kiem_bang_trac=False))

    async def test_sai_so_tieng_thi_BO_QUA_kiem_van_cau_do(self) -> None:
        """Cau sai so tieng thi "tieng 6" tro vao chu khac, nen moi loi van bao tren
        cau do deu la loi GIA — va loi gia se lam model di sua nham cho.
        """
        bai = "Trăm năm trong cõi người ta đây\nChữ tài chữ mệnh khéo là ghét nhau"

        loi = kiem_luc_bat(bai, kiem_bang_trac=False)

        assert _loai(loi) == {"so_tieng"}

    async def test_bai_trong(self) -> None:
        assert kiem_luc_bat("") != []
        assert kiem_luc_bat("   \n  ") != []


class TestThatNgonTuTuyet:
    async def test_bai_dung_luat(self) -> None:
        """Nam Quoc Son Ha, ban dich pho bien — 4 cau 7 tieng, van 'ư'."""
        bai = (
            "Sông núi nước Nam vua Nam ở\n"
            "Rành rành định phận tại sách trời\n"
            "Cớ sao lũ giặc sang xâm phạm\n"
            "Chúng bay sẽ bị đánh tơi bời"
        )

        loi = kiem_that_ngon_tu_tuyet(bai, kiem_bang_trac=False)

        assert [x for x in loi if x.loai == "so_tieng"] == []
        assert [x for x in loi if x.loai == "so_cau"] == []

    async def test_sai_so_cau(self) -> None:
        bai = "Sông núi nước Nam vua Nam ở\nRành rành định phận tại sách trời"

        assert any(x.loai == "so_cau" for x in kiem_that_ngon_tu_tuyet(bai))

    async def test_sai_so_tieng(self) -> None:
        bai = (
            "Sông núi nước Nam vua Nam ở đây\n"
            "Rành rành định phận tại sách trời\n"
            "Cớ sao lũ giặc sang xâm phạm\n"
            "Chúng bay sẽ bị đánh tơi bời"
        )

        assert any(x.loai == "so_tieng" and x.cau == 1 for x in kiem_that_ngon_tu_tuyet(bai))

    async def test_sai_so_tieng_thi_DUNG_LAI_khong_bao_loi_gia(self) -> None:
        bai = "một hai ba bốn năm sáu\nmột hai ba bốn năm sáu bảy\nba\nbốn"

        assert _loai(kiem_that_ngon_tu_tuyet(bai)) == {"so_tieng"}


class TestThongDiepLoi:
    """Thong diep di THANG vao luot sinh lai, nen no phai noi RO sai o dau.

    "Cau 3 co 7 tieng, cau luc can 6" manh hon han "sai luat, lam lai" — do la ket
    luan da do duoc cua du an nay, xem chan 7 trong agents/pipeline/stages/generate.py.
    """

    async def test_noi_ro_SO_TIENG_va_SO_CAN(self) -> None:
        bai = "Trăm năm trong cõi người ta đây\nChữ tài chữ mệnh khéo là ghét nhau"

        loi = kiem_luc_bat(bai)[0]

        assert "7 tiếng" in loi.mo_ta
        assert "cần 6" in loi.mo_ta

    async def test_noi_ro_HAI_TIENG_NAO_khong_van(self) -> None:
        bai = "Trăm năm trong cõi người ta\nChữ tài chữ mệnh khéo buồn ghét nhau"

        van = next(x for x in kiem_luc_bat(bai, kiem_bang_trac=False) if x.loai == "van")

        assert "'ta'" in van.mo_ta
        assert "'buồn'" in van.mo_ta


class TestTieng2LaNgoaiLe:
    """Luat bang-trac KHONG ep tieng 2 — ket luan da DO duoc, khong phai bo sot.

    Hieu chuan tren tho da duoc thua nhan (Truyen Kieu + ca dao, 12 cau):

        du 2-4-6(-8)             sai 1/12 cau
        bo tieng 2 -> 4-6(-8)    sai 0/12 cau

    Cau lam vo luat: "Nghia me nhu nuoc trong nguon chay ra" — tieng 2 la `mẹ`, thanh
    nang. Day la ngoai le quen thuoc cua luc bat bien the, pho bien den muc ep tieng 2
    se loai nham 25% so bai trong tap hieu chuan.

    Neu ai do them tieng 2 vao luat mac dinh, hai test duoi day se do.
    """

    CA_DAO = (
        "Công cha như núi Thái Sơn\n"
        "Nghĩa mẹ như nước trong nguồn chảy ra\n"
        "Một lòng thờ mẹ kính cha\n"
        "Cho tròn chữ hiếu mới là đạo con"
    )

    async def test_MAC_DINH_khong_ep_tieng_2(self) -> None:
        assert kiem_luc_bat(self.CA_DAO, kiem_bang_trac=True) == []

    async def test_nghiem_ngat_thi_ep_tieng_2_va_loai_ca_dao_nay(self) -> None:
        """Che do nay co that, nhung phai biet minh dang danh doi cai gi."""
        loi = kiem_luc_bat(self.CA_DAO, kiem_bang_trac=True, nghiem_ngat=True)

        assert any(x.loai == "bang_trac" and "tiếng 2" in x.mo_ta for x in loi)

    async def test_van_bat_duoc_sai_bang_trac_o_tieng_4_va_6(self) -> None:
        """Ca am: bo tieng 2 khong duoc lam ca tang bang-trac thanh vo dung."""
        bai = "Trăm năm trong cõi người ta\nChữ tài chữ mệnh khéo là ghét nhau"
        sai = bai.replace("cõi", "trời")  # tieng 4 tu trac thanh bang

        assert any(x.loai == "bang_trac" for x in kiem_luc_bat(sai))


class TestNghiThongVanChuaBat:
    """Nhung cap NGHI la thong van nhung CHUA co du bang chung de bat.

    Test nay GHIM hanh vi hien tai. No khong khang dinh hanh vi do DUNG — no chi bao
    dam khong ai bat/tat nham ma khong ai biet.

    Do 11/09/2026: bo kiem tra cham mot doan Truyen Kieu 38,3/45 vi bao `giờ` (vần ơ)
    khong hiep van `kề` (vần ê). Theo nguyen tac "bao sai tren tho chuan muc thi BO
    KIEM TRA SAI" thi dang le phai bat {ơ, ê}. CHUA BAT vi doan tho do duoc chep tu
    tri nho, chua doi chieu ban in — xem `_NGHI_THONG_VAN` trong tho/luat.py.
    """

    async def test_o_va_e_HIEN_TAI_khong_hiep_van(self) -> None:
        assert van_nhau("giờ", "kề") is False

    async def test_danh_sach_nghi_ngo_KHONG_duoc_dung_de_cham(self) -> None:
        """Ca am: `_NGHI_THONG_VAN` chi de ghi chep. Ngay khi no duoc noi vao
        `van_nhau()` thi test tren se do, va do la luc phai co bang chung tu corpus.
        """
        from tho.luat import _NGHI_THONG_VAN, _THONG_VAN

        dang_dung = [n for cac_nhom in _THONG_VAN.values() for n in cac_nhom]
        for nhom in _NGHI_THONG_VAN:
            assert nhom not in dang_dung



class TestKiemNhip:
    """Nhip — muc 5 cua ban dac ta. KIEM DUOC MOT PHAN, va phan do phai noi ro.

    Nhip 2/2/2 phu thuoc cho ngat TU ("Tram nam / trong coi / nguoi ta"), ma biet cho
    ngat tu thi can mot tu dien tu ghep tieng Viet — chua co. Nen ham nay khong kiem
    duoc nhip noi chung.

    Cai no kiem duoc, tat dinh va khong can tu dien: DAU PHAY do chinh nguoi viet dat.
    Dau phay la mot cho ngat co that. Roi vao vi tri LE thi cau gan nhu chac chan gay
    nhip, vi don vi nhip cua luc bat la chan (2/2/2, 2/2/2/2, 4/4) — tru nhip 3/3 cua
    cau luc.
    """

    async def test_phay_o_vi_tri_CHAN_la_hop_le(self) -> None:
        assert kiem_nhip("Lá xanh ôm ấp, dáng hồng kiêu sa") is None

    async def test_nhip_3_3_cua_cau_luc_van_hop_le(self) -> None:
        """Dac ta neu ro: cau luc co the ngat 3/3."""
        assert kiem_nhip("Cảnh nào cảnh, chẳng đeo sầu") is None

    async def test_phay_o_vi_tri_LE_bi_bao_gay_nhip(self) -> None:
        assert kiem_nhip("Đời người như, thể một đà vươn cao") == 3

    async def test_KHONG_co_phay_thi_tra_None_chu_khong_phai_DUNG_NHIP(self) -> None:
        """Ca am quan trong nhat. "Khong phat hien duoc gi" khac han "dung nhip" —
        gop hai cai lam mot se bien mot phep kiem MOT PHAN thanh mot loi bao dam sai.
        """
        assert kiem_nhip("Trăm năm trong cõi người ta") is None
        assert kiem_nhip("Đời người như thể một đà vươn cao") is None

    async def test_phay_o_CUOI_dong_khong_tinh(self) -> None:
        """Cuoi dong thi khong phai cho ngat GIUA cau."""
        assert kiem_nhip("Trăm năm trong cõi người ta,") is None

    async def test_dong_sai_so_tieng_thi_bo_qua(self) -> None:
        """Sai so tieng thi moi phep kiem nhip deu vo nghia — da co loi so_tieng lo."""
        assert kiem_nhip("một, hai ba bốn năm") is None


class TestDanhSoTieng:
    """Ve SO THU TU tung tieng ra, thay vi bao model tu dem.

    Do 11/09/2026: 35% so ban `gpt-4o-mini` sinh ra sai so tieng — tuc phep dem cua
    model khong dang tin. Bao no "cau nay co 7 tieng" la bat no dem lai bang dung cai
    kha nang vua hong. Ta thi dem dung 100%, tat dinh, mien phi.
    """

    def test_so_thang_hang_duoi_tung_tieng(self) -> None:
        ra = danh_so_tieng("Trăm năm trong cõi người ta").split(chr(10))

        assert len(ra) == 2
        # Moi so phai nam dung duoi chu cua no.
        for i, chu in enumerate(("Trăm", "năm", "trong", "cõi", "người", "ta"), start=1):
            cot = ra[0].index(chu)
            assert ra[1][cot:].startswith(str(i))

    def test_dem_dung_so_tieng(self) -> None:
        ra = danh_so_tieng("Khẽ đưa hương cốm, nồng nàn café")

        assert ra.split(chr(10))[1].split()[-1] == "7"

    def test_cau_rong_tra_ve_chuoi_rong(self) -> None:
        assert danh_so_tieng("   ") == ""


class TestAmTinhKhongDuocChapNhanNham:
    """Cac cap CHAC CHAN khong hiep van. Chung phai o `False` sau MOI lan noi bang.

    Vi sao lop nay ton tai: `ops/hieu_chuan_tho.py` do duoc ti le BAO LOI GIA (loai
    nham tho dung). Khong co gi do ti le nguoc lai — CHAP NHAN NHAM tho sai. Ma noi
    bang thi hai con so do di nguoc nhau: keo cai nay xuong la day cai kia len.

    Moi nhom mo them trong docs/plan-sua-bo-kiem-van.md muc 5 phai kem MOT ca duong
    tinh (tu tho da duoc thua nhan) VA mot ca am tinh dong dung cai cua no vua mo.
    """

    def test_nhom_theo_am_cuoi_KHONG_duoc_ro_ra_am_cuoi_khac(self) -> None:
        """`anh ~ inh` hiep van VI co am cuoi -nh. `ta ~ ti` thi khong.

        Day la ly do bang van thong phai khoa theo AM CUOI chu khong phai mot danh
        sach nhom toan cuc: cung mot cap nguyen am {a, i}, hai ket qua khac nhau.
        """
        for a, b in (("ta", "ti"), ("nhà", "nhì"), ("ba", "bi"), ("cá", "kí")):
            assert not van_nhau(a, b), f"{a} ~ {b} KHONG hiep van"

    def test_nhom_theo_am_cuoi_ng_KHONG_ro_ra_am_cuoi_trong(self) -> None:
        """`ung ~ ông` mo cho nhom -ng. `thu ~ tho` van phai la khong."""
        for a, b in (("thu", "tho"), ("cu", "co"), ("tù", "tò")):
            assert not van_nhau(a, b), f"{a} ~ {b} KHONG hiep van"

    def test_am_cuoi_phai_TRUNG_KHIT(self) -> None:
        """`an` va `ang` khong hiep van, du am chinh giong het."""
        for a, b in (("an", "ang"), ("tan", "tang"), ("mình", "mình" + "h"), ("tôi", "tôn")):
            assert not van_nhau(a, b), f"{a} ~ {b} KHONG hiep van"

    def test_bon_nhom_CHUA_GIAI_THICH_DUOC_van_dong(self) -> None:
        """Bon nhom nhieu dan chung nhat trong Kieu, va deu KHONG duoc mo.

        `{a, ươ}` co 69 dan chung voi am cuoi -ng — nhieu nhat trong tat ca. Nhung
        `đường ~ vàng` khong phai van tieng Viet. Dan chung chua giai thich duoc thi
        chua phai bang chung; xem plan muc 7.
        """
        for a, b in (
            ("đường", "vàng"),   # -ng  {a, ươ}   69 lan
            ("trang", "nhường"),
            ("vời", "ngài"),     # -i   {a, ơ}    35 lan
            ("bài", "mười"),     # -i   {a, ươ}   32 lan
            ("thưa", "cờ"),      # trống {ơ, ưa}  27 lan
        ):
            assert not van_nhau(a, b), f"{a} ~ {b} chua duoc mo — xem plan muc 7"

    def test_hai_tieng_khong_lien_quan(self) -> None:
        for a, b in (("hoa", "sen"), ("mùa", "thu"), ("trăng", "sao"), ("nhà", "cửa")):
            assert not van_nhau(a, b), f"{a} ~ {b} KHONG hiep van"


class TestF1BocDauCau:
    """Dau cau dinh vao tieng van lam hong hoan toan phep kiem.

    `tàn,` -> van `'an,'` -> tach thanh `(',', '')`, tuc lay dau phay lam nguyen am.
    """

    def test_dau_cau_KHONG_lot_vao_van(self) -> None:
        for tieng, van in (
            ("tàn,", "an"),
            ("đời.", "ơi"),
            ("mình!", "inh"),
            ("người\"", "ươi"),
            ("(sen)", "en"),
            ("thu…", "u"),
        ):
            assert lay_van(tieng) == van, tieng

    def test_mot_dau_phay_KHONG_duoc_pha_phep_kiem_van(self) -> None:
        assert van_nhau("nhan", "tàn,")
        assert van_nhau("nhan", "tàn")

    def test_cau_bat_ket_bang_dau_cham_van_hiep_van(self) -> None:
        """Ca thuc te: model gan nhu luon ket cau bang dau cham."""
        assert van_nhau("café.", "kê")
        assert van_nhau("đời.", "trời")


class TestF2PhuAmBocXongConRong:
    """`gi` la phu am dau, nhung voi chinh tieng `gì` thi boc xong khong con gi.

    Ban cu tra ve nguyen ca tieng (`'gi'`), roi `_tach_van` lay `g` lam nguyen am.
    Cach phan tich truyen thong: nguyen am `i` bi nuot vao chinh chu `i` cua `gi`.
    """

    def test_van_cua_gi_la_i(self) -> None:
        assert lay_van("gì") == "i"
        assert lay_van("gi") == "i"

    def test_khi_hiep_van_gi(self) -> None:
        """Truyen Kieu hiep van cap nay."""
        assert van_nhau("khi", "gì")
        # `kia ~ gì` la {i, ia} — nhom do duoc mo o buoc 6, xem
        # `TestNhomVanThongTheoAmCuoi`. O day chi kiem viec boc phu am `gi`.

    def test_gi_con_nguyen_am_thi_van_boc_binh_thuong(self) -> None:
        assert lay_van("giếng") == "êng"
        assert lay_van("gia") == "a"

    def test_qu_boc_xong_con_rong(self) -> None:
        assert lay_van("qu") == "u"

    def test_tieng_chi_gom_phu_am_thi_KHONG_tra_ve_chuoi_rong(self) -> None:
        """Chuoi rong lam moi phep so sanh sau do thanh dung — im lang va sai."""
        assert lay_van("tr") == "tr"
        assert lay_van("ngh") == "ngh"


class TestF3YeVaIeLaMot:
    """`yê`/`iê` va `ya`/`ia` la CACH VIET, khong phai van thong.

    Chu `y` duoc dung khi am tiet khong co phu am dau hoac sau am dem `u`. Khong doi
    cach doc, nen khong duoc doi ket qua hiep van.
    """

    def test_tien_va_yen_la_cung_mot_van(self) -> None:
        assert van_nhau("tiên", "yên")

    def test_chuan_hoa_KHONG_thay_the_cho_bang_van_thong(self) -> None:
        """`thêu` ~ `yêu` la `ê` voi `iê` — viec cua BANG VAN THONG, khong phai cua
        buoc chuan hoa nay. Ghim lai de khong ai nham hai thu do lam mot.
        """
        assert lay_van("yêu") == "yêu"          # chinh ta giu nguyen
        assert _tach_van(lay_van("yêu")) == ("iê", "u")   # chuan hoa o tang tach van
        assert _tach_van(lay_van("thêu")) == ("ê", "u")

    def test_duyen_va_hien(self) -> None:
        """Am dem `u` xen vao giua cung khong doi gi."""
        assert van_nhau("duyên", "hiền")

    def test_KHONG_noi_long_gi_them(self) -> None:
        """Chuan hoa cach viet khong duoc keo theo cap nao khac thanh hiep van."""
        assert not van_nhau("yên", "yên" + "g")
        assert not van_nhau("yêu", "yên")


class TestNhomVanThongTheoAmCuoi:
    """Ca DUONG TINH cho chin nhom mo ngay 11/09/2026, moi nhom mot dan chung Kieu.

    Doi voi `TestAmTinhKhongDuocChapNhanNham`: moi nhom o day mo mot cua, va lop kia
    ghim rang cua do khong mo ra rong hon muc dinh mo.
    """

    def test_anh_hiep_van_inh(self) -> None:
        """48 cặp trong Truyện Kiều."""
        assert van_nhau("mành", "tình")
        assert van_nhau("đành", "mình")

    def test_oi_hiep_van_uoi(self) -> None:
        """47 cặp."""
        assert van_nhau("nơi", "người")
        assert van_nhau("trời", "người")

    def test_ung_hiep_van_ong(self) -> None:
        """14 + 11 cặp."""
        assert van_nhau("chung", "hồng")
        assert van_nhau("phùng", "lòng")

    def test_ien_hiep_van_en(self) -> None:
        """16 + 9 cặp."""
        assert van_nhau("thiên", "trên")
        assert van_nhau("tiền", "đen")

    def test_ang_hiep_van_ung(self) -> None:
        """5 cặp."""
        assert van_nhau("trăng", "chừng")

    def test_am_tiet_mo_long_hon(self) -> None:
        """9 + 5 cặp. Âm tiết mở chỉ còn nguyên âm để hiệp vần."""
        assert van_nhau("thề", "nghì")
        assert van_nhau("kia", "gì")

    def test_nhom_moi_KHONG_ro_sang_am_cuoi_khac(self) -> None:
        """Cua vua mo phai dung do. Day la nua kia cua moi dong o tren."""
        assert van_nhau("mành", "tình")     # {a, i} CO, voi am cuoi -nh
        assert not van_nhau("ta", "ti")     # {a, i} KHONG, khi khong co am cuoi
        assert van_nhau("chung", "hồng")    # {o, u} CO, voi am cuoi -ng
        assert not van_nhau("thu", "tho")   # {o, u} KHONG, khi khong co am cuoi


class TestCumBiBe:
    """Bat cum bi BE CHO VAN — "ngọt ngào" -> "ngọt ngao".

    Kieu hong nang nhat con lai cua tinh nang lam tho. Bai chua no duoc cham VAN 20/20
    TUYET DOI, vi model be chu cho khop van — tuc thang diem dang THUONG cho hanh vi
    pha nghia.

    Hieu chuan 12/09/2026:
        chat=True      bao nham    1/3254 cau Truyen Kieu = 0,03%
        chat=False     bao nham 1559/3254 = 47,9%  -> khong dung duoc
    """

    def test_bat_duoc_cum_bi_be_dau(self) -> None:
        """Ca THAT tu luot do: "ngọt ngao" thay vi "ngọt ngào"."""
        from tho.tu_vung import cum_kha_nghi

        ra = cum_kha_nghi("Tỏa hương thanh khiết ngọt ngao nụ cười")

        assert ("ngọt ngao", "ngọt ngào") in ra

    def test_KHONG_bao_nham_tho_dung(self) -> None:
        """Bao nham thi ta loai chinh nhung bai tot — kieu hong im lang."""
        from tho.tu_vung import cum_kha_nghi

        for cau in (
            "Công cha như núi Thái Sơn",
            "Nghĩa mẹ như nước trong nguồn chảy ra",
            "Dịu dàng e ấp, hồn lương níu chân",
            "Trăm năm trong cõi người ta",
            "Mây thua nước tóc, tuyết nhường màu da",
        ):
            assert cum_kha_nghi(cau) == [], cau

    def test_che_do_LONG_da_do_va_khong_dung_duoc(self) -> None:
        """Ghim rang `chat=False` bao nham gan mot nua Truyen Kieu.

        No bao ca "Trăm năm trong cõi người ta". Test nay ton tai de khong ai bat no
        len mac dinh ma khong do lai.
        """
        from tho.tu_vung import cum_kha_nghi

        assert cum_kha_nghi("Trăm năm trong cõi người ta", chat=False) != []
        assert cum_kha_nghi("Trăm năm trong cõi người ta", chat=True) == []


class TestBoDoRongChiDeXepHang:
    """Bo do RONG bat them kieu diep am ("rực rỡ" -> "rực rao"), nhung bao nham 4,70%.

    RANH GIOI QUAN TRONG, va no la ranh gioi co that chu khong phai cach noi:

        CHAN  bao nham mot lan la loai han mot bai tot, khong lay lai duoc
              -> `cum_kha_nghi` (chat, 0,03%)
        CHON  bao nham chi doi thu tu uu tien giua cac ban
              -> `cum_nghi_be` (rong, 4,70%)

    Do theo CAP, HAI luot doc lap, n=40 moi luot:
        cum bi be / bai       0,713 -> 0,375   (-47%)
        bai KHONG co cum be   38/80 -> 55/80   p=0,0101  THAT
        van /20                9,94 -> 9,04    (-0,89, lech am ca hai luot)
    """

    def test_rong_bat_duoc_ca_chat_BO_SOT(self) -> None:
        """"rực rao" — doi ca van lan dau, `chat` khong bat duoc."""
        from tho.tu_vung import cum_kha_nghi, cum_nghi_be

        cau = "Nét vàng như ánh nguyệt đèn rực rao"

        assert cum_kha_nghi(cau) == []
        assert cum_nghi_be(cau) != []

    def test_rong_VAN_bat_duoc_kieu_be_dau(self) -> None:
        from tho.tu_vung import cum_nghi_be

        assert cum_nghi_be("Tỏa hương thanh khiết ngọt ngao nụ cười")

    def test_rong_KHONG_bao_tho_dung_pho_bien(self) -> None:
        """4,70% bao nham la ti le tren ca Kieu; cac cau quen thuoc phai sach."""
        from tho.tu_vung import cum_nghi_be

        for cau in (
            "Công cha như núi Thái Sơn",
            "Nghĩa mẹ như nước trong nguồn chảy ra",
            "Trăm năm trong cõi người ta",
            "Mây thua nước tóc, tuyết nhường màu da",
        ):
            assert cum_nghi_be(cau) == [], cau

    def test_bo_CHAN_van_dung_bo_do_CHAT(self) -> None:
        """Ghim ranh gioi: doi bo chan sang bo do rong se loai nham tho tot.

        `sinh_tho` loc cung bang `cum_kha_nghi`, xep hang bang `cum_nghi_be`.
        """
        import inspect

        from tho import sinh

        nguon = inspect.getsource(sinh.sinh_tho)
        assert "cum_kha_nghi(x[0])" in nguon, "bộ CHẶN phải dùng bộ dò CHẶT"


class TestThuHepBoDoRong:
    """Thu hep bo do rong bang LY DO, khong bang cach nhoi tu vao danh sach.

    VI SAO KHONG NHOI TU: 159 luot bao nham tren Kieu den tu 113 CUM KHAC NHAU — trung
    binh 1,4 luot moi cum. Phan bo thoai nhu vay nghia la von tu MO: them du 113 cum thi
    bao nham ve 0% TREN KIEU, nhung bai tho tiep theo se gap tu lay khac. Con so 0% do
    duoc tao ra bang dinh nghia.

    Hai cho thu hep o day thi tong quat hoa duoc:
        1. chi VI TRI VAN  — be chu xay ra VI BI TU VAN
        2. bo DIEP TU      — be chu khong bao gio tao ra hai tieng giong het nhau

    Do tren 1.627 cap Truyen Kieu:
        rong  150/1627 = 9,22%   ->   hep  35/1627 = 2,15%
    """

    def test_hai_ca_that_van_bi_bat(self) -> None:
        from tho.tu_vung import cum_nghi_be

        bai = (
            "Nét vàng như ánh nguyệt đèn rực rao" + chr(10)
            + "Tỏa hương thanh khiết ngọt ngao nụ cười"
        )
        cum = {c for c, _ in cum_nghi_be(bai)}

        assert "rực rao" in cum
        assert "ngọt ngao" in cum

    def test_bo_DIEP_TU(self) -> None:
        """"xa xa", "ngày ngày" la thu phap that. Be chu khong tao ra cap giong het."""
        from tho.tu_vung import cum_nghi_be

        bai = "Trông vời cố quốc xa xa" + chr(10) + "Ngày ngày trông ngóng cửa nhà ngày qua"

        assert cum_nghi_be(bai) == []

    def test_bo_cum_KHONG_o_vi_tri_van(self) -> None:
        """Diep am ngau nhien giua cau khong phai be chu.

        "thì thôi" o giua cau — bo. Cung cum do neu roi vao vi tri van thi van xet.
        """
        from tho.tu_vung import cum_nghi_be

        giua = "Thôi thì thôi có tiếc gì" + chr(10) + "Một lời đã trót thì đi cho rồi"

        assert all(c != "thì thôi" for c, _ in cum_nghi_be(giua))

    def test_ban_RONG_van_lay_duoc_de_kiem_rui_ro(self) -> None:
        """`hep=False` giu lai de kiem xem thu hep co lam lot ca that khong.

        Xem docs/plan-sua-bo-do-be-chu.md muc 7: mau ca that moi co hai, va ca hai deu
        o vi tri van. Neu ve sau gap ca be o GIUA cau thi phai xem lai.
        """
        from tho.tu_vung import cum_nghi_be

        bai = "Thôi thì thôi có tiếc gì" + chr(10) + "Một lời đã trót thì đi cho rồi"

        assert len(cum_nghi_be(bai, hep=False)) > len(cum_nghi_be(bai))


class TestChuanHoaCachDatDau:
    """Hai quy uoc dat dau thanh la CUNG MOT CHU — tra cuu phai khop ca hai.

        kieu cu   "hòa"  "hóa"  "thủy"  "lòa"
        kieu moi  "hoà"  "hoá"  "thuỷ"  "loà"

    Do 12/09/2026: `hiền hoà` bi bao la cum la trong khi `hiền hòa` DA CO trong danh
    sach. Do la loi TRA CUU, khong phai thieu tu — va them "hiền hoà" vao danh sach la
    va trieu chung chu khong sua benh.
    """

    def test_hai_cach_dat_dau_ra_cung_dang_chuan(self) -> None:
        from tho.tu_vung import chuan_hoa

        for cu, moi in (("hòa", "hoà"), ("hóa", "hoá"), ("thủy", "thuỷ"), ("lòa", "loà")):
            assert cu != moi, "hai chuỗi phải KHÁC nhau về byte"
            assert chuan_hoa(cu) == chuan_hoa(moi), f"{cu} vs {moi}"

    def test_tra_cuu_khop_ca_hai_kieu(self) -> None:
        from tho.tu_vung import cum_nghi_be

        for cach_viet in ("hiền hòa", "hiền hoà"):
            bai = f"Ai về nét mặt {cach_viet}" + chr(10) + "Một đời tảo tần vì gia đình ta"
            assert cum_nghi_be(bai) == [], cach_viet

    def test_chuan_hoa_GIU_thanh_dieu(self) -> None:
        """Chuan hoa cach dat dau, KHONG phai bo dau. "ngọt ngào" va "ngọt ngao" phai
        van khac nhau — neu khong thi bo do mat luon kha nang bat be dau.
        """
        from tho.tu_vung import chuan_hoa

        assert chuan_hoa("ngào") != chuan_hoa("ngao")


class TestGoiYPhaiCoDau:
    """Chu gia thang vao loi nhac sua ("từ thật là ...") nen no phai la chu THAT.

    Loi da mac 12/09/2026 khi them chuan hoa cach dat dau: bang tra luu dang CHUAN roi
    lay nguoc ra, nen loi nhac thanh "từ thật là ngọt ngao" — chinh cai chu vua bao la
    sai. Mot loi nhac nhu vay con te hon khong nhac.
    """

    def test_goi_y_giu_nguyen_dau(self) -> None:
        from tho.tu_vung import cum_kha_nghi

        ra = cum_kha_nghi("Tỏa hương thanh khiết ngọt ngao nụ cười")

        assert ra == [("ngọt ngao", "ngọt ngào")]

    def test_goi_y_KHONG_trung_voi_chu_bi_bao(self) -> None:
        """Ca am: goi y bang chinh chu sai thi vo dung."""
        from tho.tu_vung import cum_nghi_be

        bai = (
            "Nét vàng như ánh nguyệt đèn rực rao" + chr(10)
            + "Tỏa hương thanh khiết ngọt ngao nụ cười"
        )

        for sai, dung in cum_nghi_be(bai):
            assert sai != dung, sai


class TestTuDienDapBaoNhamChuKhongMoPhamViBat:
    """Tu dien Wiktionary dung de DAP BAO NHAM, KHONG de mo rong pham vi BAT.

    Khac biet do la tat ca, va no da duoc do. Ban dau nhoi ca hai nguon vao bang dieu
    khien viec BAT:

        bao nham tren Truyen Kieu   chat 0,00% -> 8,79%   hep 1,72% -> 13,95%

    Te hon TAM LAN. Doc cac ca bao nham thi ro ngay:

        "có hai" -> "có hại"      "nước đã" -> "nước đá"
        "mới là" -> "mới lạ"      "sao bằng" -> "sao băng"

    CA HAI VE DEU LA TU THAT, chi khac dau. Luat "khac moi dau => nghi be" chi dung khi
    von tu NHO va nham vao TU LAY. Voi tu dien day du thi cap khac-dau-deu-co-that co o
    khap noi, va luat mat hieu luc.

    Sau khi tach vai tro: chat 0,00% · hep 1,60% · do chinh xac tren tho bot ~40% -> ~81%.
    """

    def test_pham_vi_BAT_chi_tu_danh_sach_TU_SOAN(self) -> None:
        """`_THEO_DAU` dieu khien viec bat — no phai nho va duoc soan tay."""
        from tho.tu_vung import _THEO_DAU, _TU_SOAN, TU_GHEP

        assert len(_TU_SOAN) < 1000, "danh sách tự soạn phải NHỎ"
        assert len(TU_GHEP) > 10_000, "danh sách dập báo nhầm phải LỚN"
        assert len(_THEO_DAU) <= len(_TU_SOAN), "phạm vi bắt không được phình theo từ điển"

    def test_tu_dien_DAP_duoc_bao_nham(self) -> None:
        """Cum co trong tu dien thi khong duoc bao, du no khop mau nghi ngo."""
        from tho.tu_vung import TU_GHEP, cum_nghi_be

        # "vội vàng" co trong ca hai; "mải mê" co trong tu soan. Lay mot tu CHI co trong
        # ban trich Wiktionary de chung minh ban trich that su dang dap bao nham.
        chi_wikt = [t for t in ("bâng khuâng", "hờ hững", "lận đận") if t in TU_GHEP]
        assert chi_wikt, "cần ít nhất một từ để kiểm"
        for tu in chi_wikt:
            bai = f"Chiều nay {tu} một mình" + chr(10) + "Nhớ về quê cũ bóng hình ngày xưa"
            assert all(c != tu for c, _ in cum_nghi_be(bai)), tu

    def test_van_bat_duoc_hai_ca_that(self) -> None:
        """Dap bao nham KHONG duoc lam mat kha nang bat."""
        from tho.tu_vung import cum_nghi_be

        bai = (
            "Nét vàng như ánh nguyệt đèn rực rao" + chr(10)
            + "Tỏa hương thanh khiết ngọt ngao nụ cười"
        )
        cum = {c for c, _ in cum_nghi_be(bai)}

        assert "rực rao" in cum
        assert "ngọt ngao" in cum

    def test_tep_dan_xuat_ghi_ro_NGUON_va_GIAY_PHEP(self) -> None:
        """CC BY-SA doi GHI NGUON. Nghia vu do phai nam ngay trong tep, khong chi o README.

        Tep duoc SINH RA, nen neu bo sinh quen ghi thi khong ai thay — test nay thay.
        """
        from tho import tu_ghep_wiktionary

        doc = tu_ghep_wiktionary.__doc__ or ""

        assert "Wiktionary" in doc
        assert "CC BY-SA" in doc
        assert "kaikki.org" in doc
