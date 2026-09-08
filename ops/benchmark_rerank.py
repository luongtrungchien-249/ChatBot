"""So sanh nha cung cap rerank TREN TAI LIEU THAT cua ban, roi moi chot va chot nguong.

Vi sao khong the chot san: bang xep hang chung do tren tap tieng Anh; cai quyet dinh
la model co xep dung tren van ban cua CHINH ban khong. Va quan trong khong kem —
`RERANK_MIN_SCORE` phai do lai theo tung nha cung cap, vi hai cross-encoder khac nhau
tra ve hai THANG DIEM khac nhau. Bung nguong cua nha nay sang nha kia la doan mo.

Dau vao: mot tep JSONL, moi dong `{"question": "...", "expected_chunk_ids": ["12"]}`.
Dung duoc luon `evals/dataset/qa.jsonl`.

Cach chay:
    1. Nap tai lieu that:  uv run python -m main.cli ingest <tep>
    2. Viet cau hoi that:  moi dong mot cau + id chunk dung
    3. uv run python ops/benchmark_rerank.py evals/dataset/qa.jsonl

Script KHONG tu doi RERANK_PROVIDER: no do CAI DANG DUOC CAU HINH. Doi nha cung cap
trong `.env` roi chay lai, rồi so hai bang voi nhau — nhu vay moi so cung mot dieu
kien va khong co bien an nao.

DO NAY TON TIEN THAT (rerank tinh theo so van ban).
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agents.domain.thread import ThreadScope
from config import get_settings
from knowledge.retrieve.fusion import reciprocal_rank_fusion
from knowledge.retrieve.search import CANDIDATES_PER_SIDE, lexical_search, vector_search
from knowledge.retrieve.service import FUSION_TOP
from llm.reranker import get_reranker

TOP_K = 5

#: Do tren pham vi "chung" — dung pham vi ma moi nhom deu doc duoc.
_SCOPE = ThreadScope(platform="cli", thread_id="benchmark")


async def ung_vien(question: str) -> list[tuple[int, str]]:
    """(chunk_id, content) sau buoc hop nhat, TRUOC rerank.

    Dung dung duong ma service.py chay, khong dung mot ban rut gon: do nguong tren
    mot tap ung vien khac voi tap that la do sai thu.
    """
    vector_hits, lexical_hits = await asyncio.gather(
        vector_search(_SCOPE, question, CANDIDATES_PER_SIDE),
        lexical_search(_SCOPE, question, CANDIDATES_PER_SIDE),
        return_exceptions=True,
    )
    rows: dict[int, str] = {}
    rankings: list[list[int]] = []
    for hits in (vector_hits, lexical_hits):
        if isinstance(hits, BaseException):
            continue
        rankings.append([h.chunk_id for h in hits])
        rows.update({h.chunk_id: h.content for h in hits})
    fused = reciprocal_rank_fusion(rankings)[:FUSION_TOP]
    return [(r.chunk_id, rows[r.chunk_id]) for r in fused]


async def main() -> int:
    if len(sys.argv) < 2:
        print("Dung: uv run python ops/benchmark_rerank.py <dataset.jsonl>", file=sys.stderr)
        return 1

    dataset = Path(sys.argv[1])
    if not dataset.exists():
        print(f"Khong thay {dataset}", file=sys.stderr)
        return 1

    rows = [
        json.loads(dong)
        for dong in dataset.read_text(encoding="utf-8").splitlines()
        if dong.strip()
    ]
    if not rows:
        print("Dataset rong.", file=sys.stderr)
        return 1

    settings = get_settings()
    print(f"Nha cung cap: {settings.RERANK_PROVIDER} / {settings.RERANK_MODEL}")
    print(f"Nguong dang dat: RERANK_MIN_SCORE = {settings.RERANK_MIN_SCORE}")
    print(f"{len(rows)} cau hoi\n")

    diem_dung: list[float] = []
    diem_sai: list[float] = []
    top1 = 0
    khong_co_ung_vien = 0

    for row in rows:
        question = row["question"]
        mong_doi = {str(c) for c in row.get("expected_chunk_ids") or []}
        if not mong_doi:
            continue

        candidates = await ung_vien(question)
        if not candidates:
            khong_co_ung_vien += 1
            continue

        hits = await get_reranker().rerank(question, [c for _, c in candidates], TOP_K)
        if not hits:
            khong_co_ung_vien += 1
            continue

        if str(candidates[hits[0].index][0]) in mong_doi:
            top1 += 1

        for h in hits:
            chunk_id = str(candidates[h.index][0])
            (diem_dung if chunk_id in mong_doi else diem_sai).append(h.score)

    if not diem_dung:
        print("Khong cau nao tra ve chunk dung. Da nap tai lieu chua?", file=sys.stderr)
        return 1

    dung_min, dung_tb = min(diem_dung), sum(diem_dung) / len(diem_dung)
    sai_max = max(diem_sai) if diem_sai else 0.0

    print(f"  top-1 dung        {top1}/{len(rows)}")
    print(f"  diem chunk DUNG   {dung_min:.3f} - {max(diem_dung):.3f}  (tb {dung_tb:.3f})")
    print(f"  diem chunk SAI    {min(diem_sai) if diem_sai else 0:.3f} - {sai_max:.3f}")
    print(f"  khoang an toan    {dung_min - sai_max:+.3f}")
    if khong_co_ung_vien:
        print(f"  {khong_co_ung_vien} cau khong co ung vien nao")

    _quet_nguong(diem_dung, diem_sai)

    print()
    if dung_min > sai_max:
        de_xuat = (dung_min + sai_max) / 2
        print(f"  RERANK_MIN_SCORE de xuat: {de_xuat:.2f}")
        print("  (diem giua khoang an toan — moi huong sai deu co gia nhu nhau o day:")
        print("   cao qua thi bo sot tai lieu co that, thap qua thi dua rac vao prompt)")
    else:
        print("  KHONG co nguong nao tach duoc chunk dung khoi chunk sai.")
        print("  Doi nha cung cap rerank, hoac xem lai cach cat chunk truoc.")
    return 0


def _quet_nguong(diem_dung: list[float], diem_sai: list[float]) -> None:
    """Bang danh doi, cho truong hop hai phan bo CHONG NHAU.

    Khi chung tach roi thi chon nguong la viec de — lay diem giua. Khi chung chong
    nhau thi khong co dap an dung, chi co danh doi, va nguoi chon phai NHIN THAY no:

      giu duoc  = ti le chunk DUNG vuot nguong  -> mat cai nay la bo sot tai lieu that
      chan duoc = ti le chunk SAI bi loai       -> mat cai nay la dua rac vao prompt

    Khong tu chon ho: hai huong sai co gia khac nhau tuy viec, va do la quyet dinh
    cua chu du an chu khong phai cua mot cong thuc.
    """
    print()
    print("  Quet nguong (khi hai phan bo chong nhau, khong co dap an dung — chi co danh doi):")
    print()
    print(f"    {'nguong':>8}  {'giu duoc chunk DUNG':>21}  {'chan duoc chunk SAI':>21}")
    for nguong in (0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75):
        giu = sum(1 for d in diem_dung if d >= nguong) / len(diem_dung)
        chan = (
            sum(1 for d in diem_sai if d < nguong) / len(diem_sai) if diem_sai else 1.0
        )
        print(f"    {nguong:>8.2f}  {giu:>20.1%}  {chan:>20.1%}")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
