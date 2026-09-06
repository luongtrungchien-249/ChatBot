"""Recall@5: chunk dung co nam trong top 5 khong. Muc tieu > 0,85.

TODO(giai-doan-8) — can `expected_chunk_ids` that trong qa.jsonl, ma cai do can
tai lieu da nap (Giai doan 6).
"""


def recall_at_k(retrieved_ids: list[str], expected_ids: list[str], k: int = 5) -> float:
    """Ti le chunk mong doi xuat hien trong top k.

    Khong co chunk mong doi thi tra ve 1.0: cau hoi khong can tra cuu tai lieu
    khong duoc tinh la truot.
    """
    if not expected_ids:
        return 1.0
    top = set(retrieved_ids[:k])
    return len([i for i in expected_ids if i in top]) / len(expected_ids)
