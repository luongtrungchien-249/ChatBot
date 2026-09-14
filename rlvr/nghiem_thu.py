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
from math import comb
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
for _p in ("src", "."):
    sys.path.insert(0, str(GOC / _p))

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


def do_mot_tap(bai: list[str]) -> dict[str, float]:
    sach = sum(1 for b in bai if not kiem_luc_bat(b, kiem_bang_trac=False))
    return {
        "sạch luật": sach,
        "thưởng TB": statistics.mean(phan_thuong(b).tong for b in bai),
        "chép bài mẫu": sum(1 for b in bai if so_cau_chep(b)),
        "cụm bị bẻ": sum(1 for b in bai if cum_kha_nghi(b)),
    }


async def sinh_hang_loat(model: object, chu_de: list[dict[str, str]]) -> list[str]:
    """Sinh mot bai cho moi chu de. Tach rieng de doi duoc backend."""
    raise NotImplementedError(
        "Noi vao vLLM hoac transformers o day — can GPU, xem rlvr/huan_luyen.py"
    )


async def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")

    bo = argparse.ArgumentParser(description="Nghiem thu RLVR")
    bo.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    bo.add_argument("--adapter", type=Path, default=GOC / "rlvr" / "ket_qua")
    bo.add_argument("--du-lieu", type=Path, default=GOC / "rlvr" / "du_lieu")
    bo.add_argument("--n", type=int, default=200)
    tham = bo.parse_args()

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

    ket: dict[str, dict[str, float]] = {}
    for ten, adapter in (("GỐC", None), ("SAU RLVR", tham.adapter)):
        bai = await sinh_hang_loat(adapter, chu_de)
        ket[ten] = do_mot_tap(bai)

    print("=" * 74)
    print(f"NGHIỆM THU RLVR — n={len(chu_de)} chủ đề CHƯA THẤY khi train")
    print("=" * 74)
    muc = list(next(iter(ket.values())))
    print(f"  {'':<16}" + "".join(f"{t:>14}" for t in ket))
    for m in muc:
        print(f"  {m:<16}" + "".join(f"{ket[t][m]:>14.2f}" for t in ket))

    goc, moi = ket["GỐC"], ket["SAU RLVR"]
    n = len(chu_de)
    p = fisher(int(goc["sạch luật"]), n - int(goc["sạch luật"]),
               int(moi["sạch luật"]), n - int(moi["sạch luật"]))
    print(f"\n  ĐẠT: sạch luật {goc['sạch luật']:.0f} -> {moi['sạch luật']:.0f}, Fisher p={p:.4f}")
    print(f"  GIỮ: chép {moi['chép bài mẫu']:.0f} · cụm bị bẻ "
          f"{goc['cụm bị bẻ']:.0f} -> {moi['cụm bị bẻ']:.0f}")
    print("\n  CÒN THIẾU: chấm nội dung bằng người chấm (ngôn ngữ/hình ảnh/ý nghĩa).")
    print("  Xem evals/metrics/tho_hay.py — cột GIỮ chưa đủ nếu thiếu phần này.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
