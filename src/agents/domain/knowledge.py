"""Doan tai lieu da lay ve, o hinh dang ma prompt can.

Truoc day kieu nay nam trong `agents/ports/knowledge.py`, canh `KnowledgePort`. Nhung
port do da chet (07/09/2026): duong tra cuu that di qua CONG CU
`search_knowledge_base`, tuc qua `ToolPort`, chu khong qua mot port rieng cho tri thuc.

Con `RetrievedChunk` thi khong chet — `prompt/builder.py` va `prompt/context.py` van
dung no de dung khoi <tai_lieu>, va `evals/runner.py` dung no de dung dung khoi ay khi
cham diem. No la mot GIA TRI cua mien nghiep vu, khong phai mot hop dong, nen no thuoc
ve `domain/` chu khong phai `ports/`.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: str
    doc_title: str
    section: str | None
    page: int | None
    content: str
    #: Diem cua buoc rerank, sau khi da loc theo RERANK_MIN_SCORE.
    score: float
