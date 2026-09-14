"""Verifier cho THAT NGON BAT CU — 8 cau x 7 tieng, co NIEM va DOI.

VI SAO TACH KHOI luat.py: `luat.py` da 620 dong va da hieu chuan tren Truyen Kieu; the
nay them niem va doi — hai khai niem KHONG co trong luc bat lan tu tuyet. Tron vao se
lam mot tep da on kho doc hon, va moi lan sua bat cu lai phai chay lai toan bo hieu
chuan luc bat.

LUAT DAY DU:

    8 cau, moi cau 7 tieng
    van   cuoi cau 1, 2, 4, 6, 8 — CUNG mot van (cau 1 duoc phep that van)
    luat  BANG hoac TRAC, xet tieng 2-4-6 ("nhat tam ngu bat luan")
    niem  cau 1-8, 2-3, 4-5, 6-7 — cung thanh o tieng 2
    doi   cau 3-4 (thuc) va cau 5-6 (luan)
    bo cuc  de (1-2) · thuc (3-4) · luan (5-6) · ket (7-8)

DOI KHONG VERIFY TAT DINH TRON VEN — doc ky cho nay truoc khi dung lam THUONG.

Doi chuan doi hai cau tuong nhau ve TU LOAI (danh doi danh, dong doi dong) va ve Y
(tuong hoac phan). Tu loai can bo gan nhan tieng Viet; y thi khong co cach tat dinh.

Nen o day tach lam hai:

    doi_thanh     tieng 2-4-6 cua hai cau NGUOC thanh nhau  -> TAT DINH 100%
    doi_tu_loai   danh doi danh...                          -> KHONG lam

Chi `doi_thanh` duoc phep vao ham thuong. Dua mot xap xi on vao thuong la day model hoc
dung cai sai cua bo do — xem §3 cua docs/plan-rlvr-tho.md.
"""

from .luat import Loi, _cac_cau, la_bang, tach_tieng, van_nhau

#: So cau va so tieng cua the.
SO_CAU = 8
SO_TIENG = 7

#: Luat BANG: tieng 2-4-6 cua tung cau. True = phai thanh bang.
#:
#: Tam cau theo mau nhi-tu-luc luan phien, va cau 1 quyet dinh ca bai goi la "luat bang"
#: hay "luat trac". Bang duoi la LUAT BANG; luat trac la ban dao nguoc hoan toan.
_LUAT_BANG: tuple[dict[int, bool], ...] = (
    {2: True, 4: False, 6: True},
    {2: False, 4: True, 6: False},
    {2: False, 4: True, 6: False},
    {2: True, 4: False, 6: True},
    {2: True, 4: False, 6: True},
    {2: False, 4: True, 6: False},
    {2: False, 4: True, 6: False},
    {2: True, 4: False, 6: True},
)

_LUAT_TRAC: tuple[dict[int, bool], ...] = tuple(
    {vi: not b for vi, b in cau.items()} for cau in _LUAT_BANG
)

#: Cac cap cau phai NIEM voi nhau — cung thanh o tieng 2. Dem tu 1.
#:
#: Niem la thu giu tam cau thanh MOT bai chu khong phai bon cap roi rac. Mat niem
#: ("that niem") la loi nang, va no la ràng buoc GIUA cac cau — khac han bang-trac von
#: chi xet trong mot cau.
CAP_NIEM: tuple[tuple[int, int], ...] = ((1, 8), (2, 3), (4, 5), (6, 7))

#: Cac cap cau phai DOI nhau: thuc (3-4) va luan (5-6).
CAP_DOI: tuple[tuple[int, int], ...] = ((3, 4), (5, 6))

#: Vi tri tieng duoc xet cho bang-trac, niem va doi. "Nhat tam ngu bat luan."
_VI_TRI_XET: tuple[int, ...] = (2, 4, 6)

#: Cau mang VAN — cuoi cau 1, 2, 4, 6, 8.
CAU_CO_VAN: tuple[int, ...] = (1, 2, 4, 6, 8)


def _loi_bang_trac(cau: list[list[str]], luat: tuple[dict[int, bool], ...]) -> list[Loi]:
    ra: list[Loi] = []
    for i, tieng in enumerate(cau):
        for vi_tri, phai_bang in luat[i].items():
            if vi_tri > len(tieng):
                continue
            chu = tieng[vi_tri - 1]
            if la_bang(chu) != phai_bang:
                can = "bằng" if phai_bang else "trắc"
                thuc = "bằng" if la_bang(chu) else "trắc"
                ra.append(
                    Loi(
                        cau=i + 1,
                        loai="bang_trac",
                        mo_ta=f"tiếng {vi_tri} ('{chu}') là thanh {thuc}, luật cần thanh {can}",
                        vi_tri=vi_tri,
                    )
                )
    return ra


def kiem_niem(bai: str) -> list[Loi]:
    """Loi NIEM. Rong = niem dung (hoac khong du cau de xet).

    Niem: tieng 2 cua hai cau trong mot cap phai CUNG thanh (cung bang hoac cung trac).
    """
    cau = _cac_cau(bai)
    ra: list[Loi] = []
    for a, b in CAP_NIEM:
        if len(cau) < b or len(cau[a - 1]) < 2 or len(cau[b - 1]) < 2:
            continue
        ta, tb = cau[a - 1][1], cau[b - 1][1]
        if la_bang(ta) != la_bang(tb):
            ra.append(
                Loi(
                    cau=b,
                    loai="bang_trac",
                    mo_ta=(
                        f"thất niêm: tiếng 2 câu {a} ('{ta}') và tiếng 2 câu {b} ('{tb}') "
                        "phải cùng thanh"
                    ),
                    vi_tri=2,
                )
            )
    return ra


def kiem_doi_thanh(bai: str) -> list[Loi]:
    """Loi DOI THANH o cap thuc (3-4) va luan (5-6). CHI phan thanh, khong phan tu loai.

    Doi thanh: tieng 2, 4, 6 cua hai cau phai NGUOC thanh nhau.

    Day la phan TAT DINH cua doi. Phan tu loai (danh doi danh) KHONG lam o day va khong
    duoc dua vao ham thuong — xem docstring dau tep.
    """
    cau = _cac_cau(bai)
    ra: list[Loi] = []
    for a, b in CAP_DOI:
        if len(cau) < b:
            continue
        ca, cb = cau[a - 1], cau[b - 1]
        for vi_tri in _VI_TRI_XET:
            if vi_tri > len(ca) or vi_tri > len(cb):
                continue
            x, y = ca[vi_tri - 1], cb[vi_tri - 1]
            if la_bang(x) == la_bang(y):
                ra.append(
                    Loi(
                        cau=b,
                        loai="bang_trac",
                        mo_ta=(
                            f"không đối thanh: tiếng {vi_tri} câu {a} ('{x}') và câu {b} "
                            f"('{y}') cùng thanh, phải ngược nhau"
                        ),
                        vi_tri=vi_tri,
                    )
                )
    return ra


def kiem_that_ngon_bat_cu(
    bai: str, *, kiem_bang_trac: bool = True, kiem_doi: bool = True
) -> list[Loi]:
    """Danh sach loi cua mot bai that ngon bat cu. Rong = dung luat.

    Theo dung nep `kiem_luc_bat`:
      - sai so tieng thi KHONG kiem van/thanh tren cau do (tranh loi gia day chuyen);
      - thu CA luat bang lan luat trac, lay ban it loi hon — tac gia khong khai bao
        truoc bai minh theo luat nao.
    """
    cau = _cac_cau(bai)
    if not cau:
        return [Loi(cau=0, loai="so_cau", mo_ta="bài thơ trống")]

    loi: list[Loi] = []
    if len(cau) != SO_CAU:
        loi.append(
            Loi(
                cau=len(cau),
                loai="so_cau",
                mo_ta=f"có {len(cau)} câu, thất ngôn bát cú cần đúng {SO_CAU}",
            )
        )

    sai_so_tieng = False
    for i, tieng in enumerate(cau):
        if len(tieng) != SO_TIENG:
            sai_so_tieng = True
            loi.append(
                Loi(
                    cau=i + 1,
                    loai="so_tieng",
                    mo_ta=f"có {len(tieng)} tiếng, thất ngôn cần {SO_TIENG}",
                )
            )

    # Thieu cau hoac sai so tieng -> moi phep kiem con lai deu cho loi GIA.
    if len(cau) != SO_CAU or sai_so_tieng:
        return loi

    if kiem_bang_trac:
        theo_bang = _loi_bang_trac(cau, _LUAT_BANG)
        theo_trac = _loi_bang_trac(cau, _LUAT_TRAC)
        loi.extend(theo_bang if len(theo_bang) <= len(theo_trac) else theo_trac)
        loi.extend(kiem_niem(bai))

    if kiem_doi:
        loi.extend(kiem_doi_thanh(bai))

    # --- Van: cuoi cau 1, 2, 4, 6, 8 ---
    loi.extend(_loi_van(cau))
    return loi


def _loi_van(cau: list[list[str]]) -> list[Loi]:
    """Loi van, neo vao van DA SO chu khong vao mot cau co dinh.

    VI SAO KHONG NEO VAO CAU 2 — day la mot loi thiet ke ma chinh phep hieu chuan bat
    duoc, ngay lan chay dau tien.
    ...
    Ban dau ham nay lay cuoi cau 2 lam moc. Chay tren «Thu vinh» (Nguyen Khuyen):

        cao · hiu · vào · nào · Đào

    Bon tieng hiep nhau o van "ao", rieng cau 2 lech. Neo vao cau 2 thi verifier bao
    BA cau DUNG la sai, va bo qua cau that su lech. Bao nham 3 loi tren mot bai chuan.

    Neo vao DA SO thi ban thân bai quyet dinh van cua no. Mot bai lech mot van van bi
    bat dung cho, con mot bai ma cau moc lech thi khong keo ca bai xuong theo.

    Hoa thi (tat ca lech nhau) -> lay cau 2, vi do la lua chon chuan nhat khi khong co
    da so. Luc do bai vốn da hong van roi.
    """
    co_van = [(so, cau[so - 1][-1]) for so in CAU_CO_VAN if len(cau) >= so and cau[so - 1]]
    if len(co_van) < 2:
        return []

    # Nhom cac tieng hiep nhau, lay nhom DONG nhat lam van chinh cua bai.
    nhom: list[list[tuple[int, str]]] = []
    for muc in co_van:
        for n in nhom:
            if van_nhau(muc[1], n[0][1]):
                n.append(muc)
                break
        else:
            nhom.append([muc])
    lon_nhat = max(nhom, key=len)
    if len(lon_nhat) == 1:
        # Khong co da so — moi tieng mot phach. Quay ve cau 2 lam moc.
        lon_nhat = next((n for n in nhom if n[0][0] == 2), nhom[0])
    moc = lon_nhat[0][1]
    thuoc = {so for so, _ in lon_nhat}

    ra: list[Loi] = []
    for so, chu in co_van:
        if so in thuoc:
            continue
        # Cau 1 duoc phep "that van" — bien the duoc thua nhan, khong tinh la loi.
        if so == 1:
            continue
        ra.append(
            Loi(
                cau=so,
                loai="van",
                mo_ta=f"'{chu}' không hiệp vần '{moc}' (vần chính của bài)",
                vi_tri=SO_TIENG,
            )
        )
    return ra


def bo_cuc(bai: str) -> dict[str, str]:
    """De · thuc · luan · ket. Rong neu khong du 8 cau.

    KHONG kiem duoc bang code — bo cuc la chuyen NOI DUNG. Ham nay chi CAT bai ra de
    nguoi doc (hoac mot bo cham khac) xem, khong tra ve loi nao.
    """
    cau = [d.strip() for d in bai.strip().split("\n") if d.strip()]
    if len(cau) != SO_CAU:
        return {}
    return {
        "đề": "\n".join(cau[0:2]),
        "thực": "\n".join(cau[2:4]),
        "luận": "\n".join(cau[4:6]),
        "kết": "\n".join(cau[6:8]),
    }


def _cung_thanh(a: str, b: str) -> bool:
    """Hai tieng cung THANH DIEU cu the (khong chi cung nhom bang/trac)."""
    return tach_tieng(a)[1] == tach_tieng(b)[1]
