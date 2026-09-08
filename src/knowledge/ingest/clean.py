"""Lam sach van ban trich xuat, va GIU LAI so trang thay vi vut di.

Day la buoc truoc day khong ton tai. `_from_pdf` noi cac trang bang '\\n\\n' roi tra
ve mot chuoi phang — nghia la moi thu nhieu cua PDF di thang vao chunk, vao embedding
va vao ca `tsv`.

Do tren The_Open_Source_Cookbook_v0.4.pdf (88 trang):

    so trang lan vao dau moi trang   88/88 trang
    xuong dong GIUA cau              1.209 cho
    dong chi mot chu cai (muc luc)   1 trang
    khoang trang thua                2 cho     <- khong dang lam
    the HTML                         0         <- khong ap dung
    header/footer lap lai            0         <- tep nay khong co, co che van can

Hai cai dau moi la van de that, va cai dau tien con la mot co hoi bi bo lo: SO TRANG
DANG NAM SAN NGAY DO, ma cot `kb_chunk.page` thi luon NULL. Cong cu
`search_knowledge_base` da viet san nhanh in `trang {c.page}` — nhanh do chua bao gio
chay.

Nguyen tac chung cua ca module: MOI LUAT DEU HEP. Lam sach qua tay se sua hong mot
van ban von dung, va khong ai phat hien ra — dung loai loi im lang ma du an nay chong.
"""

import re
from collections import Counter
from dataclasses import dataclass

#: Ti le trang phai cung khop thi mot quy luat moi duoc coi la that. Duoi nguong nay
#: coi nhu trung hop va KHONG dung toi van ban.
_NGUONG = 0.6


@dataclass(frozen=True, slots=True)
class Trang:
    #: So trang IN TRONG TAI LIEU neu doc duoc, khong phai chi so vat ly. Hai cai nay
    #: lech nhau o moi tai lieu co bia va loi noi dau danh so La Ma.
    so: int | None
    noi_dung: str


# --------------------------------------------------------------------------------
# 1. So trang
# --------------------------------------------------------------------------------
_CHI_SO = re.compile(r"^\s*(\d{1,4})\s*$")


#: So trang nam o dau hay cuoi trang. Do that tren hai tai lieu: cookbook tieng Anh
#: de o DAU (88/88 trang), booklet Sa Pa de o CUOI (41/46 trang). Chi dò mot vi tri
#: la bo sot mot nua so tai lieu thuc te.
ViTriSoTrang = str  # "dau" | "cuoi"


def _lay_so(noi_dung: str, vi_tri: ViTriSoTrang) -> int | None:
    dong = [d for d in noi_dung.strip().split("\n") if d.strip()]
    if not dong:
        return None
    khop = _CHI_SO.match(dong[0] if vi_tri == "dau" else dong[-1])
    return int(khop.group(1)) if khop else None


def _do_lech_so_trang(trang_tho: list[str]) -> tuple[int, ViTriSoTrang] | None:
    """Tim (do lech, vi tri) neu co mot quy luat nhat quan. Khong co -> None.

    Khong gia dinh trang vat ly 1 = trang in "1": sach co bia va loi noi dau thuong
    lech vai trang. Tim do lech pho bien nhat o TUNG vi tri, va chi nhan neu no dung
    cho da so.

    Booklet Sa Pa la vi du vi sao phai co nguong: chi 7/46 trang co con so o dong
    DAU, va do lech cua chung khong nhat quan (30, 1, -5, -7) — do la con so lac vao
    tu noi dung, khong phai so trang. O dong CUOI thi 40/46 trang cung do lech -5.
    """
    tot_nhat: tuple[int, int, ViTriSoTrang] | None = None
    for vi_tri in ("dau", "cuoi"):
        lech: Counter[int] = Counter()
        for i, t in enumerate(trang_tho, start=1):
            so = _lay_so(t, vi_tri)
            if so is not None:
                lech[so - i] += 1
        if not lech:
            continue
        pho_bien, so_lan = lech.most_common(1)[0]
        if so_lan >= len(trang_tho) * _NGUONG and (tot_nhat is None or so_lan > tot_nhat[0]):
            tot_nhat = (so_lan, pho_bien, vi_tri)

    return (tot_nhat[1], tot_nhat[2]) if tot_nhat else None


def _tach_so_trang(
    noi_dung: str, so_mong_doi: int, vi_tri: ViTriSoTrang
) -> tuple[str, int | None]:
    """Bo dong so trang, tra ve kem so doc duoc.

    Chi bo khi dong do la DUNG con so mong doi. Mot trang bat dau bang
    "1 cp coarsely chopped celery" co dong dau khong phai chi mot con so, nen khong
    bi dung toi.
    """
    dong = noi_dung.strip("\n").split("\n")
    if not dong:
        return noi_dung, None

    chi_muc = 0 if vi_tri == "dau" else len(dong) - 1
    # Bo qua dong trong o ria truoc khi doi chieu.
    while 0 <= chi_muc < len(dong) and not dong[chi_muc].strip():
        chi_muc += 1 if vi_tri == "dau" else -1
    if not (0 <= chi_muc < len(dong)):
        return noi_dung, None

    khop = _CHI_SO.match(dong[chi_muc])
    if khop and int(khop.group(1)) == so_mong_doi:
        return "\n".join(dong[:chi_muc] + dong[chi_muc + 1 :]), so_mong_doi
    return noi_dung, None


# --------------------------------------------------------------------------------
# 2. Header / footer lap lai
# --------------------------------------------------------------------------------
#: Duoi so trang nay thi KHONG do header/footer.
#:
#: Luat "lap tren >60% so trang" dung mot cach tam thuong khi co qua it trang: mot
#: trang thi dong dau cua no luon dat 100%. Da gap that trong test — mot tai lieu mot
#: trang bi bo mat ca dong dau lan dong cuoi, tuc la mat noi dung that.
_TOI_THIEU_TRANG = 4


def _dong_lap(trang: list[str], lay_dong_dau: bool) -> str | None:
    """Dong dau (hoac cuoi) giong nhau tren da so trang = header/footer, khong phai
    noi dung. Tra ve None neu khong co quy luat.
    """
    if len(trang) < _TOI_THIEU_TRANG:
        return None

    dem: Counter[str] = Counter()
    for t in trang:
        cac_dong = [d.strip() for d in t.strip().split("\n") if d.strip()]
        if cac_dong:
            dem[cac_dong[0] if lay_dong_dau else cac_dong[-1]] += 1
    if not dem:
        return None
    dong, so_lan = dem.most_common(1)[0]
    # Do dai co tran: mot dong dai giong nhau tren nhieu trang gan nhu chac chan la
    # noi dung bi lap (dieu khoan giay phep), khong phai header.
    if so_lan >= len(trang) * _NGUONG and len(dong) <= 80:
        return dong
    return None


def _bo_dong(noi_dung: str, can_bo: set[str]) -> str:
    giu = [d for d in noi_dung.split("\n") if d.strip() not in can_bo]
    return "\n".join(giu)


# --------------------------------------------------------------------------------
# 3. Chu cai roi tung dong (van ban dat doc trong ban goc)
# --------------------------------------------------------------------------------
#: Vi du that o trang muc luc: "C\nO\nN\nT\nE\nN\nT\nS" -> "CONTENTS".
#: Toi thieu BON dong de khong gop nham mot danh sach kieu "A\nB\nC".
_CHU_CAI_DOC = re.compile(r"(?:^[A-Za-z]\n){3,}^[A-Za-z]$", re.MULTILINE)


def _gop_chu_cai_doc(noi_dung: str) -> str:
    return _CHU_CAI_DOC.sub(lambda m: m.group(0).replace("\n", ""), noi_dung)


# --------------------------------------------------------------------------------
# 4. Xuong dong giua cau
# --------------------------------------------------------------------------------
#: Noi 'a\nb' thanh 'a b' khi dong truoc KHONG ket thuc bang dau cau va dong sau bat
#: dau bang chu THUONG.
#:
#: Luat hep co chu dich. Danh sach nguyen lieu co moi dong mot mon:
#:     "1 cp coarsely chopped celery"
#:     "5 or 6 carrots, sliced"
#: dong sau bat dau bang CHU SO nen khong bi noi. "INSTRUCTIONS:" ket thuc bang ':'
#: nen cung khong bi noi vao buoc 1.
_GAY_DONG = re.compile(r"(?<=[^\s.!?:;•\-–—])\n(?=[a-z])")


def _noi_dong_gay(noi_dung: str) -> str:
    return _GAY_DONG.sub(" ", noi_dung)


# --------------------------------------------------------------------------------
# 5. Khoang trang
# --------------------------------------------------------------------------------
_NHIEU_CACH = re.compile(r"[ \t]{2,}")
_NHIEU_DONG = re.compile(r"\n{3,}")


def _nen_khoang_trang(noi_dung: str) -> str:
    return _NHIEU_DONG.sub("\n\n", _NHIEU_CACH.sub(" ", noi_dung)).strip()


# --------------------------------------------------------------------------------
# Ghep lai
# --------------------------------------------------------------------------------
def lam_sach(trang_tho: list[str]) -> list[Trang]:
    """Tra ve tung trang da lam sach, kem so trang doc duoc (None neu khong doc duoc).

    THU TU CO Y NGHIA:
      1. So trang -> phai bo TRUOC khi do header/footer, neu khong moi trang mot so
         khac nhau se khong bao gio thanh "dong lap".
      2. Header/footer -> can nhin CA TAP trang, nen khong the lam trong mot ham
         chi thay mot trang.
      3. Chu cai doc -> truoc buoc noi dong, vi no chinh la cac dong mot ky tu.
      4. Noi dong gay -> sau cung trong cac buoc dung toi cau truc dong.
      5. Nen khoang trang -> cuoi cung, don not.
    """
    if not trang_tho:
        return []

    quy_luat = _do_lech_so_trang(trang_tho)

    da_bo_so: list[str] = []
    so_trang: list[int | None] = []
    for i, tho in enumerate(trang_tho, start=1):
        if quy_luat is None:
            da_bo_so.append(tho)
            so_trang.append(None)
        else:
            lech, vi_tri = quy_luat
            noi_dung, so = _tach_so_trang(tho, i + lech, vi_tri)
            da_bo_so.append(noi_dung)
            so_trang.append(so)

    can_bo = {d for d in (_dong_lap(da_bo_so, True), _dong_lap(da_bo_so, False)) if d}

    ket_qua: list[Trang] = []
    for so, noi_dung in zip(so_trang, da_bo_so, strict=True):
        if can_bo:
            noi_dung = _bo_dong(noi_dung, can_bo)
        noi_dung = _nen_khoang_trang(_noi_dong_gay(_gop_chu_cai_doc(noi_dung)))
        ket_qua.append(Trang(so=so, noi_dung=noi_dung))
    return ket_qua


def ghep(trang: list[Trang]) -> tuple[str, list[tuple[int, int | None]]]:
    """Noi cac trang thanh mot van ban, kem BAN DO VI TRI -> SO TRANG.

    Ban do la danh sach (offset bat dau, so trang) da sap tang dan. Buoc chunk dung
    no de biet mot chunk bat dau o trang nao — do la tat ca nhung gi can de dien cot
    `kb_chunk.page`.

    Ngan trang bang dong trong: buoc chunk coi do la ranh gioi doan, nen mot chunk
    khong bat qua hai trang tru khi that su can.
    """
    phan: list[str] = []
    ban_do: list[tuple[int, int | None]] = []
    vi_tri = 0
    for t in trang:
        if not t.noi_dung:
            continue
        ban_do.append((vi_tri, t.so))
        phan.append(t.noi_dung)
        vi_tri += len(t.noi_dung) + 2  # '\n\n'
    return "\n\n".join(phan), ban_do


def trang_cua(ban_do: list[tuple[int, int | None]], vi_tri: int) -> int | None:
    """So trang chua `vi_tri`. Ban do da sap nen duyet nguoc la du va khong can bisect
    cho vai tram phan tu.
    """
    ket_qua: int | None = None
    for bat_dau, so in ban_do:
        if bat_dau > vi_tri:
            break
        ket_qua = so
    return ket_qua
