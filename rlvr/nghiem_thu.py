"""Do nghiem thu RLVR: model GOC vs model DA HUAN LUYEN. Buoc 7 cua plan.

    uv run python rlvr/nghiem_thu.py --model Qwen/Qwen2.5-7B-Instruct --adapter rlvr/ket_qua

Do tren `chu_de_test.jsonl` — tap chu de CHUA TUNG THAY khi train (tach theo chu the,
xem ops/sinh_chu_de.py).

--------------------------------------------------------------------------------
COT "GIU" LA PHAN DE BO QUEN NHAT, va la phan quan trong nhat
--------------------------------------------------------------------------------

Toi uu thang vao luat se HY SINH chat tho neu khong canh. Model hoan toan co the hoc ra
nhung bai dung luat tuyet doi ma vo hon — va verifier se cham chung diem tuyet doi, vi
no chi biet dem tieng va do van.

Nen tep nay do BON thu, khong phai mot:

    DAT    ti le bai SACH LUAT tang co y nghia (Fisher, n >= 200)
    GIU    ngon ngu / hinh anh / y nghia (nguoi cham) KHONG tut qua 0,5
    GIU    chep bai mau = 0
    GIU    cum bi be khong tang

Mot lan chay chi cai thien cot DAT ma keo tut cot GIU thi la THAT BAI, du con so dau
bang co dep den may.
"""

import argparse
import asyncio
import json
import statistics
import sys
import uuid
from math import comb
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
for _p in ("src", "."):
    sys.path.insert(0, str(GOC / _p))

from evals.metrics.tho_hay import cham_tho_hay  # noqa: E402
from tho.luat import kiem_luc_bat  # noqa: E402
from tho.phan_thuong import phan_thuong  # noqa: E402
from tho.prompt import system_prompt, yeu_cau  # noqa: E402
from tho.sinh import so_cau_chep  # noqa: E402
from tho.tu_vung import cum_kha_nghi  # noqa: E402

#: Nguong cot GIU. Tut qua nguong la THAT BAI du ti le dung luat co tang.
NGUONG_TUT = 0.5


def fisher(a: int, b: int, c: int, d: int) -> float:
    """Fisher exact hai duoi cho bang 2x2."""
    n = a + b + c + d
    if n == 0:
        return 1.0
    quan_sat = comb(a + b, a) * comb(c + d, c) / comb(n, a + c)
    p = 0.0
    for x in range(max(0, a + c - (c + d)), min(a + b, a + c) + 1):
        pr = comb(a + b, x) * comb(c + d, a + c - x) / comb(n, a + c)
        if pr <= quan_sat + 1e-12:
            p += pr
    return min(1.0, p)


#: Ti le cham HONG toi da truoc khi BO phan noi dung.
#:
#: Nguoi cham hong thi ghi None, KHONG ghi 0 — va neu hong qua nhieu thi trung binh cua
#: phan con lai cung khong dung dai dien. Du an nay da bon lan bien mot su co ha tang
#: thanh mot ket luan chat luong gia; mot lan la 21/30 luot timeout roi van cong diem
#: cua 9 bai con lai ra "42,3/100".
TI_LE_CHAM_HONG_TOI_DA = 0.2

#: Cac muc NOI DUNG. Day la cot GIU — phan bat duoc "dung luat nhung vo hon".
MUC_NOI_DUNG: tuple[str, ...] = ("ngon_ngu", "hinh_anh", "y_nghia", "cam_xuc", "sang_tao")


def do_tat_dinh(bai: list[str]) -> dict[str, float]:
    """Phan do duoc bang CODE. Chay trong micro-giay, khong bao gio timeout."""
    sach = sum(1 for b in bai if not kiem_luc_bat(b, kiem_bang_trac=False))
    return {
        "sạch luật": sach,
        "thưởng TB": statistics.mean(phan_thuong(b).tong for b in bai),
        "chép bài mẫu": sum(1 for b in bai if so_cau_chep(b)),
        "cụm bị bẻ": sum(1 for b in bai if cum_kha_nghi(b)),
    }


async def do_noi_dung(bai: list[str]) -> dict[str, float] | None:
    """Diem NGUOI CHAM. `None` = cham hong qua nhieu, KHONG ket luan duoc.

    TRA None CHU KHONG TRA 0 — va day khong phai mot chi tiet:

    Cot GIU ton tai de bat truong hop RLVR day model ra nhung bai DUNG LUAT ma VO HON.
    Neu nguoi cham hong ma ta lang le tra 0, thi cot GIU se bao "noi dung tut" o MOI
    lan chay — ke ca nhung lan no khong tut. Bo do lam hong ca phep do la kieu sai te
    nhat, vi no nhin y het mot ket qua.

    Nguoc lai, coi bai CHUA CHAM DUOC nhu bai 0 diem thi trung binh bi keo xuong theo
    so lan API hong — tuc con so phu thuoc vao chat luong MANG chu khong vao chat luong
    THO.
    """
    diem: list[dict[str, float] | None] = []
    for b in bai:
        try:
            diem.append(await cham_tho_hay(b, str(uuid.uuid4())))
        except Exception:
            diem.append(None)

    sach = [d for d in diem if d is not None]
    hong = len(diem) - len(sach)
    if not sach or hong > len(diem) * TI_LE_CHAM_HONG_TOI_DA:
        print(
            f"    người chấm hỏng {hong}/{len(diem)} — BỎ phần nội dung, "
            "số ra sẽ là rác",
            file=sys.stderr,
        )
        return None

    if hong:
        print(f"    người chấm hỏng {hong}/{len(diem)} — trung bình trên {len(sach)} bài")
    return {m: statistics.mean(d[m] for d in sach) for m in MUC_NOI_DUNG}


def kiem_cot_giu(
    goc: dict[str, float], moi: dict[str, float], noi_goc: dict[str, float] | None,
    noi_moi: dict[str, float] | None,
) -> list[str]:
    """Nhung dieu kien GIU bi vi pham. Rong = giu duoc het.

    Mot lan chay chi cai thien cot DAT ma keo tut cot GIU thi la THAT BAI, du con so
    dau bang co dep den may.
    """
    vi_pham: list[str] = []
    if moi["chép bài mẫu"] > 0:
        vi_pham.append(f"chép bài mẫu {moi['chép bài mẫu']:.0f} bài (phải bằng 0)")
    if moi["cụm bị bẻ"] > goc["cụm bị bẻ"]:
        vi_pham.append(f"cụm bị bẻ tăng {goc['cụm bị bẻ']:.0f} -> {moi['cụm bị bẻ']:.0f}")
    if noi_goc is None or noi_moi is None:
        vi_pham.append("KHÔNG đo được nội dung — cột GIỮ chưa đủ để kết luận")
        return vi_pham
    for m in MUC_NOI_DUNG:
        tut = noi_goc[m] - noi_moi[m]
        if tut > NGUONG_TUT:
            vi_pham.append(f"{m} tụt {tut:.2f} (ngưỡng {NGUONG_TUT})")
    return vi_pham


async def sinh_hang_loat(model: object, chu_de: list[dict[str, str]]) -> list[str]:
    """Sinh mot bai cho moi chu de. Tach rieng de doi duoc backend."""
    raise NotImplementedError(
        "Noi vao vLLM hoac transformers o day — can GPU, xem rlvr/huan_luyen.py"
    )


async def bao_cao(bai_goc: list[str], bai_moi: list[str], mo_ta: str) -> int:
    """In bang so sanh day du: cot DAT, cot GIU tat dinh, va cot GIU NOI DUNG.

    Tra 0 khi DAT va GIU duoc het; 1 khi vi pham mot dieu kien GIU nao do. Ma tra khac
    0 co chu dich: mot lan chay "cai thien luat nhung lam tho vo hon" phai TRUOT, khong
    phai chi duoc ghi chu o cuoi bao cao.
    """
    print("=" * 74)
    print(f"NGHIỆM THU RLVR — {mo_ta}")
    print("=" * 74)

    td = {"GỐC": do_tat_dinh(bai_goc), "MỚI": do_tat_dinh(bai_moi)}
    print(f"  {'':<16}" + "".join(f"{t:>14}" for t in td))
    for m in td["GỐC"]:
        print(f"  {m:<16}" + "".join(f"{td[t][m]:>14.2f}" for t in td))

    print("\n  người chấm (cột GIỮ — bắt 'đúng luật nhưng vô hồn')…", flush=True)
    noi_goc = await do_noi_dung(bai_goc)
    noi_moi = await do_noi_dung(bai_moi)
    if noi_goc is not None and noi_moi is not None:
        print(f"  {'':<16}{'GỐC':>14}{'MỚI':>14}{'chênh':>10}")
        for m in MUC_NOI_DUNG:
            print(
                f"  {m:<16}{noi_goc[m]:>14.2f}{noi_moi[m]:>14.2f}"
                f"{noi_moi[m] - noi_goc[m]:>+10.2f}"
            )

    goc, moi = td["GỐC"], td["MỚI"]
    n_goc, n_moi = len(bai_goc), len(bai_moi)
    p = fisher(
        int(goc["sạch luật"]), n_goc - int(goc["sạch luật"]),
        int(moi["sạch luật"]), n_moi - int(moi["sạch luật"]),
    )
    tang = moi["sạch luật"] / n_moi > goc["sạch luật"] / n_goc
    dat = tang and p < 0.05
    print(
        f"\n  ĐẠT: sạch luật {goc['sạch luật']:.0f}/{n_goc} -> {moi['sạch luật']:.0f}/{n_moi}"
        f", Fisher p={p:.4f}  {'✓' if dat else '✗'}"
    )

    vi_pham = kiem_cot_giu(goc, moi, noi_goc, noi_moi)
    if vi_pham:
        print("  GIỮ: ✗")
        for v in vi_pham:
            print(f"        - {v}")
    else:
        print("  GIỮ: ✓ không mục nào tụt quá ngưỡng")

    print()
    if dat and not vi_pham:
        print("  => ĐẠT. RLVR nâng được tỉ lệ đúng luật mà không hy sinh chất thơ.")
        return 0
    if vi_pham:
        print("  => TRƯỢT cột GIỮ. Tối ưu thẳng vào luật đã hy sinh thứ khác —")
        print("     đây chính là kiểu hỏng mà cột GIỮ tồn tại để bắt.")
    else:
        print("  => Chưa ĐẠT: tỉ lệ đúng luật không tăng có ý nghĩa.")
    return 1


async def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")

    bo = argparse.ArgumentParser(description="Nghiem thu RLVR")
    bo.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    bo.add_argument("--adapter", type=Path, default=GOC / "rlvr" / "ket_qua")
    bo.add_argument("--du-lieu", type=Path, default=GOC / "rlvr" / "du_lieu")
    bo.add_argument("--n", type=int, default=200)
    bo.add_argument(
        "--tu-tep",
        nargs=2,
        type=Path,
        metavar=("GOC.txt", "MOI.txt"),
        help="so hai tap tho co san thay vi sinh moi — CHAY DUOC KHONG CAN GPU",
    )
    tham = bo.parse_args()

    # --- Che do TU TEP: chay duoc ma khong can GPU ---
    #
    # Dat o day chu khong lam mot script rieng: toan bo phan DO (tat dinh + nguoi cham
    # + cot GIU) la chung cho ca hai che do. Tach ra thanh hai duong se de hai duong
    # lech nhau — va luc do con so nghiem thu se khac con so tu tay, ma khong ai biet.
    if tham.tu_tep:
        tap = {}
        for ten, p in zip(("GỐC", "MỚI"), tham.tu_tep, strict=True):
            if not p.exists():
                print(f"KHONG CO TEP: {p}", file=sys.stderr)
                return 2
            tap[ten] = [b.strip() for b in p.read_text(encoding="utf-8").split("\n\n") if b.strip()]
        return await bao_cao(tap["GỐC"], tap["MỚI"], "hai tập thơ từ tệp")

    p_test = tham.du_lieu / "chu_de_test.jsonl"
    if not p_test.exists():
        print(f"CHUA CO {p_test}\n\n  uv run python ops/sinh_chu_de.py", file=sys.stderr)
        return 2

    test = [json.loads(d) for d in p_test.read_text(encoding="utf-8").splitlines() if d.strip()]
    # Lap lai bo test cho du n — no chi co 112 chu de, va n=200 la nguong Fisher.
    chu_de = [test[i % len(test)] for i in range(tham.n)]

    try:
        import torch  # noqa: F401
    except ImportError:
        print(
            "THIEU PHU THUOC:\n\n  uv sync --group rlvr\n\n"
            f"Bo chu de da san sang: {len(test)} chu de test (chua thay khi train).\n"
            f"System prompt dung de do: {len(system_prompt('luc_bat'))} ky tu.\n"
            f"Vi du de bai: {yeu_cau(test[0]['chu_de'])!r}",
            file=sys.stderr,
        )
        return 2

    bai_goc = await sinh_hang_loat(None, chu_de)
    bai_moi = await sinh_hang_loat(tham.adapter, chu_de)
    return await bao_cao(bai_goc, bai_moi, f"{len(chu_de)} chủ đề CHƯA THẤY khi train")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
