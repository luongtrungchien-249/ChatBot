"""GPU nay chay duoc model bao lon? Doc VRAM that bang nvidia-smi roi tinh.

Chay:
    uv run python ops/kiem_gpu.py              # xem may nay chay duoc gi
    uv run python ops/kiem_gpu.py 26           # model 26B co chay duoc khong
    uv run python ops/kiem_gpu.py 26 --ngu-canh 8192

VI SAO CAN: "co GPU" khong phai mot cau tra loi. 4 GB va 24 GB deu la "co GPU", ma
mot ben khong nap noi model 26B con ben kia thi thoai mai. Con so quyet dinh la VRAM,
va no tra duoc trong mot giay.

CACH TINH:

    trong so   = so_tham_so x so_byte_moi_tham_so
    KV cache   ~ 2 (K va V) x so_lop x so_dau_kv x chieu_dau x do_dai x 2 byte
    du phong   ~ 10% cho kich hoat, phan manh, va ban than runtime

Kien truc thuc te cua tung model khac nhau, nen KV cache o day la UOC LUONG dua tren
ti le thuong gap. Sai so ±30% la binh thuong — dung dung no de quyet dinh mot ca sat
nut, hay thu that.

MoE: dung `--tong` cho TONG so tham so, khong phai so tham so hoat dong. Mot model
26B-A4B van phai nap ca 26B vao VRAM — phan thua nam o PHEP TINH, khong nam o bo nho.
Day la cho hieu nham dat tien nhat khi chon phan cung cho MoE.
"""

import subprocess
import sys
from dataclasses import dataclass

#: Byte moi tham so theo cach luong tu hoa.
#:
#: int4 khong phai dung 0,5: AWQ/GPTQ con luu he so scale va zero-point, thuc te roi
#: vao khoang 0,55-0,60 byte. Lay 0,58 cho sat.
_BYTE: dict[str, float] = {"bf16": 2.0, "int8": 1.0, "int4": 0.58}

#: Du phong cho kich hoat, phan manh bo nho, va ban than CUDA/runtime.
_DU_PHONG = 0.10

#: KV cache moi token, uoc luong theo ti le thuong gap o model dense hien dai co GQA.
#: Don vi: MB moi ty tham so moi token. Rat tho — xem canh bao o docstring.
_KV_MB_MOI_TY_MOI_TOKEN = 0.020


@dataclass(frozen=True, slots=True)
class Gpu:
    ten: str
    tong_mb: int
    trong_mb: int


def doc_gpu() -> list[Gpu]:
    try:
        ra = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if ra.returncode != 0:
        return []
    gpu: list[Gpu] = []
    for dong in ra.stdout.strip().splitlines():
        phan = [x.strip() for x in dong.split(",")]
        if len(phan) >= 3 and phan[1].isdigit() and phan[2].isdigit():
            gpu.append(Gpu(ten=phan[0], tong_mb=int(phan[1]), trong_mb=int(phan[2])))
    return gpu


def can_bao_nhieu_gb(ty_tham_so: float, cach: str, ngu_canh: int) -> float:
    trong_so = ty_tham_so * 1e9 * _BYTE[cach] / 1024**3
    kv = ty_tham_so * _KV_MB_MOI_TY_MOI_TOKEN * ngu_canh / 1024
    return (trong_so + kv) * (1 + _DU_PHONG)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ngu_canh = 4096
    if "--ngu-canh" in sys.argv:
        ngu_canh = int(sys.argv[sys.argv.index("--ngu-canh") + 1])

    gpu = doc_gpu()
    if not gpu:
        print("Không đọc được nvidia-smi — máy này không có GPU NVIDIA, hoặc chưa cài driver.")
        print("Không có GPU thì đừng tự host: CPU sinh 2-8 token/giây.")
        return 1

    for g in gpu:
        print(f"{g.ten}")
        print(f"  VRAM tổng {g.tong_mb / 1024:.1f} GB · còn trống {g.trong_mb / 1024:.1f} GB")
    print(f"  (ngữ cảnh giả định {ngu_canh} token)\n")

    trong_gb = max(g.trong_mb for g in gpu) / 1024

    if args:
        ty = float(args[0])
        print(f"Model {ty:g}B — TỔNG số tham số (MoE cũng tính tổng):\n")
        vua_nao = []
        for cach in ("bf16", "int8", "int4"):
            can = can_bao_nhieu_gb(ty, cach, ngu_canh)
            vua = can <= trong_gb
            if vua:
                vua_nao.append(cach)
            dau = "VỪA " if vua else "THIẾU"
            thieu = (
                ""
                if vua
                else f"  (thiếu {can - trong_gb:.1f} GB, tức {can / trong_gb:.1f} lần)"
            )
            print(f"  {dau}  {cach:5} cần ~{can:5.1f} GB{thieu}")
        print()
        if vua_nao:
            print(f"→ Chạy được ở: {', '.join(vua_nao)}.")
            return 0
        print("→ KHÔNG chạy được trên GPU này. Model sẽ không nạp nổi, không phải chạy chậm.")
        print("  Thuê GPU theo giờ, hoặc chọn model nhỏ hơn (xem bảng khi chạy không tham số).")
        return 1

    print("Cỡ model lớn nhất vừa VRAM còn trống:\n")
    print(f"  {'cỡ':>6}  {'bf16':>8}  {'int8':>8}  {'int4':>8}")
    for ty in (1, 3, 4, 7, 8, 13, 26, 32, 70):
        o = []
        for cach in ("bf16", "int8", "int4"):
            can = can_bao_nhieu_gb(ty, cach, ngu_canh)
            o.append("vừa" if can <= trong_gb else f"{can:.0f}GB")
        print(f"  {ty:>5}B  {o[0]:>8}  {o[1]:>8}  {o[2]:>8}")
    print("\n  'vừa' = nạp được. Số = cần bấy nhiêu GB, tức KHÔNG vừa.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
