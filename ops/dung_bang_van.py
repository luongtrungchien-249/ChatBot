"""Sinh `src/tho/bang_van.py` — bang chu CO THAT, tra theo van.

Chay:
    uv run python ops/dung_bang_van.py

VI SAO SINH RA TEP THAY VI DOC LUC CHAY: `src/tho/` khong duoc phu thuoc `evals/`.
Corpus nam trong evals/, va src/ phai chay duoc ma khong co no. Sinh mot lan thanh hang
so thi tho/ tu chua du lieu cua minh, khong doc tep nao luc import.

NGUON TU VUNG:
  - evals/corpus/tho/truyen-kieu.txt — CHI lay tieng o VI TRI VAN, tuc nhung chu that
    su duoc dung de gieo van trong tho. Het han bao ho.
  - src/tho/tu_vung.py — tu ghep hai tieng tu soan, tra theo van cua tieng CUOI.

CHI GIU THANH BANG: van luc bat la van bang.

XEP THEO TAN SUAT roi cat ngon. Kieu co tu co (`đàng`, `tràng`, `tòng`), va tan suat la
cach loc re nhat: chu hay dung thi thuong la chu con song.
"""

import sys
from collections import Counter, defaultdict
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "src"))

from tho.luat import la_bang, lay_van  # noqa: E402
from tho.tu_vung import TU_GHEP  # noqa: E402

CORPUS = GOC / "evals" / "corpus" / "tho" / "truyen-kieu.txt"
RA = GOC / "src" / "tho" / "bang_van.py"

#: So chu toi da moi nhom. Dai hon khong giup: bang di vao prompt, va prompt dai them
#: thi loang cac rang buoc khac — da do duoc o v4 (prompt +762 ky tu, van -1,25).
TOI_DA = 12

#: Nhom it hon ngan nay thi bo: mot nhom hai ba chu khong cho model lua chon gi.
TOI_THIEU = 5


def _muc(van: str, ds: list[str]) -> list[str]:
    """Mot muc dict, tu xuong dong khi qua 100 cot.

    Tuple MOT phan tu phai co dau phay cuoi, khong thi `("x")` la mot chuoi chu khong
    phai tuple — mypy bat duoc, nhung sua o BO SINH chu khong sua tay tep sinh ra.
    """
    phan = [f'"{x}"' for x in ds]
    mot_dong = f'    "{van}": ({", ".join(phan)}{"," if len(phan) == 1 else ""}),'
    if len(mot_dong) <= 100:
        return [mot_dong]
    ra = [f'    "{van}": (']
    dong_hien = "        "
    for x in phan:
        them = x + ","
        if len(dong_hien) + len(them) + 1 > 99:
            ra.append(dong_hien.rstrip())
            dong_hien = "        "
        dong_hien += them + " "
    ra.append(dong_hien.rstrip())
    ra.append("    ),")
    return ra


def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")

    if not CORPUS.exists():
        print(f"KHONG CO CORPUS: {CORPUS}", file=sys.stderr)
        return 2

    cau = [
        d.strip()
        for d in CORPUS.read_text(encoding="utf-8").splitlines()
        if d.strip() and not d.startswith("#")
    ]

    # Chi tieng o VI TRI VAN.
    tan_suat: Counter[str] = Counter()
    for c in cau:
        t = c.split()
        if len(t) == 6:
            tan_suat[t[5].lower()] += 1
        elif len(t) == 8:
            tan_suat[t[5].lower()] += 1
            tan_suat[t[7].lower()] += 1

    nhom: dict[str, list[str]] = defaultdict(list)
    for chu, _ in tan_suat.most_common():
        if la_bang(chu) and chu.isalpha():
            nhom[lay_van(chu)].append(chu)

    ghep: dict[str, list[str]] = defaultdict(list)
    for tu in sorted(TU_GHEP):
        cuoi = tu.split()[1]
        if la_bang(cuoi):
            ghep[lay_van(cuoi)].append(tu)

    giu = {v: ds[:TOI_DA] for v, ds in nhom.items() if len(ds) >= TOI_THIEU}
    print(f"{len(cau)} câu · {len(tan_suat)} tiếng ở vị trí vần")
    print(f"{len(nhom)} nhóm vần · giữ {len(giu)} nhóm có >= {TOI_THIEU} chữ")
    print(f"{len(ghep)} nhóm từ ghép hai tiếng")

    dong = [
        '"""Bang chu CO THAT, tra theo van. TEP NAY DUOC SINH RA — dung sua tay.',
        "",
        "    uv run python ops/dung_bang_van.py",
        "",
        "VI SAO TON TAI: model be chu (`ngọt ngào` -> `ngọt ngao`) khong phai vi no sai",
        "chinh ta, ma vi no BI TU VAN — viet toi vi tri van thi khong co san chu that nao",
        "vua hop van vua hop nghia. Bang nay dua san chu that cho no chon.",
        "",
        "LA GOI Y, KHONG PHAI RANG BUOC. «Chon van truoc» — ep dung nhung chu do o dung",
        "nhung vi tri do — da lam diem sap tu 69,7 xuong 57,1/100. Khac biet nam o cho:",
        "bang nay MO RONG lua chon, khong thu hep no.",
        "",
        "Nguon: vi tri van cua 3.254 cau Truyen Kieu (het han bao ho) + tho/tu_vung.py.",
        "Chi thanh bang, xep theo tan suat roi cat ngon.",
        '"""',
        "",
        "#: van -> cac TIENG that cung van, thanh bang, xep theo tan suat giam dan.",
        "CHU_THEO_VAN: dict[str, tuple[str, ...]] = {",
    ]
    for v in sorted(giu, key=lambda x: (-len(giu[x]), x)):
        dong += _muc(v, giu[v])
    dong += [
        "}",
        "",
        "#: van cua tieng CUOI -> cac TU GHEP hai tieng. Nguon: tho/tu_vung.py.",
        "TU_THEO_VAN: dict[str, tuple[str, ...]] = {",
    ]
    for v in sorted(ghep, key=lambda x: (-len(ghep[x]), x)):
        dong += _muc(v, ghep[v][:TOI_DA])
    dong += ["}", ""]

    RA.write_text("\n".join(dong), encoding="utf-8", newline="\n")
    print(f"-> {RA}")

    lon = sum(1 for ds in giu.values() if len(ds) >= 8)
    print(f"\nnhóm có >= 8 chữ: {lon}/{len(giu)}")
    if lon < 30:
        print("CHƯA ĐẠT — plan mục 5 đòi >= 30 nhóm có >= 8 chữ.")
        return 1
    print("ĐẠT.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
