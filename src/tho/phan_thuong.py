"""HAM THUONG VERIFIABLE cho RLVR — bien ket qua verify thanh mot so trong [0, 1].

Xem docs/plan-rlvr-tho.md. Day la lop 2: lop 1 (verifier) nam o `luat.py` va `bat_cu.py`.

BA NGUYEN TAC, moi cai chan mot kieu hong rieng cua RL.

1. THUONG DAC, KHONG THUA.
   Thuong nhi phan ("dung luat / khong") thi voi model goc gan nhu luon bang 0 — GRPO
   khong co gradient de di. Nen moi thanh phan cho diem theo TI LE rang buoc thoa, y
   nhu `cham_tat_dinh` dang lam. Mot bai sai mot van phai duoc diem cao hon bai sai bon
   van, neu khong thi model khong biet minh dang di dung huong.

2. CHONG LACH PHAI CO NGAY TU DAU, KHONG THEM SAU.
   Toi uu thang vao mot bo do la moi cho ho cua bo do deu tro thanh muc tieu. Ba lo
   hong da BIET truoc, va ca ba deu da co bo bat san trong du an:

     chep ca dao   -> diem luat tuyet doi ma khong sang tac gi     (`so_cau_chep`)
     be chu        -> "ngọt ngào" -> "ngọt ngao" LAM TANG diem van (`cum_kha_nghi`)
     lap chu       -> bai suy bien van an duoc diem ti le
     tieng bia ra  -> "mìmh" khop van va khop thanh nhu mot tieng that
                                                             (`tieng_khong_hop_le`)

   Lo hong thu hai nguy hiem nhat vi no duoc thuong TRUC TIEP: be chu lam diem van tang
   that, chu khong phai mot ke ho gian tiep.

3. VERIFIER CO SAI SO, VA SAI SO DO TRO THANH MUC TIEU.
   Bo kiem van bao nham 17,0% tren Truyen Kieu. Voi mot bo LOC thi do la 17% bai tot bi
   loai oan — kho chiu, khong tich luy. Voi mot ham THUONG thi do la 17% van DUNG bi
   phat, va model se hoc TRANH chung. Sai lech tich luy qua tung buoc cap nhat.

   Day la gioi han tren cua ca phuong phap, khong phai mot chi tiet ky thuat. Xem §3.1
   va §4.3 cua plan: ha con so nay xuong la viec phai lam TRUOC khi huan luyen.
"""

from dataclasses import dataclass

from .bat_cu import kiem_that_ngon_bat_cu
from .luat import Loi, _cac_cau, kiem_luc_bat, kiem_that_ngon_tu_tuyet
from .tu_vung import cum_kha_nghi, tieng_khong_hop_le

#: Trong so GOC. Xem `trong_so()` — the tho nao khong co rang buoc nao cua mot thanh
#: phan thi thanh phan do bi bo di va phan con lai duoc chuan hoa lai.
#:
#: `van` nang nhat co chu dich: do 14/09 cho thay day dung la cho model manh hong nang
#: nhat (gpt-5-mini duoc 2,2/20 van trong khi sang tao 3,0/5 — vuot ca moc ca dao).
#: RLVR o day nham vao chinh cho do.
TRONG_SO_GOC: dict[str, float] = {
    "khung": 0.30,  # so tieng + so cau — rang buoc cung nhat
    "van": 0.35,
    "thanh": 0.25,  # bang-trac + niem
    "doi": 0.10,  # CHI doi thanh; xem bat_cu.py ve vi sao khong co doi tu loai
}

#: Phat khi bat duoc hanh vi LACH. Nhan vao thuong, khong tru.
#:
#: Nhan chu khong tru: tru thi mot bai chep van con duong am de giu diem duong nho cac
#: thanh phan khac. Nhan voi 0 thi chep = khong duoc gi, dut khoat.
PHAT_CHEP = 0.0
#: Cung hang voi `chep`, va vi mot ly do khac han: mot bai chua tieng khong phai
#: tieng Viet la mot bai KHONG DOC DUOC. `mìmh` duoc may cham 0,778/1,000 trong khi
#: nguoi cham 0/0/0 — day chinh la cho thang do va nguoi doc lech nhau nhat da tim
#: thay. Nhan 0 chu khong 0,5: khong co phan nao cua bai do dang duoc thuong.
PHAT_TIENG_SAI = 0.0
PHAT_BE_CHU = 0.5
PHAT_LAP = 0.5

#: Ti le tieng lap toi da truoc khi coi la bai SUY BIEN.
#:
#: 0,45 chon tu do tren tho chuan: bai co ti le lap cao nhat trong tap hieu chuan la
#: «Qua Deo Ngang» (0,34 — "chen", "gia gia", "quoc quoc", "ta voi ta" deu la lap CO Y).
#: Dat 0,45 de chua het lap nghe thuat ma van bat duoc bai doc mot chu tu dau den cuoi.
NGUONG_LAP = 0.45


@dataclass(frozen=True, slots=True)
class ChiTietThuong:
    """Tach bach tung phan de go loi duoc. `tong` la thu GRPO dung."""

    tong: float
    khung: float
    van: float
    thanh: float
    doi: float
    #: He so phat da nhan vao (1,0 = khong phat).
    he_so_phat: float
    #: Vi sao bi phat. Rong = khong phat.
    ly_do_phat: tuple[str, ...]


def _ti_le(so_loi: int, so_rang_buoc: int) -> float:
    """Ti le rang buoc THOA, kep ve [0, 1]. Khong co rang buoc nao -> 1,0."""
    if so_rang_buoc <= 0:
        return 1.0
    return max(0.0, min(1.0, (so_rang_buoc - so_loi) / so_rang_buoc))


def _ti_le_lap(bai: str) -> float:
    """Ti le tieng LAP LAI trong ca bai. Cao = bai suy bien."""
    tieng = [t.lower() for cau in _cac_cau(bai) for t in cau]
    if not tieng:
        return 1.0
    return 1.0 - len(set(tieng)) / len(tieng)


#: So cau CHUAN cua tung the — dung de tinh trong so, KHONG dung so cau that cua bai.
#:
#: Phai la so CHUAN chu khong phai so quan sat duoc, neu khong thi mot bai suy bien se
#: duoc chuan hoa co loi cho no: bai mot cau -> khong co cap van nao -> bo trong so cua
#: `van` -> con moi `khung`, va no an diem cao hon mot bai bon cau chi lech mot van.
_SO_CAU_CHUAN: dict[str, int] = {
    "luc_bat": 4,
    "that_ngon_bat_cu": 8,
    "that_ngon_tu_tuyet": 4,
}


def trong_so(the_tho: str) -> dict[str, float]:
    """Trong so cho MOT the tho. Cong lai bang 1,0.

    THANH PHAN KHONG CO RANG BUOC NAO THI KHONG CO TRONG SO. Nghe hien nhien, nhung no
    la mot loi da chay that va chi lo ra khi do DONG GOP PHUONG SAI:

        luc bat khong co luat DOI -> `_dem_rang_buoc` tra doi = 0 rang buoc
        -> `_ti_le(0, 0)` tra 1,0 luon
        -> nhung khi khung hong thi ta dat doi = 0,0

    Tuc `doi` tro thanh mot BAN SAO NHI PHAN cua "khung co hong khong", mang trong so
    0,10. Do 15/09 tren 10 nhom x 8 ban: `doi` co phuong sai CAO NHAT bang (std 0,4704)
    va chiem 15,6% phuong sai cua R_total — de lap lai dung cai `khung` da noi.

    Hau qua: `R_total` that su la 0,40·khung + 0,35·van + 0,25·thanh, khong phai bang
    trong so da ghi. Trong GRPO thi do la khuech dai tin hieu khung them mot lan nua.

    33 test cua ham nay khong bat duoc, vi chung kiem GIA TRI chu khong kiem DONG GOP
    PHUONG SAI. Xem `TestDongGopPhuongSai`.

    SUY TU SO RANG BUOC chu khong ghi hai bang cung: cach nay tu dung cho the tho them
    vao sau, va khong the lech khoi `_dem_rang_buoc`.
    """
    rb = _dem_rang_buoc(the_tho, _SO_CAU_CHUAN.get(the_tho, 4))
    co = {k: w for k, w in TRONG_SO_GOC.items() if rb[k] > 0}
    tong = sum(co.values())
    return {k: (co[k] / tong if k in co else 0.0) for k in TRONG_SO_GOC}


def _dem_rang_buoc(the_tho: str, so_cau: int) -> dict[str, int]:
    """So rang buoc cua tung nhom, de chia ti le cho dung.

    CHUAN HOA THEO SO RANG BUOC chu khong theo so loi tuyet doi: bai dai hon co nhieu
    rang buoc hon, va neu khong chia thi bai NGAN tu dong duoc diem cao hon — mot cach
    lach ma model se tim ra rat nhanh.
    """
    if the_tho == "luc_bat":
        cap = max(0, so_cau - 1)
        return {"khung": so_cau + 1, "van": cap, "thanh": so_cau * 3, "doi": 0}
    if the_tho == "that_ngon_bat_cu":
        return {"khung": 9, "van": 4, "thanh": 8 * 3 + 4, "doi": 2 * 3}
    return {"khung": 5, "van": 2, "thanh": 4 * 3, "doi": 0}


def _loi_theo_nhom(loi: list[Loi]) -> dict[str, int]:
    nhom = {"khung": 0, "van": 0, "thanh": 0, "doi": 0}
    for x in loi:
        if x.loai in ("so_tieng", "so_cau"):
            nhom["khung"] += 1
        elif x.loai == "van":
            nhom["van"] += 1
        elif "đối thanh" in x.mo_ta:
            nhom["doi"] += 1
        else:
            nhom["thanh"] += 1
    return nhom


def phan_thuong(bai: str, the_tho: str = "luc_bat") -> ChiTietThuong:
    """Thuong trong [0, 1] cho mot bai tho. Cang cao cang dung luat.

    `the_tho`: "luc_bat" | "that_ngon_bat_cu" | "that_ngon_tu_tuyet".
    """
    bai = bai.strip()
    if not bai:
        return ChiTietThuong(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, ("bài trống",))

    if the_tho == "luc_bat":
        loi = kiem_luc_bat(bai)
    elif the_tho == "that_ngon_bat_cu":
        loi = kiem_that_ngon_bat_cu(bai)
    else:
        loi = kiem_that_ngon_tu_tuyet(bai)

    so_cau = len(_cac_cau(bai))
    rb = _dem_rang_buoc(the_tho, so_cau)
    nhom = _loi_theo_nhom(loi)
    ts = trong_so(the_tho)
    phan = {k: _ti_le(nhom[k], rb[k]) for k in TRONG_SO_GOC}

    # SAI KHUNG THI KHONG DUOC DIEM O CAC NHOM CON LAI.
    #
    # LO HONG LACH NGHIEM TRONG, bat duoc ngay lan chay thu dau tien cua ham nay.
    #
    # Moi bo kiem trong du an deu BO QUA van/thanh tren nhung cau sai so tieng — co chu
    # dich, de tranh loi GIA day chuyen ("tieng 6" tro vao chu khac khi cau thieu chu).
    # Voi mot bo LOC thi dung. Voi mot ham THUONG thi no thanh mot ke ho: khong co loi
    # nao duoc bao o nhom do, nen ti le thoa = 1,0 — diem TUYET DOI cho thu chua he
    # duoc kiem.
    #
    # Do that: mot bai hai cau, 7 va 3 tieng, an 0,800/1,0. Model se tim ra rat nhanh
    # rang PHA KHUNG la cach re nhat de ne kiem van.
    #
    # "Chua kiem duoc" phai ra 0 chu khong ra 1 — cung luat `None` vs `0.0` da lam hong
    # hai phep do trong du an nay, nhung o day hau qua nang hon: no khong lam sai mot
    # bao cao, no day model hoc mot thoi quen hong.
    #
    # Van con gradient de model di: `khung` duoc cham theo ti le, nen bai sai it tieng
    # van hon bai sai nhieu. Sua xong khung thi ba nhom kia moi sang len — dung thu tu
    # hoc ma ta muon.
    if nhom["khung"] > 0:
        for k in ("van", "thanh", "doi"):
            phan[k] = 0.0

    tho = sum(ts[k] * phan[k] for k in TRONG_SO_GOC)

    # --- Chong lach ---
    he_so = 1.0
    ly_do: list[str] = []

    # Nhap muon: `so_cau_chep` nam trong sinh.py, va sinh.py nhap nguoc lai module nay
    # se thanh vong. Day la cai gia cua viec de bo chan chep canh vong sinh.
    from .sinh import NGUONG_CHEP, so_cau_chep

    chep = so_cau_chep(bai)
    if chep:
        he_so *= PHAT_CHEP
        ly_do.append(f"chép {chep} câu của bài mẫu (ngưỡng {NGUONG_CHEP:.0%})")

    sai = tieng_khong_hop_le(bai)
    if sai:
        he_so *= PHAT_TIENG_SAI
        ly_do.append("tiếng không phải tiếng Việt: " + ", ".join(f"'{t}'" for t in sai[:3]))

    be = cum_kha_nghi(bai)
    if be:
        he_so *= PHAT_BE_CHU
        ly_do.append("bẻ chữ: " + "; ".join(f"'{a}' (chắc là '{b}')" for a, b in be[:3]))

    lap = _ti_le_lap(bai)
    if lap > NGUONG_LAP:
        he_so *= PHAT_LAP
        ly_do.append(f"lặp tiếng {lap:.0%} > ngưỡng {NGUONG_LAP:.0%}")

    return ChiTietThuong(
        # KEP THAT ve [0, 1], khong tin vao phep cong so thuc.
        #
        # `trong_so()` chia lai nen tong cac trong so ra 1,0000000000000002 chu khong
        # dung 1,0. Mot bai hoan hao vi the vuot tran — nho, nhung ham nay HUA tra
        # trong [0, 1] va GRPO dung thang con so do. Mot hop dong da khai thi phai giu
        # bang code, khong bang hy vong rang phep cong khong troi.
        tong=max(0.0, min(1.0, tho * he_so)),
        khung=phan["khung"],
        van=phan["van"],
        thanh=phan["thanh"],
        doi=phan["doi"],
        he_so_phat=he_so,
        ly_do_phat=tuple(ly_do),
    )


def thuong(bai: str, the_tho: str = "luc_bat") -> float:
    """Chi con so — dang GRPO goi."""
    return phan_thuong(bai, the_tho).tong
