"""Kiem tra luat luc bat va that ngon tu tuyet. Thuan, khong I/O, khong goi model.

Chay trong micro-giay, nen goi bao nhieu lan cung duoc — ke ca trong mot vong sinh
lai, ke ca de loc du lieu huan luyen.

BA TANG LUAT, doc lap nhau:

    1. So tieng     tat dinh tuyet doi, khong co vung xam
    2. Bang/trac    tat dinh, chi phu thuoc dau thanh
    3. Van          CO vung xam — xem `van_nhau` va canh bao ve van thong

Tang 3 la cho de sai nhat, va no da sai that mot lan trong nguyen mau. Doc ky
docstring cua `tach_tieng` truoc khi sua bat cu thu gi o day.
"""

import unicodedata
from dataclasses import dataclass
from typing import Literal

ThanhDieu = Literal["ngang", "huyen", "sac", "hoi", "nga", "nang"]

#: Dau thanh o dang Unicode to hop (NFD). DUNG NAM ky tu nay, khong hon.
#:
#: Day la cho da sai mot lan. Ban dau viet `unicodedata.category(k) != "Mn"` de loc,
#: tuc xoa MOI dau to hop — va no nuot luon dau MU (â ê ô), dau RAU (ơ ư) va dau
#: TRANG (ă). Nhung dau do thuoc ve NGUYEN AM, khong phai thanh dieu.
#:
#: Hau qua rat im lang: `dâu` bi gop thanh `dau`, `người` thanh `ngươi`. Bo kiem tra
#: van khi do bao Truyen Kieu "dung luat" o CA che do chat che — dung vi mot ly do
#: SAI, do no da am tham coi `au` va `âu` la mot.
_DAU_THANH: dict[str, ThanhDieu] = {
    "̀": "huyen",
    "́": "sac",
    "̃": "nga",
    "̉": "hoi",
    "̣": "nang",
}

#: Thanh BANG (bang phang) va thanh TRAC (gay goc). Luat tho xet theo hai nhom nay.
_BANG: frozenset[str] = frozenset({"ngang", "huyen"})

#: Phu am dau, XEP DAI TRUOC NGAN de `ngh` khong bi `ng` cat mat.
#:
#: `gi` va `qu` nam trong danh sach: cach phan tich truyen thong coi chung la phu am
#: dau, nen `quả` co van `a` va `giả` co van `a`. Do la chu y, khong phai sot.
_PHU_AM_DAU: tuple[str, ...] = (
    "ngh", "tr", "ch", "gh", "kh", "nh", "ng", "ph", "th", "gi", "qu",
    "b", "c", "d", "đ", "g", "h", "k", "l", "m", "n", "p", "r", "s", "t", "v", "x",
)

#: AM CUOI, xep DAI TRUOC NGAN de `ng` khong bi `n` cat mat.
_AM_CUOI: tuple[str, ...] = ("ng", "nh", "ch", "m", "n", "p", "t", "c", "i", "y", "o", "u")

#: Cac cach VIET khac nhau cua CUNG MOT nguyen am. Day khong phai van thong.
#:
#: `yê` va `iê` la mot: `tiên`/`yên`, `thêu`/`yêu`, `duyên`/`hiền`. Chu `y` duoc dung
#: khi am tiet khong co phu am dau, hoac sau am dem `u` — thuan chinh ta, khong doi
#: cach doc. `ya`/`ia` cung vay.
#:
#: Khong chuan hoa thi `van_nhau('tiên', 'yên')` tra False — hai tieng van HET NHAU.
#: Rieng cho nay go duoc 24 cap trong Truyen Kieu ma KHONG noi long gi ca: no chi thoi
#: coi mot chu la hai.
_VIET_KHAC_NHAU_CUNG_AM: dict[str, str] = {"yê": "iê", "ya": "ia"}

#: AM CHINH la nguyen am doi, xep DAI TRUOC NGAN.
_AM_CHINH_DOI: tuple[str, ...] = ("ươ", "uô", "iê", "yê", "ưa", "ua", "ia", "ya")

#: Cac nhom AM CHINH duoc coi la THONG VAN trong tho truyen thong.
#:
#: BAT BUOC phai co. Hai bang chung tu tho DA DUOC THUA NHAN:
#:
#:   Truyen Kieu   `nhau` (a + u)  hiep van  `dâu` (â + u)      -> nhom {a, â, ă}
#:   Ca dao        `Sơn`  (ơ + n)  hiep van  `nguồn` (uô + n)   -> nhom {ơ, uô}
#:
#: Cai thu hai la ly do phai tach AM CHINH khoi AM CUOI. Mo hinh cu so sanh ca phan
#: van va chi cho phep doi MOT ky tu, nen `ơn` va `uôn` (khac ca do dai) khong the
#: hiep van — va bo kiem tra loai thang mot cau ca dao ai cung thuoc.
#:
#: BANG NAY CHUA DAY DU. No moi duoc hieu chuan tren so tho nam trong
#: tests/unit/test_tho_luat.py. Muon them nhom thi phai co DAN CHUNG tu tho da duoc
#: thua nhan, va them ca ca kiem thu — dung them vi "nghe co ve hiep van".
#: KHOA LA AM CUOI. `"*"` = dung voi moi am cuoi.
#:
#: VI SAO KHOA THEO AM CUOI, khong phai mot danh sach nhom toan cuc:
#:
#:     `anh` va `inh` hiep van — 48 dan chung trong Truyen Kieu.
#:     `ta`  va `ti`  thi khong.
#:
#: Cung mot cap nguyen am {a, i}, hai ket qua khac nhau, va cai phan biet chung la AM
#: CUOI `-nh`. Mot bang toan cuc khong dien dat duoc dieu do: mo {a, i} de cho
#: `mành ~ tình` thi keo theo `nhà ~ nhì` thanh hiep van. Xem lop test
#: `TestAmTinhKhongDuocChapNhanNham`.
#:
#: Day cung la loi giai cho nhom {a, ươ} tung chan viec mo bang (xem
#: docs/plan-nang-chat-luong-tho.md muc 17.2): thong ke cu gop moi am cuoi lai roi doc
#: ra mot cap nguyen am vo nghia. Tach theo am cuoi thi no la ba thu khac nhau.
_THONG_VAN: dict[str, tuple[frozenset[str], ...]] = {
    "*": (
        frozenset({"a", "â", "ă"}),
        frozenset({"o", "ô", "ơ"}),
        frozenset({"ơ", "uô"}),
        frozenset({"u", "ư"}),
        frozenset({"u", "uô"}),
        frozenset({"ư", "ươ"}),
        frozenset({"e", "ê"}),
        frozenset({"i", "y"}),
        frozenset({"i", "iê"}),
    ),
    # --- Cac nhom duoi day rut TU CHINH Truyen Kieu, 11/09/2026 -------------------
    #
    # Quy trinh: do TUNG nhom mot, moi nhom phai qua HAI cua —
    #   1. ha ti le bao loi gia tren Truyen Kieu
    #   2. KHONG lam mot cap nao trong `TestAmTinhKhongDuocChapNhanNham` thanh hiep van
    #
    # Cot "giam" la so cap Truyen Kieu ma RIENG nhom do cuu duoc, do khi them no vao
    # sau cac nhom dung truoc. Tong: 440 -> 276 cap bi loai (27,0% -> 17,0%).
    #
    # Mo ca chin cung mot luc roi thay am tinh do thi khong biet nhom nao gay ra — nen
    # them nhom moi cung phai lam tung cai mot. Xem docs/plan-sua-bo-kiem-van.md muc 8.
    #
    #: `anh ~ inh` — 48 cap. CHI dung voi am cuoi -nh: `ta ~ ti` phai la KHONG.
    "nh": (frozenset({"a", "i"}),),
    #: -i: `ơi ~ ươi` 47 cap (nơi/người) · `ôi ~ ui` nam trong {u, ư} san co.
    "i": (frozenset({"ơ", "ươ"}),),
    #: -ng: `ung ~ ông` 14 (chung/hồng) · `ong ~ ung` 11 (phùng/lòng)
    #:      `ăng ~ ưng` 5 (trăng/chừng)
    "ng": (
        frozenset({"u", "ô"}),
        frozenset({"o", "u"}),
        frozenset({"ă", "ư"}),
    ),
    #: -n: `iên ~ ên` 16 (thiên/trên) · `en ~ iên` 9 (tiền/đen)
    "n": (
        frozenset({"iê", "ê"}),
        frozenset({"e", "iê"}),
    ),
    #: Am tiet MO (khong am cuoi): `i ~ ê` 9 (thề/nghì) · `i ~ ia` 5 (kia/gì).
    #: Am tiet mo chi con nguyen am de hiep van nen no long hon cac am tiet co am cuoi.
    "": (
        frozenset({"i", "ê"}),
        frozenset({"i", "ia"}),
    ),
}


#: Cac nhom NGHI la thong van nhung CHUA BAT, vi chua du bang chung.
#:
#: Day khong phai danh sach viec can lam — no la danh sach nhung cho ta BIET la minh
#: chua biet. Bat mot nhom vao day ma khong co dan chung la noi long bo kiem tra mot
#: cach im lang, va bo kiem tra noi long thi vo dung.
#:
#: {ơ, ê} — do 11/09/2026 khi hieu chuan nguoi cham bang tho chuan muc:
#:
#:     Cảnh nào cảnh chẳng đeo sầu
#:     Người buồn cảnh có vui đâu bao giờ      <- `giờ`  van ơ
#:     Đòi phen gió tựa hoa kề                 <- `kề`   van ê
#:     Nửa rèm tuyết ngậm bốn bề trăng thâu
#:
#:   Bo kiem tra bao cap `giờ`/`kề` khong hiep van, tuc cham mot doan Truyen Kieu
#:   38,3/45. Theo nguyen tac da dung cho ca tep nay — "bao sai tren tho chuan muc thi
#:   BO KIEM TRA SAI" — dang le phai bat {ơ, ê} ngay.
#:
#:   CHUA BAT, vi doan tho tren duoc chep TU TRI NHO va chua doi chieu ban in. Neu
#:   nho sai ma lai noi bang van theo no thi ta pha bo kiem tra bang dung loai tu lua
#:   ma no sinh ra de chong.
#:
#:   DIEU KIEN DE BAT: doi chieu voi corpus Truyen Kieu that (xem
#:   docs/plan-nang-chat-luong-tho.md muc 3.4). Neu cap van do xuat hien nhieu lan
#:   trong 3.254 cau thi bat, va them ca kiem thu.
_NGHI_THONG_VAN: tuple[frozenset[str], ...] = (frozenset({"ơ", "ê"}),)


def _tach_van(van: str) -> tuple[str, str]:
    """Phan van -> (am chinh, am cuoi).

    Vi sao phai tach: hai tieng hiep van khi CUNG AM CUOI va am chinh cung nhom. So
    ca phan van nhu mot chuoi thi `ơn` va `uôn` khong bao gio giong nhau, du chung
    hiep van that trong ca dao.
    """
    am_cuoi = ""
    con = van
    for cuoi in _AM_CUOI:
        if len(con) > len(cuoi) and con.endswith(cuoi):
            am_cuoi = cuoi
            con = con[: -len(cuoi)]
            break
    for doi in _AM_CHINH_DOI:
        if con.endswith(doi):
            # Chuan hoa cach viet TRUOC khi tra ve: `yê` va `iê` la mot nguyen am.
            return _VIET_KHAC_NHAU_CUNG_AM.get(doi, doi), am_cuoi
    # Con lai: am dem (o/u) + mot nguyen am don. Lay ky tu cuoi lam am chinh.
    return (con[-1] if con else con), am_cuoi


#: Luat bang-trac cua luc bat, cac vi tri BAT BUOC. True = phai thanh bang.
#:
#: KHONG co tieng 2 trong bang nay, va do la ket luan da DO duoc chu khong phai bo
#: sot. Hieu chuan tren tho da duoc thua nhan (Truyen Kieu + ca dao, 12 cau):
#:
#:     du 2-4-6(-8)        sai 1/12 cau
#:     bo tieng 2 -> 4-6(-8)  sai 0/12 cau
#:
#: Cau lam vo luat: "Nghĩa mẹ như nước trong nguồn chảy ra" — tieng 2 la `mẹ`, thanh
#: nang (trac). Day la ngoai le quen thuoc cua luc bat bien the, va no pho bien den
#: muc ep tieng 2 se loai nham 25% so bai trong tap hieu chuan.
#:
#: Tieng 4 va 6 thi KHONG co ngoai le nao trong tap da do — giu chung.
_LUC_BAT_LUC: dict[int, bool] = {4: False, 6: True}
_LUC_BAT_BAT: dict[int, bool] = {4: False, 6: True, 8: True}

#: Ep ca tieng 2. Chi dung khi muon tho "dung luat sach vo" va chap nhan loai nham
#: mot phan tho truyen thong. Xem so do o tren truoc khi bat.
_LUC_BAT_LUC_NGHIEM: dict[int, bool] = {2: True, **_LUC_BAT_LUC}
_LUC_BAT_BAT_NGHIEM: dict[int, bool] = {2: True, **_LUC_BAT_BAT}


@dataclass(frozen=True, slots=True)
class Loi:
    """Mot loi luat. `cau` dem tu 1 de khop cach nguoi doc dem dong."""

    cau: int
    loai: Literal["so_tieng", "bang_trac", "van", "so_cau"]
    #: Viet cho MODEL doc trong luot sinh lai, nen phai noi RO sai o dau —
    #: "cau 3 co 7 tieng, luc bat can 6" manh hon han "sai luat, lam lai".
    mo_ta: str
    #: Vi tri TIENG bi sai, dem tu 1. None = loi cua ca cau (so tieng, so cau).
    #:
    #: Co mat de `chu_thich_thanh()` chi dung vao chu do. Mo ta bang loi thi model
    #: phai tu dem lai de tim, va do la mot buoc nua de sai.
    vi_tri: int | None = None


def tach_tieng(tieng: str) -> tuple[str, ThanhDieu]:
    """Tra ve (phan chu KHONG co dau thanh, ten thanh dieu).

    GIU LAI dau mu / rau / trang — chung thuoc ve nguyen am. Xem `_DAU_THANH`.
    """
    chu: list[str] = []
    thanh: ThanhDieu = "ngang"
    for ky_tu in unicodedata.normalize("NFD", tieng.lower()):
        if ky_tu in _DAU_THANH:
            thanh = _DAU_THANH[ky_tu]
        else:
            chu.append(ky_tu)
    return unicodedata.normalize("NFC", "".join(chu)), thanh


def la_bang(tieng: str) -> bool:
    return tach_tieng(tieng)[1] in _BANG


#: Dau cau co the dinh vao mot tieng. PHAI boc truoc khi phan tich van.
#:
#: Khong boc thi `tàn,` cho van `'an,'`, tach ra thanh `(',', '')` — lay dau phay lam
#: nguyen am — va `van_nhau('nhan', 'tàn,')` tra False trong khi `van_nhau('nhan',
#: 'tàn')` tra True. Mot dau phay du lam hong phep kiem.
#:
#: Tren Truyen Kieu loi nay chi chiem 16/497 cap bi loai vi corpus da duoc lam sach.
#: Voi tho MODEL SINH RA thi nang hon han — no dat dau cau khap noi, va cau bat hay
#: ket bang dau cham dung ngay tieng 8, dung moi van bat[8]~luc[6]:
#:
#:     Khẽ đưa hương cốm, nồng nàn café.
#:
#: Bo ca dau ngoac kep va ngoac don: loi thoai trong truyen tho nam trong ngoac kep.
# Ngoac cong va gach dai la CO Y: model sinh ra chung that, va o day chung dang o
# dung vai tro dau cau can boc. noqa vi ruff canh bao ky tu de nham.
_DAU_CAU = ",.;:!?\"'“”‘’()[]-–—…"  # noqa: RUF001


def lay_van(tieng: str) -> str:
    """Phan VAN: bo dau cau, bo phu am dau, bo dau thanh, giu nguyen am va am cuoi."""
    chu, _ = tach_tieng(tieng.strip(_DAU_CAU))
    for phu_am in _PHU_AM_DAU:
        if chu.startswith(phu_am):
            con_lai = chu[len(phu_am) :]
            if con_lai:
                return con_lai
            # Boc xong con RONG. Rieng `gi` va `qu` thi day la truong hop that va
            # thuong gap: `gì`, `gi`, `qu`. Cach phan tich truyen thong coi `gi` la
            # phu am dau, va nguyen am `i` bi NUOT vao chinh chu `i` cua `gi` — nen
            # van cua `gì` la `i`, khong phai `gi`.
            #
            # Khong xu ly thi `lay_van('gì')` tra `'gi'`, tach ra thanh `('g', 'i')`:
            # lay phu am lam nguyen am. Hau qua: `van_nhau('khi', 'gì')` la False,
            # trong khi Truyen Kieu hiep van cap do.
            if phu_am == "gi":
                return "i"
            if phu_am == "qu":
                return "u"
            # Con lai: tieng chi gom phu am — khong hop le. Giu nguyen de khong tra
            # ve chuoi rong roi lam moi phep so sanh sau do thanh dung.
            return chu
    return chu


def van_nhau(a: str, b: str, *, thong_van: bool = True) -> bool:
    """Hai tieng co hiep van khong.

    `thong_van=False` la van CHINH (trung khit). Che do do loai ca Truyen Kieu lan ca
    dao, nen no chi dung de nghien cuu, khong dung de cham.
    """
    van_a, van_b = lay_van(a), lay_van(b)
    if van_a == van_b:
        return True
    if not thong_van:
        return False

    chinh_a, cuoi_a = _tach_van(van_a)
    chinh_b, cuoi_b = _tach_van(van_b)
    # AM CUOI phai trung khit. `an` va `ang` khong hiep van, du am chinh giong nhau.
    if cuoi_a != cuoi_b:
        return False
    if chinh_a == chinh_b:
        return True
    nhom_dung = _THONG_VAN.get("*", ()) + _THONG_VAN.get(cuoi_a, ())
    return any(chinh_a in nhom and chinh_b in nhom for nhom in nhom_dung)


#: Ten thanh cho NGUOI DOC. Bang code dung ten khong dau, nhung cai nay di thang vao
#: prompt nen phai la tieng Viet that.
_TEN_THANH: dict[str, str] = {
    "ngang": "ngang",
    "huyen": "huyền",
    "sac": "sắc",
    "hoi": "hỏi",
    "nga": "ngã",
    "nang": "nặng",
}


def danh_so_tieng(cau: str) -> str:
    """Dong tho kem SO THU TU tung tieng, thang hang.

        Khẽ  đưa  hương  cốm,  nồng  nàn  café
        1    2    3      4     5     6    7

    VI SAO CAN: mot dong loi kieu "co 7 tieng, cau bat can 8" bat model tu DEM lai
    tieng — va dem tieng la dung cai model lam sai ngay tu dau. Do 11/09/2026: 35%
    so ban sinh ra sai so tieng, tuc phep dem cua no khong dang tin.

    Ta thi dem duoc chinh xac 100%, tat dinh, mien phi (`cau.split()`). Ve con so ra
    thi model khong con phai dem, chi con MOT viec thuan ngu nghia: them hay bot mot
    chu cho du. Cung co che da an hai lan trong du an — xem docstring `chu_thich_thanh`.
    """
    tieng = cau.split()
    if not tieng:
        return ""
    so = [str(i) for i in range(1, len(tieng) + 1)]
    rong = [max(len(t), len(n)) for t, n in zip(tieng, so, strict=True)]
    return (
        "  ".join(t.ljust(r) for t, r in zip(tieng, rong, strict=True))
        + chr(10)
        + "  ".join(n.ljust(r) for n, r in zip(so, rong, strict=True))
    )


def chu_thich_thanh(cau: str, nhan_manh: int | None = None) -> str:
    """Dong tho kem thanh dieu tung tieng, thang hang, co the chi vao mot vi tri.

    VI SAO CAN: mot dong loi kieu "tieng 4 ('trời') la thanh bang, can trac" bat model
    tu lam BA viec lien tiep — xac dinh `trời` mang thanh gi, biet thanh do thuoc nhom
    nao, roi nghi ra chu thay the. Hong o buoc nao cung ra ket qua sai, va ta khong
    thay no hong o dau.

    Hai buoc dau la viec `tach_tieng()` lam duoc: tat dinh, mien phi, chinh xac 100%.
    Bat model doan lai thu ta da biet chac la lang phi dung the manh cua minh.

    Ve ra thi model chi con MOT viec thuan ngu nghia: tim mot chu khac cung y, dung
    thanh. Do la viec model lam duoc.

        Xa    xôi   phương  trời   lạ    nơi
        ngang ngang ngang   huyền  nặng  ngang
                            ^^^^^
    """
    tieng = cau.split()
    if not tieng:
        return ""
    thanh = [_TEN_THANH[tach_tieng(t)[1]] for t in tieng]
    rong = [max(len(t), len(th)) for t, th in zip(tieng, thanh, strict=True)]

    dong_chu = "  ".join(t.ljust(r) for t, r in zip(tieng, rong, strict=True))
    dong_thanh = "  ".join(th.ljust(r) for th, r in zip(thanh, rong, strict=True))
    ra = [dong_chu, dong_thanh]

    if nhan_manh is not None and 1 <= nhan_manh <= len(tieng):
        truoc = sum(rong[: nhan_manh - 1]) + 2 * (nhan_manh - 1)
        ra.append(" " * truoc + "^" * rong[nhan_manh - 1])
    return "\n".join(ra)


#: Cac vi tri NGAT hop le trong mot dong luc bat, theo dac ta:
#:     cau luc  6 tieng  ->  2/2/2  hoac 3/3
#:     cau bat  8 tieng  ->  2/2/2/2 hoac 4/4
#: Tuc moi cho ngat deu roi vao vi tri CHAN, tru nhip 3/3 cua cau luc.
_NGAT_HOP_LE: dict[int, frozenset[int]] = {
    6: frozenset({2, 3, 4}),  # 2/2/2 va 3/3
    8: frozenset({2, 4, 6}),  # 2/2/2/2 va 4/4
}


def kiem_nhip(cau: str) -> int | None:
    """Vi tri dau phay dat SAI nhip, dem tu 1. None = khong phat hien duoc gi.

    KIEM DUOC MOT PHAN, va phan do phai noi ro.

    Nhip 2/2/2 phu thuoc cho ngat TU ("Tram nam / trong coi / nguoi ta"), ma biet cho
    ngat tu thi can mot tu dien tu ghep tieng Viet — chua co. Nen ham nay KHONG kiem
    duoc nhip noi chung.

    Cai no kiem duoc: dau PHAY do chinh nguoi viet dat. Dau phay la mot cho ngat co
    that, tat dinh, khong can tu dien. Neu no roi vao vi tri LE thi cau gan nhu chac
    chan bi gay nhip:

        La xanh om ap, dang hong kieu sa     phay sau tieng 4  -> hop le
        Doi nguoi nhu, the mot da vuon cao   phay sau tieng 3  -> gay

    Khong co dau phay thi ham tra None — KHONG phai "dung nhip". Hai cai do khac nhau,
    va gop lam mot se bien mot phep kiem MOT PHAN thanh mot loi bao dam sai.
    """
    tieng = cau.split()
    if len(tieng) not in _NGAT_HOP_LE:
        return None
    hop_le = _NGAT_HOP_LE[len(tieng)]
    for i, t in enumerate(tieng, start=1):
        # Dau phay/cham phay dinh cuoi tieng thu i -> cho ngat sau tieng i.
        if t.rstrip('"\'').endswith((",", ";")) and i < len(tieng) and i not in hop_le:
            return i
    return None


def _cac_cau(bai: str) -> list[list[str]]:
    return [d.split() for d in bai.strip().split("\n") if d.strip()]


def _kiem_bang_trac(tieng: list[str], cau: int, can_bang: dict[int, bool]) -> list[Loi]:
    loi: list[Loi] = []
    for vi_tri, phai_bang in can_bang.items():
        if vi_tri > len(tieng):
            continue
        chu = tieng[vi_tri - 1]
        if la_bang(chu) != phai_bang:
            loi.append(
                Loi(
                    cau=cau,
                    loai="bang_trac",
                    mo_ta=(
                        f"tiếng {vi_tri} ('{chu}') là thanh "
                        f"{'bằng' if la_bang(chu) else 'trắc'}, luật cần thanh "
                        f"{'bằng' if phai_bang else 'trắc'}"
                    ),
                    vi_tri=vi_tri,
                )
            )
    return loi


def kiem_luc_bat(
    bai: str, *, kiem_bang_trac: bool = True, nghiem_ngat: bool = False
) -> list[Loi]:
    """Danh sach loi. Rong = dung luat.

    `kiem_bang_trac=False` chi kiem so tieng va van. Bang-trac la tang ton nhieu luot
    sinh lai nhat ma nguoi doc it nhan ra nhat, nen no duoc tat/bat rieng — xem
    docs/plan-lam-tho-va-tu-host.md muc 0.3.

    `nghiem_ngat=True` ep ca tieng 2. Mac dinh TAT vi no loai nham tho truyen thong —
    xem so do o `_LUC_BAT_LUC`.
    """
    cau = _cac_cau(bai)
    if not cau:
        return [Loi(cau=0, loai="so_cau", mo_ta="bài thơ trống")]

    loi: list[Loi] = []

    # --- 1. So tieng ---
    # Lam TRUOC, va nho lai cau nao sai: sai so tieng thi "tieng 6" tro vao chu khac,
    # nen moi phep kiem van/bang-trac tren cau do deu cho ra loi GIA. Bao mot dong loi
    # gia se lam model di sua nham cho o luot sinh lai.
    sai_so_tieng: set[int] = set()
    for i, tieng in enumerate(cau):
        can = 6 if i % 2 == 0 else 8
        if len(tieng) != can:
            sai_so_tieng.add(i)
            loi.append(
                Loi(
                    cau=i + 1,
                    loai="so_tieng",
                    mo_ta=f"có {len(tieng)} tiếng, câu {'lục' if can == 6 else 'bát'} cần {can}",
                )
            )

    if len(cau) % 2 != 0:
        loi.append(
            Loi(
                cau=len(cau),
                loai="so_cau",
                mo_ta="bài phải kết thúc bằng một câu bát (8 tiếng)",
            )
        )

    # --- 2. Bang/trac ---
    if kiem_bang_trac:
        for i, tieng in enumerate(cau):
            if i in sai_so_tieng:
                continue
            if i % 2 == 0:
                can_bang = _LUC_BAT_LUC_NGHIEM if nghiem_ngat else _LUC_BAT_LUC
            else:
                can_bang = _LUC_BAT_BAT_NGHIEM if nghiem_ngat else _LUC_BAT_BAT
            loi.extend(_kiem_bang_trac(tieng, i + 1, can_bang))
            # Cau bat: tieng 6 va tieng 8 deu thanh bang nhung phai KHAC nhau —
            # mot huyen mot ngang. Cung thanh thi doc len bi "det".
            # Cau bat: tieng 6 va tieng 8 deu thanh bang nhung phai KHAC nhau —
            # mot huyen mot ngang. Cung thanh thi doc len bi "det".
            if (
                i % 2 == 1
                and len(tieng) >= 8
                and tach_tieng(tieng[5])[1] == tach_tieng(tieng[7])[1]
            ):
                loi.append(
                    Loi(
                        cau=i + 1,
                        loai="bang_trac",
                        mo_ta=(
                            f"tiếng 6 ('{tieng[5]}') và tiếng 8 ('{tieng[7]}') cùng thanh; "
                            "một tiếng phải huyền, tiếng kia phải ngang"
                        ),
                        vi_tri=8,
                    )
                )

    # --- 3. Van ---
    for i in range(len(cau) - 1):
        if i in sai_so_tieng or (i + 1) in sai_so_tieng:
            continue
        truoc, sau = cau[i], cau[i + 1]
        if i % 2 == 0:
            # luc -> bat: tieng 6 hiep van tieng 6
            a, b, mo = truoc[5], sau[5], "tiếng 6 câu lục phải hiệp vần tiếng 6 câu bát"
        else:
            # bat -> luc: tieng 8 hiep van tieng 6
            a, b, mo = truoc[7], sau[5], "tiếng 8 câu bát phải hiệp vần tiếng 6 câu lục sau"
        if not van_nhau(a, b):
            loi.append(
                Loi(
                    cau=i + 1,
                    loai="van",
                    mo_ta=f"'{a}' không hiệp vần '{b}' — {mo}",
                    vi_tri=6 if i % 2 == 0 else 8,
                )
            )

    return loi


#: That ngon tu tuyet: luat BANG va luat TRAC, xet tieng 2-4-6 cua tung cau.
#: "Nhat tam ngu bat luan, nhi tu luc phan minh" — tieng 1,3,5 tu do.
#: True = phai thanh bang.
_LUAT_BANG: tuple[dict[int, bool], ...] = (
    {2: True, 4: False, 6: True},
    {2: False, 4: True, 6: False},
    {2: False, 4: True, 6: False},
    {2: True, 4: False, 6: True},
)
_LUAT_TRAC: tuple[dict[int, bool], ...] = tuple(
    {vi: not b for vi, b in cau.items()} for cau in _LUAT_BANG
)


def kiem_that_ngon_tu_tuyet(bai: str, *, kiem_bang_trac: bool = True) -> list[Loi]:
    """Danh sach loi. Rong = dung luat.

    Van: cuoi cau 1, 2, 4 hiep van (hoac chi 2 va 4 — bai "that van" o cau 1 van duoc
    coi la hop le, nen cau 1 chi bao loi khi no khong van voi CA HAI cau kia).
    """
    cau = _cac_cau(bai)
    if not cau:
        return [Loi(cau=0, loai="so_cau", mo_ta="bài thơ trống")]

    loi: list[Loi] = []
    if len(cau) != 4:
        loi.append(
            Loi(cau=len(cau), loai="so_cau", mo_ta=f"có {len(cau)} câu, tứ tuyệt cần đúng 4")
        )

    sai_so_tieng: set[int] = set()
    for i, tieng in enumerate(cau):
        if len(tieng) != 7:
            sai_so_tieng.add(i)
            loi.append(
                Loi(cau=i + 1, loai="so_tieng", mo_ta=f"có {len(tieng)} tiếng, thất ngôn cần 7")
            )

    if len(cau) != 4 or sai_so_tieng:
        # Thieu cau hoac sai so tieng thi moi phep kiem con lai deu cho loi GIA.
        return loi

    # --- Bang/trac: thu ca hai luat, lay ban it loi hon ---
    if kiem_bang_trac:
        ung_vien: list[list[Loi]] = [
            [lo for i, tieng in enumerate(cau) for lo in _kiem_bang_trac(tieng, i + 1, luat[i])]
            for luat in (_LUAT_BANG, _LUAT_TRAC)
        ]
        # Bai hop le neu no theo MOT trong hai luat. Lay ban it loi hon chinh la chon
        # luat ma tac gia dinh dung — khong the doi ho khai bao truoc.
        theo_bang, theo_trac = ung_vien
        loi.extend(theo_bang if len(theo_bang) <= len(theo_trac) else theo_trac)

    # --- Van cuoi cau 1, 2, 4 ---
    c1, c2, c4 = cau[0][-1], cau[1][-1], cau[3][-1]
    if not van_nhau(c2, c4):
        loi.append(
            Loi(cau=4, loai="van", mo_ta=f"'{c4}' không hiệp vần '{c2}' (cuối câu 2 và câu 4)")
        )
    if not van_nhau(c1, c2) and not van_nhau(c1, c4):
        loi.append(
            Loi(
                cau=1,
                loai="van",
                mo_ta=f"'{c1}' không hiệp vần với '{c2}' hay '{c4}' (thể thất vận thì bỏ qua)",
            )
        )

    return loi
