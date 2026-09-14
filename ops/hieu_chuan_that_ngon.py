"""Hieu chuan verifier THAT NGON — tu tuyet (4 cau) va bat cu (8 cau).

    uv run python ops/hieu_chuan_that_ngon.py

Anh em voi ops/hieu_chuan_tho.py (luc bat). Cung mot nguyen tac:

    Moi lan bo kiem tra bao mot bai o day sai luat, gan nhu chac chan la BO KIEM TRA
    SAI, khong phai Nguyen Khuyen sai.

VI SAO PHAI CO, va vi sao no khat khe hon truoc: hai bo kiem nay da duoc dung trong
`tho/phan_thuong.py` lam HAM THUONG cho RLVR. Mot ham thuong bao nham thi khong chi
loai oan — no DAY MODEL tranh nhung cai dung, va sai lech tich luy qua tung buoc cap
nhat. Xem §3.1 cua docs/plan-rlvr-tho.md.

TIEU CHI CHON MAU — hoc duoc khi soan tap nay, va no khong hien nhien:

  1. KHONG dung BAN DICH de hieu chuan luat thanh. Nguyen tac chu Han theo luat
     bang-trac cua tho Duong; ban dich tieng Viet giu nghia va so tieng nhung khong co
     gi bat no giu thanh dieu. Hai ban dich «Nam quoc son ha» bao 6 va 4 loi bang-trac
     — va do khong phai loi cua verifier.
  2. KIEM THE TRUOC KHI THEM. «Ram thang gieng» (ban dich Xuan Thuy) la LUC BAT, khong
     phai tu tuyet. Chinh verifier bat duoc loi soan tep do.

Tieu chi khong phai "noi tieng", ma la "duoc sang tac THEO DUNG the dang do".

Chi phi: 0 dong, 0 lan goi model.
"""

import sys
from collections import Counter
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "src"))

from tho.bat_cu import kiem_that_ngon_bat_cu  # noqa: E402
from tho.luat import Loi, kiem_that_ngon_tu_tuyet  # noqa: E402

#: Nguong dat, theo §4.2 cua docs/plan-rlvr-tho.md.
#:
#: Chat hon nguong cua luc bat (van 5,8%) co ly do: hai the nay ngan hon va luat cua
#: chung chat hon, nen mot ti le bao nham bang nhau se lam hong ti le CA BAI cao hon.
NGUONG = 0.05


def doc_bai(tep: Path) -> list[str]:
    """Moi bai cach nhau MOT dong trong. Dong '#' la chu thich."""
    bai: list[str] = []
    cur: list[str] = []
    for dong in tep.read_text(encoding="utf-8").split("\n"):
        if dong.startswith("#"):
            continue
        if not dong.strip():
            if cur:
                bai.append("\n".join(cur))
                cur = []
        else:
            cur.append(dong.strip())
    if cur:
        bai.append("\n".join(cur))
    return bai


def _do(ten: str, tep: Path, kiem: object, so_rang_buoc: int) -> bool:
    if not tep.exists():
        print(f"KHONG CO TEP: {tep}", file=sys.stderr)
        return False

    bai = doc_bai(tep)
    dem: Counter[str] = Counter()
    tong = sach = 0
    print(f"\n{'=' * 74}\n{ten} — {len(bai)} bài\n{'=' * 74}")
    for i, b in enumerate(bai, 1):
        loi: list[Loi] = kiem(b)  # type: ignore[operator]
        tong += len(loi)
        sach += not loi
        for x in loi:
            dem[x.loai] += 1
        dau = "  " if not loi else "<-"
        print(f"  [{i}] {b.split(chr(10))[0][:38]:<40} {len(loi)} lỗi {dau}")
        for x in loi[:3]:
            print(f"        câu {x.cau} · {x.loai} · {x.mo_ta[:70]}")

    rb = len(bai) * so_rang_buoc
    ti_le = tong / rb if rb else 0.0
    dat = ti_le <= NGUONG
    print(f"\n  sạch {sach}/{len(bai)} bài · {tong}/{rb} ràng buộc = {ti_le:.1%}")
    if dem:
        print(f"  theo loại: {dict(dem)}")
    print(f"  ngưỡng {NGUONG:.0%} — {'ĐẠT' if dat else 'TRƯỢT'}")
    return dat


def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")

    goc = GOC / "evals" / "corpus" / "tho"
    # So rang buoc mot bai: so tieng + so cau + (2-4-6 moi cau) + van.
    dat_tt = _do(
        "THẤT NGÔN TỨ TUYỆT", goc / "tu-tuyet.txt", kiem_that_ngon_tu_tuyet, 4 + 1 + 4 * 3 + 2
    )
    dat_bc = _do(
        "THẤT NGÔN BÁT CÚ", goc / "bat-cu.txt", kiem_that_ngon_bat_cu, 8 + 1 + 8 * 3 + 4 + 2 * 3 + 4
    )

    print()
    if dat_tt and dat_bc:
        print("ĐẠT — cả hai thể đủ tin cậy để làm HÀM THƯỞNG cho RLVR.")
        return 0
    print("TRƯỢT — chưa được dùng làm hàm thưởng. Xem §4.2 docs/plan-rlvr-tho.md.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
