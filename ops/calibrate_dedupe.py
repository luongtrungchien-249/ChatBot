"""Do NGUONG chong trung cua L3 tren cap cau tieng Viet that.

ARCHITECTURE.md va master-plan deu ghi "cosine > 0,9" — con so do viet TRUOC khi co
mot phep do nao, va no khong dung voi `text-embedding-3-large` o 1024 chieu. Script
nay do that de nguong la mot lua chon co can cu.

Ba nhom cap cau, va nguong phai tach duoc chung:

  TRUNG      cung mot y, khac cach dien dat  -> phai >= DUPLICATE_THRESHOLD
  MAU THUAN  cung chu de, noi dung loai tru  -> phai >= DUPLICATE_THRESHOLD
             (de vao nhanh Replace: revoke cai cu, chen cai moi)
  KHAC       khong lien quan                 -> phai <  DUPLICATE_THRESHOLD

Nham nguong theo huong nao cung hong, nhung hong khac nhau:
  Nguong QUA CAO -> bang day cac bien the cua cung mot cau, tat ca deu vao prompt.
  Nguong QUA THAP -> fact moi nuot fact cu, nguoi dung mat thong tin ma khong biet.

DO NAY TON TIEN THAT (rat it). Chay lai khi doi model embedding.
Chay: uv run python ops/calibrate_dedupe.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from llm.embedder import get_embedder
from memory.dedupe import DUPLICATE_THRESHOLD, FORGET_THRESHOLD, cosine

TRUNG: list[tuple[str, str]] = [
    ("Nam làm backend Node.js", "Nam phụ trách phần backend"),
    ("Nhóm họp thứ 3 hàng tuần", "Nhóm này họp vào thứ ba mỗi tuần"),
    ("Gọi tôi là anh Nam", "Hãy xưng hô với tôi là anh Nam"),
    ("Dự án tên là Hoshi", "Tên dự án là Hoshi"),
]

MAU_THUAN: list[tuple[str, str]] = [
    ("Nam làm ở công ty A", "Nam làm ở công ty B"),
    ("Deadline báo cáo là 30/11", "Deadline báo cáo là 15/12"),
    ("Nhóm họp thứ 3 hàng tuần", "Nhóm họp thứ 5 hàng tuần"),
]

#: Ca kho nhat, va la ca quyet dinh nguong: HAI FACT KHAC NHAU VE CUNG MOT NGUOI.
#:
#: Dedupe loc theo subject_id truoc khi so sanh, nen cac cap "khac chu de hoan toan"
#: gan nhu khong bao gio gap nhau trong thuc te. Cai thuc su xay ra la hai dieu khac
#: nhau ve cung mot nguoi — va chung PHAI cung ton tai. Nguong qua thap thi fact moi
#: revoke fact cu, nguoi dung mat thong tin ma khong he duoc bao.
KHAC: list[tuple[str, str]] = [
    # Cung mot nguoi, hai dieu khac nhau — phai giu ca hai.
    ("Nam làm backend Node.js", "Nam học đại học Bách khoa"),
    ("Nam làm backend Node.js", "Nam thích uống cà phê đen"),
    ("Gọi tôi là anh Nam", "Nam làm backend Node.js"),
    # Cung mot nhom, hai dieu khac nhau.
    ("Nhóm họp thứ 3 hàng tuần", "Nhóm có 12 thành viên"),
    ("Deadline báo cáo là 30/11", "Ngân sách dự án là 200 triệu"),
    # Khac chu de hoan toan — de lam moc duoi.
    ("Nam làm backend Node.js", "Nhóm họp thứ 3 hàng tuần"),
    ("Dự án tên là Hoshi", "Gọi tôi là anh Nam"),
]


#: Nguoi dung go `quen <noi dung>` bang loi cua ho, khong phai nguyen van fact.
#: Nguong o day chi dan toi mot cau HOI XAC NHAN nen no duoc phep rong: bo sot thi
#: lenh `quen` im lang khong lam gi — nguoi dung tuong da xoa ma thuc ra chua.
QUEN: list[tuple[str, str]] = [
    ("chỗ làm của tôi", "Nam làm ở công ty A"),
    ("nghề nghiệp", "Nam làm backend Node.js"),
    ("lịch họp", "Nhóm họp thứ 3 hàng tuần"),
    ("cách xưng hô", "Gọi tôi là anh Nam"),
]


async def do_nhom(ten: str, cap: list[tuple[str, str]]) -> list[float]:
    texts = [t for pair in cap for t in pair]
    vectors = await get_embedder().embed(texts)
    scores = [cosine(vectors[i], vectors[i + 1]) for i in range(0, len(vectors), 2)]

    print(f"\n{ten}")
    for (a, b), score in zip(cap, scores, strict=True):
        print(f"  {score:.3f}  {a[:38]:<38} | {b[:38]}")
    return scores


async def main() -> int:
    trung = await do_nhom("TRUNG — phai >= nguong", TRUNG)
    mau_thuan = await do_nhom("MAU THUAN — phai >= nguong", MAU_THUAN)
    khac = await do_nhom("KHAC — phai < nguong", KHAC)

    # Nguong phai nam giua "cai thap nhat can bat" va "cai cao nhat can bo qua".
    can_bat = min(trung + mau_thuan)
    can_bo = max(khac)
    print(f"\n  Thap nhat trong nhom can BAT:  {can_bat:.3f}")
    print(f"  Cao nhat trong nhom can BO QUA: {can_bo:.3f}")

    if can_bo >= can_bat:
        print("\n  >> KHONG CO NGUONG NAO TACH DUOC hai nhom. Xem lai cac cap mau,")
        print("     hoac model embedding khong phan biet duoc loai fact nay.")
        return 1

    # KHONG lay diem giua: hai huong sai khong ngang nhau.
    #   Nguong cao qua -> bang co ban trung. Phien, ton cho trong prompt, KHONG mat gi.
    #   Nguong thap qua -> fact moi revoke fact cu. MAT THONG TIN, va im lang.
    # Nen lech ve phia cao, chi chua mot bien an nho duoi `can_bat`.
    de_xuat = round(can_bat - 0.04, 2)
    print(f"\n  Khoang an toan: ({can_bo:.3f}, {can_bat:.3f})")
    print(f"  De xuat (lech len tren vi mat thong tin nang hon trung lap): {de_xuat}")
    print(f"  Dang dung: DUPLICATE_THRESHOLD = {DUPLICATE_THRESHOLD}")

    quen = await do_nhom("QUEN — cach nguoi dung noi, phai >= FORGET_THRESHOLD", QUEN)
    can_bat_quen = min(quen)
    print(f"\n  Thap nhat trong nhom QUEN: {can_bat_quen:.3f}")
    print(f"  Dang dung: FORGET_THRESHOLD = {FORGET_THRESHOLD}")

    loi = 0
    if not (can_bo < DUPLICATE_THRESHOLD <= can_bat):
        print("\n  >> DUPLICATE_THRESHOLD NAM NGOAI KHOANG AN TOAN — sua memory/dedupe.py")
        loi = 1
    if can_bat_quen < FORGET_THRESHOLD:
        print("\n  >> FORGET_THRESHOLD QUA CAO: lenh `quen` se khong tim thay gi.")
        loi = 1
    return loi


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
