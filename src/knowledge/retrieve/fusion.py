"""Reciprocal Rank Fusion — hop nhat hai bang xep hang thanh mot.

Vi sao RRF chu khong phai cong diem co trong so: diem cosine (0..1) va diem
ts_rank (khong chan tren) khong cung thang do, nen cong chung lai la cong hai don
vi khac nhau. RRF chi dung THU HANG, nen no khong quan tam thang do.

    score(d) = tong tren moi danh sach cua  1 / (k + hang cua d)

k = 60 la gia tri chuan trong bai goc; no lam phang chenh lech giua hang 1 va hang 2
de mot danh sach khong ap dao ca ket qua.
"""

from dataclasses import dataclass

RRF_K = 60


@dataclass(frozen=True, slots=True)
class Ranked:
    chunk_id: int
    score: float


def reciprocal_rank_fusion(rankings: list[list[int]], k: int = RRF_K) -> list[Ranked]:
    """`rankings`: moi phan tu la mot danh sach chunk_id DA SAP theo do lien quan."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for position, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + position)

    ordered = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    return [Ranked(chunk_id=chunk_id, score=score) for chunk_id, score in ordered]
