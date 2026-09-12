"""Sinh `src/tho/tu_ghep_wiktionary.py` — tu ghep HAI TIENG tieng Viet.

Chay:
    # 1. Tai du lieu (79 MB, KHONG commit vao repo)
    curl -L -o /tmp/vi.jsonl \\
      https://kaikki.org/dictionary/Vietnamese/kaikki.org-dictionary-Vietnamese.jsonl
    # 2. Trich ra tep dan xuat
    uv run python ops/dung_tu_ghep.py /tmp/vi.jsonl

NGUON VA GIAY PHEP
------------------
Du lieu goc: Wiktionary tieng Anh, trich bang `wiktextract`, phan phoi qua kaikki.org.
Noi dung Wiktionary o duoi **CC BY-SA 4.0** (va GFDL).

Nghia vu di kem: GHI NGUON va CHIA SE TUONG TU **tren chinh du lieu**. Tep sinh ra la
mot ban trich — tuc mot tac pham phai sinh — nen no mang theo cung giay phep, va dieu
do duoc ghi ngay trong docstring cua tep do. Xem them muc "Ghi cong" trong README.

VI SAO CHI COMMIT BAN TRICH, KHONG COMMIT 79 MB GOC: ta chi can danh sach tu, khong can
nghia, phat am, tu nguyen. Ban trich nho hon vai tram lan va doc duoc bang mat — tuc
review duoc, va do la dieu quan trong voi mot tep se quyet dinh tho nao bi loai.

VI SAO SINH RA TEP THAY VI DOC LUC CHAY: `src/tho/` phai chay duoc ma khong co mang va
khong co tep 79 MB. Cung ly do voi `ops/dung_bang_van.py`.
"""

import argparse
import json
import sys
import unicodedata
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
RA = GOC / "src" / "tho" / "tu_ghep_wiktionary.py"

#: Tu loai GIU LAI. Bo `name` (ten rieng) va `romanization`: ten rieng khong giup phan
#: biet "ngọt ngào" voi "ngọt ngao", con romanization la chu Latin hoa cua tieng khac.
POS_GIU = frozenset(
    {"noun", "verb", "adj", "adv", "intj", "pron", "conj", "phrase", "num", "prep", "particle"}
)

#: Ky tu hop le trong mot tieng Viet (da bo dau thanh khi kiem).
_CHU = frozenset("aăâbcdđeêghiklmnoôơpqrstuưvxy")


def _thuan_viet(tu: str) -> bool:
    """Ca hai tieng chi gom chu cai tieng Viet.

    Loai cac muc lan chu so, dau cham, ky tu Latin khong co trong tieng Viet (f, j, w,
    z) — chung la tu muon hoac vien tat, khong giup gi cho viec bat chu bi be.
    """
    for tieng in tu.split():
        khong_dau = "".join(
            c for c in unicodedata.normalize("NFD", tieng.lower()) if not unicodedata.combining(c)
        )
        if not khong_dau or any(c not in _CHU for c in khong_dau):
            return False
    return True


def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")

    bo = argparse.ArgumentParser(description="Trich tu ghep hai tieng tu du lieu kaikki.org")
    bo.add_argument("nguon", type=Path, help="tep .jsonl tai tu kaikki.org")
    tham = bo.parse_args()

    if not tham.nguon.exists():
        print(f"KHONG CO TEP: {tham.nguon}", file=sys.stderr)
        return 2

    tu_ghep: set[str] = set()
    tong = bo_pos = bo_chu = 0
    with tham.nguon.open(encoding="utf-8") as f:
        for dong in f:
            try:
                x = json.loads(dong)
            except json.JSONDecodeError:
                continue
            tong += 1
            if x.get("lang_code") != "vi":
                continue
            tu = str(x.get("word", "")).strip().lower()
            if len(tu.split()) != 2:
                continue
            if x.get("pos") not in POS_GIU:
                bo_pos += 1
                continue
            if not _thuan_viet(tu):
                bo_chu += 1
                continue
            tu_ghep.add(tu)

    print(f"{tong} mục · giữ {len(tu_ghep)} từ ghép hai tiếng")
    print(f"  bỏ vì từ loại  : {bo_pos}")
    print(f"  bỏ vì ký tự    : {bo_chu}")

    dong = [
        '"""Tu ghep HAI TIENG tieng Viet. TEP NAY DUOC SINH RA — dung sua tay.',
        "",
        "    uv run python ops/dung_tu_ghep.py <tep .jsonl tu kaikki.org>",
        "",
        "NGUON: Wiktionary tieng Anh, trich bang wiktextract, phan phoi qua kaikki.org.",
        "GIAY PHEP: CC BY-SA 4.0 (va GFDL) — giay phep cua chinh Wiktionary.",
        "",
        "Tep nay la mot BAN TRICH cua du lieu do, tuc mot tac pham phai sinh, nen no mang",
        "theo cung giay phep. Nghia vu: ghi nguon va chia se tuong tu TREN DU LIEU.",
        "",
        "DUNG DE LAM GI: bat cum bi BE cho van — «ngọt ngào» -> «ngọt ngao». Xem",
        "tho/tu_vung.py. Danh sach nay chi tra loi «cum nay co phai tu that khong», khong",
        "tra loi «cum nay co nghia gi».",
        '"""',
        "",
        "TU_GHEP_WIKT: frozenset[str] = frozenset(",
        "    {",
    ]
    for tu in sorted(tu_ghep):
        dong.append(f'        "{tu}",')
    dong += ["    }", ")", ""]

    RA.write_text("\n".join(dong), encoding="utf-8", newline="\n")
    kb = RA.stat().st_size / 1024
    print(f"-> {RA}  ({kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
