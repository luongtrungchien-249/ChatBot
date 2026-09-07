"""Hai duong tim, chay SONG SONG.

Chi dung vector la hong o ca DE nhat: ma san pham, ten rieng, so hieu van ban —
dung loai cau hoi pho bien nhat trong mot to chuc. Embedding gom "QD-145/2026" va
"QD-146/2026" vao gan nhu cung mot cho; BM25 thi khong.

Chi dung BM25 thi hong o chieu con lai: nguoi hoi "nghi phep" ma tai lieu viet
"ngay phep nam" se khong khop mot tu nao.

Nen phai co ca hai. `vn_tsv()` (migration 0001) bo dau truoc khi lap chi muc, vi
Postgres khong co dictionary tieng Viet va `to_tsvector('simple', ...)` giu nguyen
dau — "tra cuu" se khong khop "tra cứu".
"""

from dataclasses import dataclass
from typing import Any

from infra.db import fetch
from infra.logger import get_logger
from llm.embedder import embed_query

_log = get_logger()

#: Cache vector cau hoi nam o llm/embedder.embed_query — dung chung voi L3, vi ca
#: hai deu embed DUNG chuoi do trong cung mot luot tra loi.

#: Moi duong lay 20, hop nhat roi con 10, rerank con 3-5 (plan section 8).
CANDIDATES_PER_SIDE = 20


@dataclass(frozen=True, slots=True)
class ChunkRow:
    chunk_id: int
    doc_title: str
    section: str | None
    page: int | None
    content: str


def _to_row(row: Any) -> ChunkRow:
    return ChunkRow(
        chunk_id=int(row["id"]),
        doc_title=row["title"],
        section=row["section"],
        page=row["page"],
        content=row["content"],
    )


async def vector_search(query: str, limit: int = CANDIDATES_PER_SIDE) -> list[ChunkRow]:
    """`<=>` la khoang cach cosine cua pgvector: CANG NHO CANG GIONG.

    Index HNSW o migration 0004 phuc vu dung phep toan nay. Doi sang `<->` hay `<#>`
    la index thanh vo dung va truy van tut ve quet tuan tu — im lang, chi cham dan.
    """
    vector = await embed_query(query)
    rows = await fetch(
        """SELECT c.id, c.section, c.page, c.content, d.title
             FROM kb_chunk c JOIN kb_document d ON d.id = c.doc_id
            ORDER BY c.embedding <=> $1::vector
            LIMIT $2""",
        "[" + ",".join(f"{v:.7f}" for v in vector) + "]",
        limit,
    )
    return [_to_row(r) for r in rows]


async def lexical_search(query: str, limit: int = CANDIDATES_PER_SIDE) -> list[ChunkRow]:
    """BM25-kieu qua tsvector. Cau hoi cung phai di qua `vn_tsv` de bo dau y het luc
    lap chi muc — mot ben bo dau mot ben khong thi khong bao gio khop.
    """
    rows = await fetch(
        """SELECT c.id, c.section, c.page, c.content, d.title
             FROM kb_chunk c JOIN kb_document d ON d.id = c.doc_id,
                  plainto_tsquery('simple', unaccent('unaccent', $1)) AS q
            WHERE c.tsv @@ q
            ORDER BY ts_rank(c.tsv, q) DESC
            LIMIT $2""",
        query,
        limit,
    )
    return [_to_row(r) for r in rows]
