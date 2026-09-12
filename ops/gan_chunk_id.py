"""Gan lai `expected_chunk_ids` cho bo eval, tu cac cum tu `neo`.

VI SAO CAN: nap lai kho sinh chunk_id MOI. Trong hai ngay 10-11/09/2026 viec nay xay
ra hai lan, va ca hai lan bo eval deu am tham do mot thu khong con ton tai —
`expected_chunk_ids` tro thanh id chet, Recall@5 cham 0 cho moi cau, va con so do
trong y het mot van de chat luong.

Bon chi so RAGAS khong dinh toi chunk_id nen chung mien nhiem. Recall@5 thi khong, va
day la cach giu no song ma khong phai ngoi do lai bang tay:

    uv run python ops/gan_chunk_id.py evals/dataset/golden.jsonl --ghi

Khong co `--ghi` thi chi in ra de xem truoc, khong dung vao tep.

Doi chieu bang NOI DUNG chu khong bang id: `neo` la cum tu dac trung nen chung song
qua moi lan nap lai. Mot chunk duoc tinh la dap an khi no chua NHIEU NEO NHAT trong
so cac chunk — khong phai "chua it nhat mot neo", vi mot cum pho bien se keo theo ca
chuc chunk chi trung chu de.
"""

import asyncio
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from infra.db import close_db, fetch

#: Chunk co `section` dai hon nguong nay la trang MUC LUC, khong phai mot muc that.
#:
#: Luat "tieu de lien nhau thi GOP" trong chunk.py gap trang muc luc thi gop luon ca
#: danh sach mon an thanh mot `section`. Ket qua: mot chunk mang ten CUA MOI MON, nen
#: no khop voi bat ky cau hoi nao co ten mon — ca o day lan o duong BM25 that.
#:
#: Do tren kho hien tai, do dai `section` co mot khoang trong rat sach:
#:     muc that      <= 64 ky tu
#:     trang muc luc    144, 250, 442  (5 chunk)
#: Nen 100 nam giua, va khong phai mot con so chon bua.
MUC_LUC_TU = 100


def chuan(s: str) -> str:
    """Bo khac biet khong dang ke: dang unicode, khoang trang, chu hoa."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s)).strip().lower()


async def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ghi = "--ghi" in sys.argv[1:]
    if not args:
        print("Dung: gan_chunk_id.py <dataset.jsonl> [--ghi]", file=sys.stderr)
        return 2
    tep = Path(args[0])

    rows = [json.loads(d) for d in tep.read_text(encoding="utf-8").splitlines() if d.strip()]
    db = await fetch(
        """SELECT c.id, c.section, c.content
             FROM kb_chunk c JOIN kb_document d ON d.id = c.doc_id
            WHERE d.la_ban_moi_nhat"""
    )
    kho = [
        (str(x["id"]), chuan(f"{x['section'] or ''} {x['content']}"), len(x["section"] or ""))
        for x in db
    ]
    print(f"{len(kho)} chunk trong kho, {len(rows)} cau trong bo\n")

    khong_khop: list[str] = []
    for r in rows:
        neo = [chuan(n) for n in r.get("neo") or []]
        if not neo:
            r["expected_chunk_ids"] = []
            continue

        diem = [(cid, sum(1 for n in neo if n in txt), dai) for cid, txt, dai in kho]
        cao_nhat = max(d for _, d, _ in diem)
        if cao_nhat == 0:
            khong_khop.append(r["id"])
            r["expected_chunk_ids"] = []
            continue

        trung = [(cid, dai) for cid, d, dai in diem if d == cao_nhat]
        # Bo trang muc luc — nhung chi khi con chunk THAT de giu. Con khong thi giu
        # nguyen va de bang ket qua noi ra, chu khong am tham tra ve rong.
        that = [cid for cid, dai in trung if dai < MUC_LUC_TU]
        r["expected_chunk_ids"] = sorted(that or [cid for cid, _ in trung])
        print(
            f"  {r['id']} [{r.get('loai', ''):<14}] {cao_nhat}/{len(neo)} neo -> "
            f"{r['expected_chunk_ids']}"
        )

    if khong_khop:
        print(f"\nKHONG KHOP NEO NAO ({len(khong_khop)}): {khong_khop}")
        print("  Neo sai, hoac kho da doi. Xem lai TRUOC khi tin con so eval.")

    if ghi:
        tep.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
        )
        print(f"\nDa ghi {tep}")
    else:
        print("\n(chi xem truoc — them --ghi de ghi vao tep)")

    await close_db()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
