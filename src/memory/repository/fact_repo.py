"""L3 — CHO DUY NHAT trong codebase cham bang `memory_fact`.

`ops/guard_sql.py` cuong che dieu do bang AST: bat ky chuoi nao chua "memory_fact"
o ngoai `memory/repository/` deu lam CI do. Luat khong phai de cho dep — no la mot
nua cua hang rao chong ro ri cross-group (nua kia la ThreadScope bat buoc).

MOI truy van o day deu co `platform = $1 AND thread_id = $2`. Khong co ngoai le,
khong co ham nao "tien the" bo qua. Doc lai file nay ma thay mot cau SQL thieu hai
dieu kien do thi do la mot lo ro ri.
"""

import uuid
from typing import Any

from agents.domain.thread import ThreadScope
from agents.ports.memory import Fact, FactSource, NewFact
from infra.db import execute, fetch
from infra.logger import get_logger
from llm.embedder import embed_query, get_embedder

from ..dedupe import (
    FORGET_MAX_CANDIDATES,
    FORGET_THRESHOLD,
    Insert,
    Replace,
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

    # Qua cache: duong nay chay o MOI tin nhan, va RAG embed DUNG chuoi nay mot lan
    # nua trong cung luot. Cache chung bo hang mot vong mang khoi duong phan hoi.
    vector = await embed_query(query)
    rows = await fetch(
        """SELECT id, subject_id, content, source, confidence, created_at
             FROM memory_fact
            WHERE platform = $1 AND thread_id = $2 AND subject_id = ANY($3::text[])
              AND revoked_at IS NULL
            ORDER BY embedding <=> $4::vector
            LIMIT $5""",
        scope.platform,
        scope.thread_id,
        subject_ids,
        _to_vector(vector),
        k,
    )
    facts = [_to_fact(r) for r in rows]

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
    """Ghi mot fact moi, sau khi kiem trung va mau thuan.

    Ba ket cuc: chen moi, bo qua vi trung y, hoac revoke cai cu roi chen cai moi.
    Xem memory/dedupe.py.
    """
    vector = (await get_embedder().embed([fact.content]))[0]

    existing = await fetch(
        """SELECT id, content, embedding
             FROM memory_fact
            WHERE platform = $1 AND thread_id = $2 AND subject_id = $3
              AND revoked_at IS NULL""",
        scope.platform,
        scope.thread_id,
        fact.subject_id,
    )
    decision = decide(
        fact.content,
        vector,
        [(str(r["id"]), r["content"], _parse_vector(r["embedding"])) for r in existing],
    )

    log = _log.bind(thread_id=scope.thread_id, subject_id=fact.subject_id)

    if isinstance(decision, Skip):
        log.info("fact trung y, bo qua", existing_id=decision.existing_id, sim=decision.similarity)
        return

    if isinstance(decision, Replace):
        log.info(
            "fact mau thuan voi ban cu, thay the",
            existing_id=decision.existing_id,
            sim=decision.similarity,
        )
        await _revoke(scope, [decision.existing_id], revoked_by=fact.created_by)

    assert isinstance(decision, Insert | Replace)
    await execute(
        """INSERT INTO memory_fact
             (platform, thread_id, subject_id, content, embedding,
              source, confidence, created_by)
           VALUES ($1,$2,$3,$4,$5::vector,$6,$7,$8)""",
        scope.platform,
        scope.thread_id,
        fact.subject_id,
        fact.content,
        _to_vector(vector),
        fact.source,
        fact.confidence,
        fact.created_by,
    )
    log.info("da ghi fact", source=fact.source)


async def match_for_forget(scope: ThreadScope, subject_id: str, pattern: str) -> list[Fact]:
    """Fact khop voi cau nguoi dung muon quen. KHONG xoa — chi liet ke de hoi.

    Khong co buoc xac nhan thi mot lan go nham la mat sach, ma soft delete lai khong
    co lenh khoi phuc (ARCHITECTURE.md section 6.2).
    """
    vector = await embed_query(pattern)
    rows = await fetch(
        """SELECT id, subject_id, content, source, confidence, created_at, embedding
             FROM memory_fact
            WHERE platform = $1 AND thread_id = $2 AND subject_id = $3
              AND revoked_at IS NULL""",
        scope.platform,
        scope.thread_id,
        subject_id,
    )

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
