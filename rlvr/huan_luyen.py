"""GRPO tren verifier luat tho. Buoc 6 cua docs/plan-rlvr-tho.md.

    # 1. Cai phu thuoc nang (KHONG nam trong phu thuoc chinh cua du an)
    uv sync --group rlvr

    # 2. Sinh bo chu de neu chua co
    uv run python ops/sinh_chu_de.py

    # 3. Huan luyen  (CAN GPU)
    uv run python rlvr/huan_luyen.py --model Qwen/Qwen2.5-7B-Instruct

VI SAO TEP NAY NAM NGOAI src/: no khong phai mot phan cua bot dang chay. `src/` bi bon
hop dong import-linter rang buoc va phai cai duoc bang `uv sync` co ban; torch + trl +
vllm thi nang hang GB va chi can khi huan luyen. De chung vao se bat MOI lan trien khai
phai tai ca dong do.

--------------------------------------------------------------------------------
BA CHO DE LAM SAI, ghi ra day vi ca ba deu IM LANG khi sai
--------------------------------------------------------------------------------

1. PROMPT HUAN LUYEN PHAI LA PROMPT PHUC VU.
   Neu train bang mot prompt khac luc chay that thi model hoc dung luat DUOI prompt do,
   va con so nghiem thu khong noi gi ve he thong that. Nen tep nay goi thang
   `tho.prompt.system_prompt` — cung ham ma `sinh_tho` dung.

2. HAM THUONG PHAI LA VERIFIER DA HIEU CHUAN.
   `tho.phan_thuong.thuong` — bao nham van 5,9% tren Truyen Kieu (da ha tu 17,0%, xem
   dot 2 trong luat.py). Do la GIOI HAN TREN cua ca phep huan luyen nay: model khong
   the hoc dung hon cai thuoc do no.

3. KL PHAI CO. `beta` giu policy khong troi khoi tieng Viet tu nhien. Toi uu thang vao
   mot bo do tat dinh ma khong neo lai thi ket cuc quen thuoc la model tim ra mot chuoi
   vo nghia nhung an diem tuyet doi. Ba chot chong lach trong `phan_thuong` chan duoc
   ba kieu da biet; KL chan phan con lai.
"""

import argparse
import json
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "src"))

from tho.phan_thuong import thuong  # noqa: E402
from tho.prompt import system_prompt, yeu_cau  # noqa: E402

#: So ban sinh cho MOI chu de trong mot buoc GRPO.
#:
#: GRPO lay loi the TUONG DOI trong nhom, khong can value model — nen kich thuoc nhom
#: chinh la thu quyet dinh tin hieu co sach khong. 8 la muc pho bien; duoi 4 thi phuong
#: sai uoc luong loi the qua lon.
#:
#: Trung hop co ich: duong phuc vu cung dang sinh song song 4 ban (`SO_BAN` trong
#: sinh.py), nen co che "sinh nhieu roi chon" khong xa la voi he thong nay.
SO_BAN_NHOM = 8

#: He so KL ve model goc. Xem cho de sai so 3 o dau tep.
BETA_KL = 0.04


def doc_chu_de(p: Path) -> list[dict[str, str]]:
    return [json.loads(d) for d in p.read_text(encoding="utf-8").splitlines() if d.strip()]


def ham_thuong(completions: list[str], **kwargs: object) -> list[float]:
    """Ham thuong TRL goi. Tra ve mot so trong [0, 1] cho moi ban sinh.

    `the_tho` di theo tung dong du lieu chu khong ghi cung: mot ngay nao do train tren
    ca bat cu thi cham bang thuoc luc bat se cho diem gan nhu bang 0 cho MOI ban — va
    do la kieu hong lam ca lan chay tro nen vo nghia ma khong bao gi.

    NHAN DANG SACH cho tung ban chu khong mot chuoi chung: TRL truyen cac cot cua tap
    du lieu vao day duoi dang LIST song song voi `completions`. Nhan nham mot chuoi roi
    nhan ban ra se cho ket qua dung O TRUONG HOP tap chi co mot the tho — tuc no se
    chay im lang cho toi dung ngay ta tron hai the.
    """
    raw = kwargs.get("the_tho")
    if isinstance(raw, str):
        the_tho = [raw] * len(completions)
    elif isinstance(raw, list):
        the_tho = [str(x) for x in raw]
    else:
        the_tho = ["luc_bat"] * len(completions)

    if len(the_tho) != len(completions):
        raise ValueError(
            f"the_tho co {len(the_tho)} phan tu nhung co {len(completions)} ban sinh — "
            "cham nham the tho se cho diem gan 0 cho MOI ban ma khong bao gi"
        )
    return [thuong(c, t) for c, t in zip(completions, the_tho, strict=True)]


def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")

    bo = argparse.ArgumentParser(description="GRPO tren verifier luat tho")
    bo.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    bo.add_argument("--du-lieu", type=Path, default=GOC / "rlvr" / "du_lieu")
    bo.add_argument("--ra", type=Path, default=GOC / "rlvr" / "ket_qua")
    bo.add_argument("--so-buoc", type=int, default=500)
    bo.add_argument("--lora", action="store_true", default=True)
    tham = bo.parse_args()

    try:
        import torch
        from datasets import Dataset
        from trl import GRPOConfig, GRPOTrainer
    except ImportError as loi:
        print(
            f"THIEU PHU THUOC: {loi.name}\n\n"
            "  uv sync --group rlvr\n\n"
            "Nhom nay nam NGOAI phu thuoc chinh co chu dich — xem docstring dau tep.",
            file=sys.stderr,
        )
        return 2

    if not torch.cuda.is_available():
        print(
            "KHONG CO GPU. GRPO sinh 8 ban moi buoc x 500 buoc — tren CPU thi khong xong.",
            file=sys.stderr,
        )
        return 2

    p_train = tham.du_lieu / "chu_de_train.jsonl"
    if not p_train.exists():
        print(f"CHUA CO {p_train}\n\n  uv run python ops/sinh_chu_de.py", file=sys.stderr)
        return 2

    train = doc_chu_de(p_train)
    sys_prompt = system_prompt("luc_bat")
    ds = Dataset.from_list(
        [
            {
                "prompt": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": yeu_cau(x["chu_de"])},
                ],
                "the_tho": x["the_tho"],
            }
            for x in train
        ]
    )

    print(f"model   {tham.model}")
    print(f"dữ liệu {len(ds)} chủ đề · nhóm {SO_BAN_NHOM} bản/bước · {tham.so_buoc} bước")
    print("thưởng  tho.phan_thuong.thuong — verifier báo nhầm vần 5,9%")

    cau_hinh = GRPOConfig(
        output_dir=str(tham.ra),
        num_generations=SO_BAN_NHOM,
        beta=BETA_KL,
        max_steps=tham.so_buoc,
        per_device_train_batch_size=SO_BAN_NHOM,
        gradient_accumulation_steps=2,
        learning_rate=1e-6,
        logging_steps=10,
        save_steps=100,
        max_completion_length=256,
        bf16=True,
    )

    peft_config = None
    if tham.lora:
        from peft import LoraConfig

        peft_config = LoraConfig(
            r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM"
        )

    GRPOTrainer(
        model=tham.model,
        reward_funcs=ham_thuong,
        args=cau_hinh,
        train_dataset=ds,
        peft_config=peft_config,
    ).train()

    print(f"\nxong -> {tham.ra}")
    print("Đo nghiệm thu:  uv run python rlvr/nghiem_thu.py --adapter", tham.ra)
    return 0


if __name__ == "__main__":
    sys.exit(main())
