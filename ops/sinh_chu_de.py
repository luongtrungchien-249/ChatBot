"""Sinh BO CHU DE huan luyen cho RLVR. Buoc 5 cua docs/plan-rlvr-tho.md.

    uv run python ops/sinh_chu_de.py

DIEM DAT GIA NHAT CUA RLVR O DAY: khong can tap tho co nhan.

Huan luyen bang preference thi phai co nguoi xep hang hang nghin cap — tôn kem, chu
quan, va nhieu. RLVR thi phan thuong sinh ra tu verifier, nen du lieu huan luyen chi
can DANH SACH CHU DE. Ma danh sach chu de thi sinh bang code duoc.

TACH TRAIN / TEST KHONG GIAO NHAU — rang buoc quan trong nhat cua tep nay.

§6.3 cua plan doi nghiem thu tren chu de CHUA TUNG THAY khi train. Neu hai tap giao
nhau thi con so nghiem thu do "model da thuoc bai" chu khong do "model da hoc luat" —
va sai lech do IM LANG, khong co gi bao.

Tach theo CHU THE chu khong tach ngau nhien tren danh sach cuoi: chia ngau nhien thi
"mẹ gánh hàng rong" vao train con "mẹ ru con" vao test, hai cai gan nhau qua. Tach theo
chu the thi ca cum "mẹ" nam tron mot ben.

KHONG GOI MODEL, khong mang. Chay trong mili-giay va lap lai duoc — cung ly do voi
ops/dung_bang_van.py.
"""

import argparse
import json
import random
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent

#: CHU THE — cai bai tho noi VE. Tach train/test theo chinh truc nay.
#:
#: Chon toan chu de co trong von tho Viet: tho luat viet ve nhung thu nay se tu nhien
#: hon la viet ve "blockchain". Muc tieu cua RLVR o day la LUAT, nen de bai khong nen
#: them mot cai kho thu hai.
CHU_THE: tuple[str, ...] = (
    "mẹ", "cha", "bà ngoại", "ông nội", "người chị", "đứa em nhỏ",
    "người thầy", "mái trường", "bạn cũ", "người lính", "người nông dân",
    "cô lái đò", "bà bán hàng rong", "người thợ rèn", "chị gánh nước",
    "quê hương", "làng quê", "mái đình", "cây đa đầu làng", "bến sông",
    "con đò", "giếng nước", "chợ quê", "lũy tre", "cánh đồng",
    "mùa xuân", "mùa hạ", "mùa thu", "mùa đông", "đêm trăng",
    "chiều mưa", "sớm mai", "hoàng hôn", "đêm khuya", "ngày giáp Tết",
    "dòng sông", "ngọn núi", "biển cả", "cơn mưa rào", "gió heo may",
    "hoa sen", "hoa cau", "tiếng ve", "cánh cò", "con trâu",
    "nỗi nhớ nhà", "lòng biết ơn", "tình bạn", "sự chia xa", "niềm hy vọng",
    "công ơn dưỡng dục", "đạo hiếu", "uống nước nhớ nguồn", "tình yêu đất nước",
    "người con gái Việt xưa", "tà áo dài", "nón lá", "tiếng ru",
)

#: GOC NHIN — cung mot chu the, nhieu cach vao bai. Nhan so luong chu de len.
#:
#: Dung chung cho ca train lan test: goc nhin KHONG phai truc tach, vi no khong mang
#: noi dung rieng. Tach ca goc nhin nua se lam test lech ve mot kieu de bai.
GOC_NHIN: tuple[str, ...] = (
    "",
    "nỗi nhớ về {}",
    "{} trong ký ức tuổi thơ",
    "{} một chiều cuối năm",
    "lời cảm ơn gửi tới {}",
    "{} nhìn từ xa quê",
    "{} và những gì đã mất",
    "vẻ đẹp lặng lẽ của {}",
)

#: Ti le chu the danh cho TEST.
TI_LE_TEST = 0.25

#: Hat giong. Co dinh de bo chu de LAP LAI DUOC — doi hat giong la doi ca phep do.
HAT_GIONG = 20260914


def sinh(the_tho: str = "luc_bat") -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """`(train, test)`. Chu the cua hai tap KHONG giao nhau."""
    rng = random.Random(HAT_GIONG)
    chu_the = list(CHU_THE)
    rng.shuffle(chu_the)
    cat = int(len(chu_the) * TI_LE_TEST)
    ct_test, ct_train = set(chu_the[:cat]), set(chu_the[cat:])

    def lam(tap: set[str]) -> list[dict[str, str]]:
        ra: list[dict[str, str]] = []
        for ct in sorted(tap):
            for mau in GOC_NHIN:
                ra.append({"chu_de": mau.format(ct) if mau else ct, "the_tho": the_tho})
        rng.shuffle(ra)
        return ra

    return lam(ct_train), lam(ct_test)


def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")

    bo = argparse.ArgumentParser(description="Sinh bo chu de huan luyen RLVR")
    bo.add_argument("--the-tho", default="luc_bat", choices=("luc_bat", "that_ngon_bat_cu"))
    bo.add_argument("--ra", type=Path, default=GOC / "rlvr" / "du_lieu")
    tham = bo.parse_args()

    train, test = sinh(tham.the_tho)

    # KIEM BAT BIEN NGAY TAI DAY, khong de cho test bat: tep nay sinh du lieu huan
    # luyen, va mot lan giao nhau lot qua la ca phep nghiem thu thanh vo nghia.
    giao = {x["chu_de"] for x in train} & {x["chu_de"] for x in test}
    if giao:
        print(f"HONG: {len(giao)} chu de nam o CA HAI tap — {sorted(giao)[:5]}", file=sys.stderr)
        return 1

    tham.ra.mkdir(parents=True, exist_ok=True)
    for ten, tap in (("train", train), ("test", test)):
        p = tham.ra / f"chu_de_{ten}.jsonl"
        p.write_text(
            "\n".join(json.dumps(x, ensure_ascii=False) for x in tap) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"{ten:<6} {len(tap):>5} chủ đề  ->  {p.relative_to(GOC)}")

    print(f"\nchủ thể: {len(CHU_THE)} · góc nhìn: {len(GOC_NHIN)} · hạt giống {HAT_GIONG}")
    print("hai tập KHÔNG giao nhau (đã kiểm)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
