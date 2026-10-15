"""Hai duong tim, chay SONG SONG.

CA HAI deu loc `d.la_ban_moi_nhat`. `pipeline.py` co y bat bien theo phien ban — nap
lai tao `version + 1` va GIU ban cu — nen thieu dieu kien nay thi ket qua tim kiem
tron chunk v1 voi v2 ngay tu lan nap lai dau tien: noi dung cu va moi cung xuat hien,
trung lap, va bot trich dan ca thu da bi thay the. Khong loi nao bao ra.

LUU Y cho lan dau them bo loc metadata that (theo tai lieu, theo nhom): voi index gan
dung, `WHERE` duoc ap SAU khi index quet xong. `hnsw.ef_search` mac dinh 40 ma bo loc
khop 10% so dong thi trung binh chi con ~4 dong song sot — mat phan lon recall ma
khong co loi nao. Luc do phai bat `hnsw.iterative_scan`. Dieu kien `la_ban_moi_nhat`
hien tai khong dinh loi do vi no dung voi gan nhu TOAN BO so dong.

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

from agents.domain.thread import ThreadScope, scope_key
from infra.db import fetch
from infra.logger import get_logger
from knowledge.provenance import (
    KnowledgeProvenanceError,
    inspect_knowledge_provenance,
    status_from_row,
)
from llm.embedder import EmbeddingIdentity, embed_query, embedding_identity

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
    #: Khoang cach cosine toi cau hoi. None voi ket qua tu duong BM25 —
    #: duong do khong tinh khoang cach, va no khop bang TU nen da co tin hieu
    #: rieng khong can den thuoc do nay.
    distance: float | None = None
    doc_id: str | None = None
    doc_version: int | None = None
    doc_scope: str | None = None
    is_latest: bool | None = None


def _to_row(row: Any, distance: float | None = None) -> ChunkRow:
    return ChunkRow(
        distance=distance,
        chunk_id=int(row["id"]),
        doc_title=row["title"],
        section=row["section"],
        page=row["page"],
        content=row["content"],
        doc_id=str(row["doc_id"]),
        doc_version=int(row["doc_version"]),
        doc_scope=row["doc_scope"],
        is_latest=bool(row["is_latest"]),
    )


async def _ready_identity(scope: ThreadScope) -> EmbeddingIdentity:
    identity = embedding_identity()
    status = await inspect_knowledge_provenance(scope, identity=identity)
    if not status.ready:
        raise KnowledgeProvenanceError(status)
    return identity


def _provenance_cte(identity_arg: int) -> str:
    """Check the same SQL snapshot used for candidates, including empty results.

    Preflight avoids paid embedding on unready corpora. This second check prevents
    a concurrent ingestion/attestation from silently hiding incompatible documents.
    Parameter positions are internal constants; no user text is interpolated.
    """
    provider, model, dim, revision = (f"${identity_arg + i}" for i in range(4))
    return f"""WITH visible_documents AS MATERIALIZED (
                  SELECT d.* FROM kb_document d
                   WHERE d.la_ban_moi_nhat AND d.pham_vi IN ('chung', $3)
                     AND EXISTS (SELECT 1 FROM kb_chunk c WHERE c.doc_id = d.id)
              ), provenance AS (
                  SELECT count(*) AS total_documents,
                         count(*) FILTER (WHERE embedding_provider IS NULL) AS unknown_documents,
                         count(*) FILTER (WHERE embedding_provider IS NOT NULL AND
                           (embedding_provider, embedding_model, embedding_dim, embedding_revision)
                           IS DISTINCT FROM ({provider}::text,{model}::text,{dim}::int,
                                             {revision}::text)) AS mismatched_documents
                    FROM visible_documents
              )"""


def _checked_rows(rows: list[Any], identity: EmbeddingIdentity) -> list[ChunkRow]:
    if not rows:
        raise RuntimeError("Missing retrieval readiness row")
    status = status_from_row(rows[0], identity)
    if not status.ready:
        raise KnowledgeProvenanceError(status)
    return [
        _to_row(row, float(row["distance"]) if row["distance"] is not None else None)
        for row in rows if row["id"] is not None
    ]


def _identity_args(identity: EmbeddingIdentity) -> tuple[str, str, int, str]:
    return identity.provider, identity.model, identity.dimensions, identity.revision


async def vector_search(
    scope: ThreadScope, query: str, limit: int = CANDIDATES_PER_SIDE
) -> list[ChunkRow]:
    """`<=>` la khoang cach cosine cua pgvector: CANG NHO CANG GIONG.

    Index HNSW o migration 0004 phuc vu dung phep toan nay. Doi sang `<->` hay `<#>`
    la index thanh vo dung va truy van tut ve quet tuan tu — im lang, chi cham dan.
    """
    identity = await _ready_identity(scope)
    vector = await embed_query(query)
    if embedding_identity() != identity:
        raise RuntimeError("Embedding configuration changed during retrieval")
    rows = await fetch(
        _provenance_cte(4) + """
            SELECT hits.*, provenance.* FROM provenance LEFT JOIN LATERAL (
                SELECT c.id, c.section, c.page, c.content, d.title,
                       d.id AS doc_id, d.version AS doc_version, d.pham_vi AS doc_scope,
                       d.la_ban_moi_nhat AS is_latest, (c.embedding <=> $1::vector) AS distance
                  FROM kb_chunk c JOIN visible_documents d ON d.id = c.doc_id
                 WHERE (d.embedding_provider,d.embedding_model,d.embedding_dim,d.embedding_revision)
                       = ($4::text,$5::text,$6::int,$7::text)
                 ORDER BY c.embedding <=> $1::vector LIMIT $2
            ) hits ON true""",
        "[" + ",".join(f"{v:.7f}" for v in vector) + "]",
        limit,
        scope_key(scope),
        *_identity_args(identity),
    )
    return _checked_rows(rows, identity)


async def lexical_search(
    scope: ThreadScope, query: str, limit: int = CANDIDATES_PER_SIDE
) -> list[ChunkRow]:
    """BM25-kieu qua tsvector. Cau hoi cung phai di qua `vn_tsv` de bo dau y het luc
    lap chi muc — mot ben bo dau mot ben khong thi khong bao gio khop.

    GIU `plainto_tsquery`, tuc noi cac tu bang VA. Da thu doi sang HOAC (08/09/2026)
    va da HOAN LAI — ghi o day de khong ai thu lai ma khong doc so:

        Trieu chung ban dau: tren corpus mon an, moi cau hoi tu nhien deu cho 0 ket
        qua ben lexical ("Ga ham bi do can nguyen lieu gi" doi chunk phai chua ca
        "can" lan "gi"). Doi sang HOAC thi so ket qua nhay len 133-174.

        Nhung do chi so CUOI thi nguoc lai:

            Recall@5 chi vector   96,1%
            Recall@5 chi BM25     71,1%
            Recall@5 RRF ca hai   82,5%   <- TE HON chi dung vector

        RRF coi hai bang xep hang la ngang nhau. Khi mot bang yeu han, no keo ket qua
        xuong. Quet trong so cho BM25 tu 0,0 den 1,0: recall cao nhat o DUNG 0,0, va
        cac cau hoi tieng Viet dat 6/6 o MOI trong so — tuc duong vector da tu lo
        duoc chung, BM25 khong them duoc gi ma chi them nhieu.

    Vai that su cua BM25 o day la bat thu embedding lam nhoe: ma san pham, so hieu
    van ban ("QD-145/2026"). Voi vai tro do thi VA moi dung — no chi ban khi khop
    chinh xac, va im lang phan con lai. "Duong lexical tra ve 0" khong phai loi; do
    la no dang lam dung viec.
    """
    # Distance improves the fallback filter, but lexical matching remains available
    # during an embedding outage. HybridKnowledge marks that partial result degraded.
    identity = await _ready_identity(scope)
    vector: list[float] | None
    try:
        vector = await embed_query(query)
    except Exception as error:
        vector = None
        _log.warning("embedding gian doan, lexical van tra cuu", error=type(error).__name__)
    if embedding_identity() != identity:
        raise RuntimeError("Embedding configuration changed during retrieval")
    rows = await fetch(
        _provenance_cte(5) + """
            SELECT hits.*, provenance.* FROM provenance LEFT JOIN LATERAL (
                SELECT c.id, c.section, c.page, c.content, d.title,
                       d.id AS doc_id, d.version AS doc_version, d.pham_vi AS doc_scope,
                       d.la_ban_moi_nhat AS is_latest,
                       CASE WHEN $4::vector IS NULL THEN NULL
                            ELSE (c.embedding <=> $4::vector) END AS distance
                  FROM kb_chunk c JOIN visible_documents d ON d.id = c.doc_id,
                       plainto_tsquery('simple', unaccent('unaccent', $1)) AS q
                 WHERE c.tsv @@ q AND
                       (d.embedding_provider,d.embedding_model,d.embedding_dim,d.embedding_revision)
                       = ($5::text,$6::text,$7::int,$8::text)
                 ORDER BY ts_rank(c.tsv, q) DESC LIMIT $2
            ) hits ON true""",
        query,
        limit,
        scope_key(scope),
        "[" + ",".join(f"{v:.7f}" for v in vector) + "]" if vector is not None else None,
        *_identity_args(identity),
    )
    return _checked_rows(rows, identity)
