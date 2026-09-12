"""Thang 100 diem cho tho luc bat — phan TAT DINH.

Chia lam hai nua, va ranh gioi giua chung la ranh gioi giua "do duoc" va "phai co
nguoi doc":

    TAT DINH  45 diem   the 6-8 (10) · van (20) · bang-trac (15)
    PHAI CHAM 55 diem   nhip (15) · ngon ngu (10) · hinh anh (10) ·
                        y nghia (10) · cam xuc (5) · sang tao (5)

Tep nay chi lo 45 diem dau. Chung tinh duoc trong micro-giay, khong goi model, khong
ton dong nao — nen goi bao nhieu lan cung duoc, ke ca de loc du lieu huan luyen.

55 diem con lai nam o evals/metrics/tho_hay.py, vi chung can mot nguoi cham.

VI SAO TACH: gop lam mot thi moi lan muon biet bai tho dung luat khong deu phai goi
model. Va quan trong hon — mot bai DUNG LUAT TUYET DOI van co the la tho do. Hai thu
do khac nhau, nen do rieng thi moi thay duoc cai nao dang hong.

CHENH VOI BAN DAC TA: bang bang-trac o day XET CA TIENG 2 (x B x T x B), dung nhu ban
dac ta. Nhung `kiem_luc_bat()` thi KHONG ep tieng 2, va do la co y — do duoc
11/09/2026: ep tieng 2 loai nham 1/12 cau tho da duoc thua nhan, trong do co
"Nghia me nhu nuoc trong nguon chay ra". CHAM DIEM khac CHAN: cham thi tru diem, chan
thi bat sinh lai. Mot cau ca dao that dang bi tru vai diem thi khong sao; bi chan thi
co.
"""

from dataclasses import dataclass

from .luat import _cac_cau, la_bang, tach_tieng, van_nhau

#: Diem toi da tung thanh phan TAT DINH. Tong 45.
DIEM_THE = 10
DIEM_VAN = 20
DIEM_BANG_TRAC = 15
TONG_TAT_DINH = DIEM_THE + DIEM_VAN + DIEM_BANG_TRAC

#: Diem toi da phan PHAI CHAM. Tong 55. O day de doi chieu; viec cham nam o evals/.
DIEM_NHIP = 15
DIEM_NGON_NGU = 10
DIEM_HINH_ANH = 10
DIEM_Y_NGHIA = 10
DIEM_CAM_XUC = 5
DIEM_SANG_TAO = 5
TONG_PHAI_CHAM = (
    DIEM_NHIP + DIEM_NGON_NGU + DIEM_HINH_ANH + DIEM_Y_NGHIA + DIEM_CAM_XUC + DIEM_SANG_TAO
)

#: Vi tri va thanh BAT BUOC, theo dung ban dac ta:
#:     cau luc  1 2 3 4 5 6  ->  x B x T x B
#:     cau bat  1 2 ... 7 8  ->  x B x T x B x B
#: True = phai thanh bang.
_LUC: dict[int, bool] = {2: True, 4: False, 6: True}
_BAT: dict[int, bool] = {2: True, 4: False, 6: True, 8: True}


@dataclass(frozen=True, slots=True)
class DiemTatDinh:
    """45 diem do duoc. Moi thanh phan kem ti le dat de biet no tru o dau."""

    the: float
    van: float
    bang_trac: float
    #: (so cho dat, tong so cho xet) cho tung thanh phan — de giai thich diem.
    chi_tiet_the: tuple[int, int]
    chi_tiet_van: tuple[int, int]
    chi_tiet_bang_trac: tuple[int, int]

    @property
    def tong(self) -> float:
        return self.the + self.van + self.bang_trac


def _diem(dat: int, tong: int, toi_da: int) -> float:
    """Khong co cho nao de xet -> 0 diem, KHONG phai diem toi da.

    Mot bai rong khong phai mot bai hoan hao. Cho diem toi da khi khong co gi de xet
    la kieu tu lua ma ca du an nay chong.
    """
    return round(toi_da * dat / tong, 2) if tong else 0.0


def cham_tat_dinh(bai: str) -> DiemTatDinh:
    """45 diem tat dinh cua mot bai luc bat."""
    cau = _cac_cau(bai)
    if not cau:
        return DiemTatDinh(0.0, 0.0, 0.0, (0, 0), (0, 0), (0, 0))

    # --- The 6-8: 10 diem ---
    # Xet CA viec bai co ket thuc bang cau bat khong: do la mot phan cua "dung the".
    the_dat = sum(1 for i, t in enumerate(cau) if len(t) == (6 if i % 2 == 0 else 8))
    the_tong = len(cau) + 1
    if len(cau) % 2 == 0:
        the_dat += 1

    # --- Van: 20 diem ---
    van_dat = van_tong = 0
    for i in range(len(cau) - 1):
        truoc, sau = cau[i], cau[i + 1]
        if i % 2 == 0:
            if len(truoc) >= 6 and len(sau) >= 6:
                van_tong += 1
                van_dat += van_nhau(truoc[5], sau[5])
        elif len(truoc) >= 8 and len(sau) >= 6:
            van_tong += 1
            van_dat += van_nhau(truoc[7], sau[5])

    # --- Bang/trac: 15 diem ---
    bt_dat = bt_tong = 0
    for i, t in enumerate(cau):
        luat = _LUC if i % 2 == 0 else _BAT
        for vi_tri, phai_bang in luat.items():
            if vi_tri > len(t):
                continue
            bt_tong += 1
            bt_dat += la_bang(t[vi_tri - 1]) == phai_bang
        # Cau bat: tieng 6 va 8 phai KHAC thanh. Tinh la mot cho xet rieng.
        if i % 2 == 1 and len(t) >= 8:
            bt_tong += 1
            bt_dat += tach_tieng(t[5])[1] != tach_tieng(t[7])[1]

    return DiemTatDinh(
        the=_diem(the_dat, the_tong, DIEM_THE),
        van=_diem(van_dat, van_tong, DIEM_VAN),
        bang_trac=_diem(bt_dat, bt_tong, DIEM_BANG_TRAC),
        chi_tiet_the=(the_dat, the_tong),
        chi_tiet_van=(van_dat, van_tong),
        chi_tiet_bang_trac=(bt_dat, bt_tong),
    )


def bang_diem(d: DiemTatDinh) -> str:
    """In ra cho nguoi doc. Kem ti le de biet diem bi tru o dau."""
    return "\n".join(
        [
            f"  thể 6-8      {d.the:5.1f}/{DIEM_THE:<3} ({d.chi_tiet_the[0]}/{d.chi_tiet_the[1]})",
            f"  vần         {d.van:5.1f}/{DIEM_VAN:<3} ({d.chi_tiet_van[0]}/{d.chi_tiet_van[1]})",
            f"  bằng-trắc   {d.bang_trac:5.1f}/{DIEM_BANG_TRAC:<3} "
            f"({d.chi_tiet_bang_trac[0]}/{d.chi_tiet_bang_trac[1]})",
            f"  ---- tất định {d.tong:5.1f}/{TONG_TAT_DINH}",
        ]
    )
