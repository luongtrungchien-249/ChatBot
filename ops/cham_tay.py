"""CHAM TAY — hieu chuan nguoi cham bang NGUOI. Buoc 3-4 cua docs/plan-danh-gia-tong-the.md.

    uv run python ops/cham_tay.py           # bat dau / tiep tuc cham
    uv run python ops/cham_tay.py --do      # do tuong quan sau khi cham xong

VI SAO CAN. Toan bo cot "noi dung" cua evals/runner_tho.py hien la MODEL CHAM MODEL. Ta
neo no bang ca dao va van xuoi, nhung ca hai diem neo do cung do chinh model dinh vi.
Chua ai biet `ngon ngu 6,00` co tuong ung voi cam nhan cua nguoi doc khong.

Day la manh DUY NHAT cua bo danh gia ma may khong tu dung duoc.

--------------------------------------------------------------------------------
BA QUY TAC CUA PHEP NAY, va vi sao pha mot cai la hong ca phep
--------------------------------------------------------------------------------

1. GIAU DIEM MAY. Thay diem may truoc thi diem nguoi bi keo theo no, va ta do duoc
   "nguoi co dong y voi may khong" thay vi "may co dung khong". Hai cau hoi khac nhau.

2. TRON NEO, GIAU NHAN. Ca dao va van xuoi di lan vao giua, khong noi cai nao la cai
   nao. Biet truoc la ca dao thi diem bi keo theo ky vong — va ta mat luon cai moc.

3. NGAU NHIEN CO HAT GIONG. Thu tu hien bai co dinh theo hat giong, de cham dang do roi
   nghi va quay lai van ra dung thu tu do.

BA MUC, KHONG PHAI SAU. `nhip` thi may chi kiem duoc mot phan; `y nghia` va `cam xuc`
kho nhat quan khi cham tay. Ba muc o day la ba muc co khoang cach LON NHAT toi ca dao,
tuc ba muc dang tin cay hoa nhat.
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "src"))

SO_KET_QUA = GOC / "evals" / "tho" / "so_ket_qua.jsonl"
RA = GOC / "evals" / "tho" / "cham_tay.jsonl"
BAI_DA_SINH = GOC / "evals" / "tho" / "bai_da_sinh.jsonl"

#: Hat giong co dinh — xem quy tac 3.
HAT_GIONG = 20260915

#: Ba muc cham tay. Thang 0-10 het, ke ca `sang_tao` (may cham /5) — de nguoi khong
#: phai doi thang giua cac muc. Quy doi khi DO tuong quan, khong quy doi khi cham.
MUC: tuple[tuple[str, str], ...] = (
    ("ngon_ngu", "có chữ nào bị nhét vào CHỈ ĐỂ ép vần không? (0 = đầy chữ vô nghĩa)"),
    ("hinh_anh", "có hình ảnh thật, cụ thể, gợi được không? (0 = toàn sáo ngữ)"),
    ("sang_tao", "có gì mới không, hay chỉ lặp cái ai cũng viết được?"),
)

NEO_TREN: tuple[str, ...] = (
    "Công cha như núi Thái Sơn\nNghĩa mẹ như nước trong nguồn chảy ra\n"
    "Một lòng thờ mẹ kính cha\nCho tròn chữ hiếu mới là đạo con",
    "Anh đi anh nhớ quê nhà\nNhớ canh rau muống nhớ cà dầm tương\n"
    "Nhớ ai dãi nắng dầm sương\nNhớ ai tát nước bên đường hôm nao",
    "Trong đầm gì đẹp bằng sen\nLá xanh bông trắng lại chen nhị vàng\n"
    "Nhị vàng bông trắng lá xanh\nGần bùn mà chẳng hôi tanh mùi bùn",
)
NEO_DUOI: tuple[str, ...] = (
    "Hôm nay trời nắng đẹp lắm\nTôi đi ra chợ mua rau\n"
    "Rau hôm nay hơi đắt một chút\nNhưng mà vẫn phải mua thôi",
    "Hà Nội có nhiều đường phố\nMùa thu thì lá rụng nhiều\n"
    "Người ta hay đi chơi hồ\nTrời se lạnh vào buổi tối",
)


#: Mot ban ghi cham tay. Khai ro de mypy kiem duoc phep cong diem o `do_tuong_quan`.
BanGhi = dict[str, Any]


def _doc_jsonl(p: Path) -> list[BanGhi]:
    if not p.exists():
        return []
    return [json.loads(d) for d in p.read_text(encoding="utf-8").splitlines() if d.strip()]


def dung_bo_cham() -> list[BanGhi]:
    """30 bai cua bot (10 cao / 10 giua / 10 thap theo MAY) + 5 neo, tron lan."""
    bai = _doc_jsonl(BAI_DA_SINH)
    if len(bai) < 30:
        print(
            f"CHUA DU BAI: co {len(bai)}, can >= 30.\n\n"
            "  uv run python evals/runner_tho.py --luu-bai\n\n"
            "Lan chay danh gia phai duoc luu bai lai thi moi cham tay duoc.",
            file=sys.stderr,
        )
        return []

    co_diem = [b for b in bai if isinstance(b.get("may"), dict) and b["may"]]
    co_diem.sort(key=lambda b: sum(b["may"].values()), reverse=True)
    n = len(co_diem)
    giua = n // 2
    chon = co_diem[:10] + co_diem[giua - 5 : giua + 5] + co_diem[-10:]

    bo: list[BanGhi] = [
        {"id": f"bot-{i}", "loai": "bot", "tho": b["tho"], "may": b["may"]}
        for i, b in enumerate(chon)
    ]
    bo += [{"id": f"tren-{i}", "loai": "neo_tren", "tho": t, "may": None}
           for i, t in enumerate(NEO_TREN)]
    bo += [{"id": f"duoi-{i}", "loai": "neo_duoi", "tho": t, "may": None}
           for i, t in enumerate(NEO_DUOI)]

    random.Random(HAT_GIONG).shuffle(bo)
    return bo


def cham() -> int:
    bo = dung_bo_cham()
    if not bo:
        return 2

    xong = {str(x["id"]) for x in _doc_jsonl(RA)}
    con = [b for b in bo if str(b["id"]) not in xong]
    if not con:
        print(f"Đã chấm hết {len(bo)} bài.\n\n  uv run python ops/cham_tay.py --do")
        return 0

    print(f"Chấm tay — còn {len(con)}/{len(bo)} bài.  Ctrl+C để dừng, chạy lại sẽ tiếp.")
    print("Mỗi mục cho điểm 0-10. Gõ 'b' để bỏ qua một bài.\n")

    RA.parent.mkdir(parents=True, exist_ok=True)
    for i, b in enumerate(con, 1):
        print("=" * 66)
        print(f"[{i}/{len(con)}]")
        print("=" * 66)
        print(b["tho"])
        print()
        diem: dict[str, float] = {}
        bo_qua = False
        for ma, hoi in MUC:
            while True:
                try:
                    tra = input(f"  {ma:<10} 0-10  ({hoi})\n  > ").strip().lower()
                except EOFError:
                    # Chay khong co terminal (CI, pipe, cong cu tu dong). Bao ro thay vi
                    # nem traceback — va noi luon vi sao viec nay khong tu dong hoa duoc.
                    print(
                        "\n\nKHONG CO TERMINAL — cong cu nay cho NGUOI go diem.\n\n"
                        "    uv run python ops/cham_tay.py\n\n"
                        "Khong tu dong hoa duoc, va do la CHU DICH: ca phep hieu chuan "
                        "ton tai\nde thoat khoi viec model cham model.",
                        file=sys.stderr,
                    )
                    return 2
                except KeyboardInterrupt:
                    print("\n\nDung lai. Chay lai se tiep dung cho.")
                    return 0
                if tra == "b":
                    bo_qua = True
                    break
                try:
                    v = float(tra.replace(",", "."))
                except ValueError:
                    print("  -> nhập một số 0-10, hoặc 'b'")
                    continue
                if 0.0 <= v <= 10.0:
                    diem[ma] = v
                    break
                print("  -> phải trong 0-10")
            if bo_qua:
                break
        if bo_qua:
            print("  (bỏ qua)\n")
            continue
        with RA.open("a", encoding="utf-8", newline="\n") as f:
            f.write(
                json.dumps({"id": b["id"], "loai": b["loai"], "nguoi": diem}, ensure_ascii=False)
                + "\n"
            )
        print()
    print(f"Xong. Đã ghi vào {RA.relative_to(GOC)}\n\n  uv run python ops/cham_tay.py --do")
    return 0


def _spearman(a: list[float], b: list[float]) -> float:
    """Tuong quan hang Spearman. Tu viet de khong them phu thuoc."""
    def hang(xs: list[float]) -> list[float]:
        sap = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0.0] * len(xs)
        i = 0
        while i < len(sap):
            j = i
            while j + 1 < len(sap) and xs[sap[j + 1]] == xs[sap[i]]:
                j += 1
            tb = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[sap[k]] = tb
            i = j + 1
        return r

    ra, rb = hang(a), hang(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    tu = sum((x - ma) * (y - mb) for x, y in zip(ra, rb, strict=True))
    mau = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return tu / mau if mau else 0.0


def do_tuong_quan() -> int:
    nguoi = {str(x["id"]): x for x in _doc_jsonl(RA)}
    bo = {str(b["id"]): b for b in dung_bo_cham()}
    if not nguoi:
        print("CHUA CHAM GI. Chay: uv run python ops/cham_tay.py", file=sys.stderr)
        return 2

    print("=" * 70)
    print(f"TUONG QUAN NGUOI vs MAY — {len(nguoi)} bai da cham")
    print("=" * 70)

    cap = [
        (nguoi[i], bo[i]) for i in nguoi if i in bo and bo[i]["loai"] == "bot"
    ]
    if len(cap) < 10:
        print(f"  chi {len(cap)} bai cua bot — can >= 10 de do tuong quan", file=sys.stderr)
    else:
        print(f"\n  {'muc':<12}{'Spearman':>10}{'n':>6}   ket luan")
        for ma, _ in MUC:
            # `sang_tao` may cham /5, nguoi cham /10 -> Spearman la tuong quan HANG nen
            # khong can quy doi thang.
            a = [float(x["nguoi"][ma]) for x, _ in cap]
            b = [float(y["may"][ma]) for _, y in cap]
            r = _spearman(a, b)
            if r >= 0.6:
                kl = "DUNG DUOC"
            elif r >= 0.3:
                kl = "chi de XEP HANG"
            else:
                kl = "KHONG DO DUNG THU"
            print(f"  {ma:<12}{r:>10.2f}{len(a):>6}   {kl}")

    print("\n  NEO — nguoi co tach duoc ba nhom khong:")
    for loai, ten in (("neo_tren", "ca dao"), ("bot", "bot"), ("neo_duoi", "van xuoi")):
        d = [
            sum(float(v) for v in x["nguoi"].values())
            for i, x in nguoi.items()
            if i in bo and bo[i]["loai"] == loai
        ]
        if d:
            print(f"    {ten:<10} {sum(d) / len(d):6.2f}/30   (n={len(d)})")
    print("\n  Neu nguoi KHONG tach duoc ba nhom thi chinh bai toan dang mo ho,")
    print("  chu khong phai nguoi cham sai.")
    return 0


def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")
    bo = argparse.ArgumentParser(description="Cham tay de hieu chuan nguoi cham")
    bo.add_argument("--do", action="store_true", help="do tuong quan sau khi cham xong")
    return do_tuong_quan() if bo.parse_args().do else cham()


if __name__ == "__main__":
    sys.exit(main())
