"""Hieu chuan bo kiem tra luat tho tren THO DA DUOC THUA NHAN.

Chay:
    uv run python ops/hieu_chuan_tho.py evals/corpus/tho/kieu.txt
    uv run python ops/hieu_chuan_tho.py evals/corpus/tho/*.txt --bang-trac

VI SAO CAN: bo kiem tra nay se duoc dung de CHAM model va de LOC du lieu huan luyen.
Mot bo chua hieu chuan se hong theo mot trong hai cach, va ca hai deu IM LANG:

  - bao loi GIA  -> ep model sinh lai vo ich -> TANG latency, dung thu dang muon giam
  - bo lot loi that -> tha tho sai luat ra cho nguoi dung

Nguyen tac: moi lan bo kiem tra bao mot cau Truyen Kieu la sai luat, gan nhu chac chan
la BO KIEM TRA SAI, khong phai Nguyen Du sai. Ti le bao loi gia la thu can do, va muc
tieu la gan 0%.

DINH DANG TEP: moi bai tho cach nhau bang MOT DONG TRONG. Trong mot bai, moi cau mot
dong. Dong bat dau bang '#' la chu thich, bi bo qua.

Chi phi: 0 dong, 0 lan goi model. Day la phan re nhat va co don bay cao nhat cua ca
bo tinh nang — xem docs/plan-lam-tho-va-tu-host.md muc 9.5.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tho import kiem_luc_bat

#: NGUONG theo TUNG CHIEU DO. Mot con so chung cho ca ba la sai.
#:
#: So tieng va so cau la LUAT CUNG va DEM DUOC — o do 0% bao loi gia la muc tieu that,
#: va da dat duoc (tho/sinh.py ep khung, do 11/09/2026: 12/12 bai).
#:
#: Van thi khong. Sau khi sua ba loi tach van va mo chin nhom van thong (xem
#: docs/plan-sua-bo-kiem-van.md), ti le tren Truyen Kieu con 17,0% — va phan con lai
#: KHONG duoi tiep duoc bang suy luan: no can mot ban in da kiem chung. Xem muc 7 cua
#: plan do: nhom nhieu dan chung nhat (`{a, ươ}`, 69 lan) lai la nhom khong the mo,
#: vi `đường ~ vàng` khong phai van tieng Viet.
#:
#: Nen nguong cho van la SO VOI MOC, khong phai so voi 0. Khong dep bang mot con so
#: tuyet doi, nhung no DUNG: no bat duoc hoi quy, va khong noi doi ve mot muc tieu
#: khong voi toi.
NGUONG: dict[str, float] = {
    "so_tieng": 0.01,
    "so_cau": 0.01,
    "bang_trac": 0.05,
}

#: Moc cua chieu VAN, do tren evals/corpus/tho/truyen-kieu.txt ngay 11/09/2026.
#:
#: Duong di toi con so nay, de lan sau co ai ha them thi biet minh dang o dau:
#:
#:     30,5%  truoc khi sua
#:     29,6%  + boc dau cau
#:     28,4%  + phu am `gi` boc xong con rong
#:     27,0%  + hop nhat `yê` voi `iê`
#:     17,0%  + chin nhom van thong khoa theo am cuoi
#:
#: HA duoc thi HA MOC XUONG theo. Tang len la hoi quy.
MOC_VAN = 0.17


def doc_bai(tep: Path) -> list[list[str]]:
    """Tach tep thanh cac bai, moi bai la mot list cau."""
    bai: list[list[str]] = []
    hien_tai: list[str] = []
    for dong in tep.read_text(encoding="utf-8").splitlines():
        d = dong.strip()
        if d.startswith("#"):
            continue
        if not d:
            if hien_tai:
                bai.append(hien_tai)
                hien_tai = []
            continue
        hien_tai.append(d)
    if hien_tai:
        bai.append(hien_tai)
    return bai


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    duong_dan = [a for a in sys.argv[1:] if not a.startswith("--")]
    bang_trac = "--bang-trac" in sys.argv[1:]
    if not duong_dan:
        print(__doc__, file=sys.stderr)
        return 2

    tong_bai = 0
    bai_sai = 0
    dem_loai: Counter[str] = Counter()
    vi_du: list[tuple[str, str]] = []

    for dd in duong_dan:
        tep = Path(dd)
        if not tep.exists():
            print(f"KHONG CO TEP: {tep}", file=sys.stderr)
            return 2
        for cau in doc_bai(tep):
            tong_bai += 1
            loi = kiem_luc_bat("\n".join(cau), kiem_bang_trac=bang_trac)
            if not loi:
                continue
            bai_sai += 1
            for x in loi:
                dem_loai[x.loai] += 1
            if len(vi_du) < 12:
                vi_du.append((" / ".join(cau[:2])[:60], f"câu {loi[0].cau}: {loi[0].mo_ta}"))

    if tong_bai == 0:
        print("Khong doc duoc bai nao. Xem lai dinh dang tep.", file=sys.stderr)
        return 2

    ti_le = bai_sai / tong_bai
    print(f"{tong_bai} bài · kiểm bằng-trắc: {'CÓ' if bang_trac else 'KHÔNG'}\n")
    print(f"  Báo lỗi trên thơ đã được thừa nhận: {bai_sai}/{tong_bai} = {ti_le:.1%}")
    print("  (đây là tỉ lệ BÁO LỖI GIẢ — xem ngưỡng từng chiều ở cuối)\n")

    if dem_loai:
        print("  Theo loại lỗi:")
        for loai, n in dem_loai.most_common():
            print(f"    {loai:<12} {n}")

    if vi_du:
        print("\n  Ví dụ (mỗi dòng là một chỗ bộ kiểm tra NGHI là sai luật):")
        for tho, mo_ta in vi_du:
            print(f"    {tho}")
            print(f"      -> {mo_ta}")

    # Nghiem thu theo TUNG CHIEU, khong gop mot con so. Xem `NGUONG`.
    print()
    hong: list[str] = []
    for loai, nguong in NGUONG.items():
        tl = dem_loai.get(loai, 0) / tong_bai
        dat = tl <= nguong
        print(f"  {loai:<12} {tl:6.1%}  ngưỡng {nguong:5.1%}  {'ĐẠT' if dat else 'CHƯA ĐẠT'}")
        if not dat:
            hong.append(loai)

    tl_van = dem_loai.get("van", 0) / tong_bai
    dat_van = tl_van <= MOC_VAN + 1e-9
    print(f"  {'van':<12} {tl_van:6.1%}  mốc    {MOC_VAN:5.1%}  {'ĐẠT' if dat_van else 'HỒI QUY'}")
    if not dat_van:
        hong.append("van")
    elif tl_van < MOC_VAN - 0.005:
        # Tot hon moc thi PHAI ha moc, khong thi lan sau mot hoi quy nho se lot.
        print(f"\n  → Tốt hơn mốc. HẠ `MOC_VAN` xuống {tl_van:.3f} trong ops/hieu_chuan_tho.py.")

    print()
    if not hong:
        print("ĐẠT — bộ kiểm tra đủ tin cậy để đem đi chấm model.")
        return 0
    print(f"CHƯA ĐẠT ở: {', '.join(hong)} — sửa trước khi dùng nó để chấm model.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
