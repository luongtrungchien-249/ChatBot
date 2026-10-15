"""L3 runtime repository; vector recovery lives in sibling embedding_rebuild.py.

`ops/guard_sql.py` cuong che dieu do bang AST: bat ky chuoi nao chua "memory_fact"
o ngoai `memory/repository/` deu lam CI do. Luat khong phai de cho dep — no la mot
nua cua hang rao chong ro ri cross-group (nua kia la ThreadScope bat buoc).

MOI truy van o day deu co `platform = $1 AND thread_id = $2`. Khong co ngoai le,
khong co ham nao "tien the" bo qua. Doc lai file nay ma thay mot cau SQL thieu hai
dieu kien do thi do la mot lo ro ri.
"""

import json
import math
import uuid
from dataclasses import dataclass
from typing import Any

from agents.domain.errors import UpstreamError
from agents.domain.thread import ThreadScope
from agents.ports.memory import Fact, FactSource, MemoryUnavailableError, NewFact
from infra.db import execute, fetch, transaction
from infra.logger import get_logger
from llm.embedder import EmbeddingIdentity, embed_query, embedding_identity, get_embedder

from ..dedupe import (
    FORGET_MAX_CANDIDATES,
    FORGET_THRESHOLD,
    Insert,
    Skip,
    cosine,
    decide,
)

_log = get_logger()

#: Ten bang, de cho khac tham chieu duoc MA KHONG phai viet lai chuoi do.
#:
#: ops/guard_sql.py cam chuoi "memory_fact" xuat hien ngoai thu muc nay, va luat do
#: dung. Nhung `main/container.py` van can biet ten bang de kiem so chieu cot vector
#: luc khoi dong. Xuat mot hang so la cach giai dung: mot noi dinh nghia, cho khac
#: import. Khoet mot ngoai le trong guard thi luat mat tac dung tu lan sau.
FACT_TABLE = "memory_fact"


@dataclass(frozen=True, slots=True)
class MemoryEmbeddingProvenanceStatus:
    total_facts: int
    unknown_facts: int
    mismatched_facts: int
    identity: EmbeddingIdentity

    @property
    def ready(self) -> bool:
        return self.unknown_facts == self.mismatched_facts == 0


class MemoryEmbeddingProvenanceError(MemoryUnavailableError):
    def __init__(self, status: MemoryEmbeddingProvenanceStatus) -> None:
        super().__init__(
            "Embedding ky uc chua duoc xac minh hoac khong khop. "
            "Van co the liet ke/audit/xoa bang ID; khong so sanh vector chua biet nguon.",
            UpstreamError(service="embed", status=409),
        )
        self.status = status

def _identity_args(identity: EmbeddingIdentity) -> tuple[str, str, int, str]:
    return identity.provider, identity.model, identity.dimensions, identity.revision


def _status(row: Any, identity: EmbeddingIdentity) -> MemoryEmbeddingProvenanceStatus:
    return MemoryEmbeddingProvenanceStatus(
        int(row["total_facts"]), int(row["unknown_facts"]), int(row["mismatched_facts"]), identity
    )


async def inspect_fact_embedding_provenance(
    scope: ThreadScope, subject_ids: list[str] | None = None,
    *, identity: EmbeddingIdentity | None = None,
) -> MemoryEmbeddingProvenanceStatus:
    """Scoped active metadata only; no content, API calls, writes, or backfill."""
    identity = identity or embedding_identity()
    rows = await fetch(
        """SELECT count(*) AS total_facts,
                  count(*) FILTER (WHERE embedding_provider IS NULL) AS unknown_facts,
                  count(*) FILTER (WHERE embedding_provider IS NOT NULL AND
                    (embedding_provider,embedding_model,embedding_dim,embedding_revision)
                    IS DISTINCT FROM ($4::text,$5::text,$6::int,$7::text)) AS mismatched_facts
             FROM memory_fact
            WHERE platform=$1 AND thread_id=$2 AND revoked_at IS NULL
              AND ($3::text[] IS NULL OR subject_id=ANY($3::text[]))""",
        scope.platform, scope.thread_id, subject_ids, *_identity_args(identity),
    )
    return _status(rows[0], identity)


async def _ready_identity(scope: ThreadScope, subjects: list[str]) -> EmbeddingIdentity:
    identity = embedding_identity()
    status = await inspect_fact_embedding_provenance(scope, subjects, identity=identity)
    if not status.ready:
        raise MemoryEmbeddingProvenanceError(status)
    return identity


def _assert_compatible(rows: list[Any], identity: EmbeddingIdentity) -> None:
    unknown = mismatched = 0
    columns = ("embedding_provider", "embedding_model", "embedding_dim", "embedding_revision")
    for row in rows:
        values = tuple(row[column] for column in columns)
        if any(value is None for value in values):
            unknown += 1
        elif values != _identity_args(identity):
            mismatched += 1
    if unknown or mismatched:
        raise MemoryEmbeddingProvenanceError(
            MemoryEmbeddingProvenanceStatus(len(rows), unknown, mismatched, identity)
        )


def _validate_vector(vector: list[float], identity: EmbeddingIdentity) -> None:
    if len(vector) != identity.dimensions or any(
        type(value) not in (int, float) or not math.isfinite(value) for value in vector
    ):
        raise ValueError("Fact embedding does not match its declared identity")


async def _insert_fact(
    connection: Any, scope: ThreadScope, fact: NewFact, vector: list[float],
    identity: EmbeddingIdentity,
) -> None:
    await connection.execute(
        """INSERT INTO memory_fact
             (platform,thread_id,subject_id,content,embedding,source,confidence,created_by,
              embedding_provider,embedding_model,embedding_dim,embedding_revision)
           VALUES ($1,$2,$3,$4,$5::vector,$6,$7,$8,$9,$10,$11,$12)""",
        scope.platform, scope.thread_id, fact.subject_id, fact.content, _to_vector(vector),
        fact.source, fact.confidence, fact.created_by, *_identity_args(identity),
    )


async def _lock_subject(connection: Any, scope: ThreadScope, subject_id: str) -> None:
    key = json.dumps(["memory-subject", scope.platform, scope.thread_id, subject_id])
    await connection.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", key)


_ACTIVE_SUBJECT_SQL = """SELECT id, content, embedding, embedding_provider, embedding_model,
                                embedding_dim, embedding_revision
                           FROM memory_fact
                          WHERE platform=$1 AND thread_id=$2 AND subject_id=$3
                            AND revoked_at IS NULL ORDER BY id FOR UPDATE"""


async def count_for_operations() -> int:
    """Tong so fact cho baseline van hanh; khong doc noi dung hay dinh danh.

    Day la ngoai le hep cho bao cao toan he thong. Moi API nghiep vu van bat buoc
    nhan ``ThreadScope``; ham nay nam trong repository de SQL cua bang fact khong
    ro ra tang van hanh.
    """
    rows = await fetch("SELECT count(*) AS total FROM memory_fact")
    return int(rows[0]["total"]) if rows else 0


async def hard_delete_scope(connection: Any, scope: ThreadScope) -> int:
    """Xoa vinh vien moi fact cua DUNG mot thread trong transaction cua caller."""
    status: str = await connection.execute(
        "DELETE FROM memory_fact WHERE platform = $1 AND thread_id = $2",
        scope.platform,
        scope.thread_id,
    )
    return int(status.rsplit(" ", 1)[-1])

#: pgvector nhan vector duoi dang chuoi '[a,b,c]'.
def _to_vector(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.7f}" for v in values) + "]"


def _to_fact(row: Any) -> Fact:
    return Fact(
        id=str(row["id"]),
        subject_id=row["subject_id"],
        content=row["content"],
        source=row["source"],
        confidence=float(row["confidence"]),
        created_at=row["created_at"],
    )


async def list_facts(scope: ThreadScope, subject_id: str) -> list[Fact]:
    """Toan bo fact CON HIEU LUC cua mot subject trong MOT thread."""
    rows = await fetch(
        """SELECT id, subject_id, content, source, confidence, created_at
             FROM memory_fact
            WHERE platform = $1 AND thread_id = $2 AND subject_id = $3
              AND revoked_at IS NULL
            ORDER BY created_at DESC""",
        scope.platform,
        scope.thread_id,
        subject_id,
    )
    return [_to_fact(r) for r in rows]


async def search_facts(scope: ThreadScope, subject_id: str, query: str, k: int = 5) -> list[Fact]:
    """Fact lien quan nhat toi `query`, trong pham vi MOT subject cua mot thread."""
    return await search_facts_for(scope, [subject_id], query, k)


async def search_facts_for(
    scope: ThreadScope, subject_ids: list[str], query: str, k: int = 5
) -> list[Fact]:
    """Nhu tren nhung tim tren NHIEU subject cung luc.

    Mot cau truy van chu khong phai nhieu lan goi, va quan trong hon: MOT lan embed.
    Duong nay chay o moi tin nhan, nen goi embedding hai lan cho hai subject la nhan
    doi mot khoan chi thuong truc — dung khoan ma llm/embedder.py vua duoc sua de
    dua vao chot chan ngan sach.

    `<=>` la khoang cach cosine cua pgvector: CANG NHO CANG GIONG. Index HNSW o
    migration 0003 phuc vu dung phep toan nay.
    """
    if not subject_ids:
        return []
    if not query.strip():
        collected: list[Fact] = []
        for subject in subject_ids:
            collected.extend(await list_facts(scope, subject))
        return collected

    if k < 1:
        raise ValueError("k must be positive")

    # Qua cache: duong nay chay o MOI tin nhan, va RAG embed DUNG chuoi nay mot lan
    # nua trong cung luot. Cache chung bo hang mot vong mang khoi duong phan hoi.
    identity = await _ready_identity(scope, subject_ids)
    vector = await embed_query(query)
    _validate_vector(vector, identity)
    if embedding_identity() != identity:
        raise ValueError("Embedding configuration changed during memory retrieval")
    rows = await fetch(
        """WITH visible_facts AS MATERIALIZED (
                SELECT * FROM memory_fact
                 WHERE platform=$1 AND thread_id=$2 AND subject_id=ANY($3::text[])
                   AND revoked_at IS NULL
            ), provenance AS (
                SELECT count(*) AS total_facts,
                       count(*) FILTER (WHERE embedding_provider IS NULL) AS unknown_facts,
                       count(*) FILTER (WHERE embedding_provider IS NOT NULL AND
                         (embedding_provider,embedding_model,embedding_dim,embedding_revision)
                         IS DISTINCT FROM ($6::text,$7::text,$8::int,$9::text)) AS mismatched_facts
                  FROM visible_facts
            )
            SELECT hits.*,provenance.* FROM provenance LEFT JOIN LATERAL (
                SELECT id,subject_id,content,source,confidence,created_at
                  FROM visible_facts
                 WHERE (embedding_provider,embedding_model,embedding_dim,embedding_revision)
                       = ($6::text,$7::text,$8::int,$9::text)
                 ORDER BY embedding <=> $4::vector LIMIT $5
            ) hits ON true""",
        scope.platform,
        scope.thread_id,
        subject_ids,
        _to_vector(vector),
        k,
        *_identity_args(identity),
    )
    status = _status(rows[0], identity)
    if not status.ready:
        raise MemoryEmbeddingProvenanceError(status)
    facts = [_to_fact(r) for r in rows if r["id"] is not None]

    if facts:
        # last_used_at cho biet fact nao that su duoc dung. Khong co cot nay thi
        # khong co cach nao don nhung fact khong ai cham toi trong sau thang.
        await execute(
            """UPDATE memory_fact SET last_used_at = now()
                WHERE platform = $1 AND thread_id = $2 AND id = ANY($3::bigint[])""",
            scope.platform,
            scope.thread_id,
            [int(f.id) for f in facts],
        )
    return facts


async def remember(scope: ThreadScope, fact: NewFact) -> None:
    """Insert or suppress exact text; never infer a destructive semantic update."""
    identity = await _ready_identity(scope, [fact.subject_id])
    vectors = await get_embedder().embed([fact.content])
    if len(vectors) != 1:
        raise ValueError("Expected one fact embedding")
    vector = vectors[0]
    _validate_vector(vector, identity)
    if embedding_identity() != identity:
        raise ValueError("Embedding configuration changed during memory write")
    async with transaction() as connection:
        await _lock_subject(connection, scope, fact.subject_id)
        existing = await connection.fetch(
            _ACTIVE_SUBJECT_SQL, scope.platform, scope.thread_id, fact.subject_id,
        )
        _assert_compatible(existing, identity)
        decision = decide(fact.content, vector, [
            (str(row["id"]), row["content"], _parse_vector(row["embedding"])) for row in existing
        ])
        if isinstance(decision, Skip):
            _log.info("fact trung chu, bo qua", existing_id=decision.existing_id)
            return
        assert isinstance(decision, Insert)
        await _insert_fact(connection, scope, fact, vector, identity)
    _log.info("da ghi fact", source=fact.source)


async def replace_fact(scope: ThreadScope, fact: NewFact, existing_id: str) -> None:
    """Explicit exact-ID update, requiring the same scope/subject and atomic writes.

    This admin/service API is intentionally not inferred by remember() or exposed
    as a new UI command. The caller must explicitly authorize the replacement.
    """
    if not existing_id.isdigit() or int(existing_id) < 1 or fact.source != "explicit":
        raise ValueError("Explicit replacement requires a positive fact ID and explicit source")
    identity = await _ready_identity(scope, [fact.subject_id])
    vectors = await get_embedder().embed([fact.content])
    if len(vectors) != 1:
        raise ValueError("Expected one fact embedding")
    vector = vectors[0]
    _validate_vector(vector, identity)
    if embedding_identity() != identity:
        raise ValueError("Embedding configuration changed during memory update")
    async with transaction() as connection:
        await _lock_subject(connection, scope, fact.subject_id)
        rows = await connection.fetch(
            _ACTIVE_SUBJECT_SQL, scope.platform, scope.thread_id, fact.subject_id,
        )
        _assert_compatible(rows, identity)
        if not any(int(row["id"]) == int(existing_id) for row in rows):
            raise ValueError("Active replacement target not found in this scope and subject")
        await connection.execute(
            """UPDATE memory_fact SET revoked_at=now(), revoked_by=$5
                WHERE platform=$1 AND thread_id=$2 AND subject_id=$3 AND id=$4
                  AND revoked_at IS NULL""",
            scope.platform, scope.thread_id, fact.subject_id, int(existing_id), fact.created_by,
        )
        await _insert_fact(connection, scope, fact, vector, identity)


async def match_for_forget(scope: ThreadScope, subject_id: str, pattern: str) -> list[Fact]:
    """Fact khop voi cau nguoi dung muon quen. KHONG xoa — chi liet ke de hoi.

    Khong co buoc xac nhan thi mot lan go nham la mat sach, ma soft delete lai khong
    co lenh khoi phuc (ARCHITECTURE.md section 6.2).
    """
    identity = embedding_identity()
    rows = await fetch(
        """SELECT id, subject_id, content, source, confidence, created_at, embedding,
                  embedding_provider,embedding_model,embedding_dim,embedding_revision
             FROM memory_fact
            WHERE platform = $1 AND thread_id = $2 AND subject_id = $3
              AND revoked_at IS NULL""",
        scope.platform,
        scope.thread_id,
        subject_id,
    )
    _assert_compatible(rows, identity)
    vector = await embed_query(pattern)
    _validate_vector(vector, identity)
    if embedding_identity() != identity:
        raise ValueError("Embedding configuration changed during memory forget matching")

    scored = [
        (cosine(vector, _parse_vector(r["embedding"])), _to_fact(r))
        for r in rows
    ]
    # Sap theo do giong roi CAT, khong chi loc theo nguong: nguong rong (0,30) de
    # khong bo sot cach noi cua nguoi dung, con viec cat top-N moi la thu giu danh
    # sach du ngan de nguoi ta thuc su doc no.
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [f for score, f in scored[:FORGET_MAX_CANDIDATES] if score >= FORGET_THRESHOLD]


async def revoke(scope: ThreadScope, fact_ids: list[str], revoked_by: str) -> int:
    """Soft delete. Tra ve so dong that su bi revoke."""
    return await _revoke(scope, fact_ids, revoked_by)


async def revoke_all(scope: ThreadScope, subject_id: str, revoked_by: str) -> int:
    """Revoke moi fact cua MOT subject trong MOT thread.

    `subject_id` la bat buoc, khong co bien the "xoa het cua ca nhom": lenh
    `quen het` cua mot nguoi chi duoc dung toi fact ve chinh ho.
    """
    status = await execute(
        """UPDATE memory_fact
              SET revoked_at = now(), revoked_by = $4
            WHERE platform = $1 AND thread_id = $2 AND subject_id = $3
              AND revoked_at IS NULL""",
        scope.platform,
        scope.thread_id,
        subject_id,
        revoked_by,
    )
    return _rows_affected(status)


async def _revoke(scope: ThreadScope, fact_ids: list[str], revoked_by: str) -> int:
    if not fact_ids:
        return 0
    status = await execute(
        """UPDATE memory_fact
              SET revoked_at = now(), revoked_by = $4
            WHERE platform = $1 AND thread_id = $2 AND id = ANY($3::bigint[])
              AND revoked_at IS NULL""",
        scope.platform,
        scope.thread_id,
        [int(i) for i in fact_ids],
        revoked_by,
    )
    return _rows_affected(status)


async def cho_duyet(scope: ThreadScope) -> list[Fact]:
    """Fact bot TU GHI ma chua ai xem lai (human-on-the-loop).

    Chi `source = 'implicit'`: fact explicit la do chinh nguoi dung noi ra, khong ai
    phai duyet loi cua ho.

    Sap theo thoi gian TANG DAN: cai cu nhat truoc, vi do la cai da nam trong prompt
    lau nhat va da anh huong nhieu cau tra loi nhat.
    """
    rows = await fetch(
        """SELECT id, subject_id, content, source, confidence, created_at
             FROM memory_fact
            WHERE platform = $1 AND thread_id = $2
              AND source = 'implicit'
              AND revoked_at IS NULL
              AND reviewed_at IS NULL
            ORDER BY created_at""",
        scope.platform,
        scope.thread_id,
    )
    return [_to_fact(r) for r in rows]


async def danh_dau_da_duyet(scope: ThreadScope, fact_ids: list[str], boi: str) -> int:
    """Danh dau da xem. KHONG doi noi dung fact — chi ghi lai rang co nguoi da nhin."""
    if not fact_ids:
        return 0
    status = await execute(
        """UPDATE memory_fact
              SET reviewed_at = now(), reviewed_by = $4
            WHERE platform = $1 AND thread_id = $2 AND id = ANY($3::bigint[])
              AND reviewed_at IS NULL""",
        scope.platform,
        scope.thread_id,
        [int(i) for i in fact_ids],
        boi,
    )
    return _rows_affected(status)


async def dump_thread(scope: ThreadScope) -> list[Fact]:
    """Cong cu AUDIT: moi fact con hieu luc cua ca mot thread, moi subject.

    Phai co TRUOC khi bat trich fact tu dong (L3 implicit) — khong nhin duoc bot da
    tu ghi gi thi khong the cho phep no tu ghi.
    """
    rows = await fetch(
        """SELECT id, subject_id, content, source, confidence, created_at
             FROM memory_fact
            WHERE platform = $1 AND thread_id = $2 AND revoked_at IS NULL
            ORDER BY subject_id, created_at""",
        scope.platform,
        scope.thread_id,
    )
    return [_to_fact(r) for r in rows]


def _parse_vector(raw: Any) -> list[float]:
    """pgvector tra ve chuoi '[a,b,c]' khi khong dang ky codec."""
    if isinstance(raw, list):
        return [float(v) for v in raw]
    return [float(v) for v in str(raw).strip("[]").split(",") if v]


def _rows_affected(status: str) -> int:
    """asyncpg tra ve 'UPDATE 3'."""
    parts = status.split()
    return int(parts[-1]) if parts and parts[-1].isdigit() else 0


def new_fact(
    subject_id: str, content: str, created_by: str, source: FactSource = "explicit"
) -> NewFact:
    """Fact do NGUOI DUNG noi thang ra: confidence 1,0.

    Fact do model tu trich (implicit) di duong khac va phai kem confidence that —
    xem TODO(giai-doan-7-implicit).
    """
    return NewFact(subject_id=subject_id, content=content, source=source, confidence=1.0,
                   created_by=created_by)


def pending_token() -> str:
    """Ma xac nhan cho lenh `quen`. Song trong Redis TTL 5 phut."""
    return uuid.uuid4().hex[:8]
