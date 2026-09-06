from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    chunk_id: str
    doc_title: str
    section: str | None
    page: int | None
    content: str
    score: float


class KnowledgePort(Protocol):
    async def search(self, query: str, k: int) -> list[RetrievedChunk]:
        """Da fusion + rerank + loc nguong RERANK_MIN_SCORE.

        Rong = "khong tim thay trong tai lieu", khong phai loi.
        """
        ...
