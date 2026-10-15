"""Nap mot tep vao knowledge base: extract -> chunk -> contextualize -> embed -> upsert.

CHI ADMIN duoc nap (master-plan section 3.4). Cuong che o tang lenh: chi co
`uv run python -m main.cli ingest <path>` goi duoc ham nay, khong co route HTTP nao.
Moi lan nap ghi lai nguoi nap vao `kb_document.ingested_by`.

Ban ghi la BAT BIEN theo phien ban: nap lai cung mot tep voi noi dung khac se tao
`version` moi chu khong sua ban cu. Ly do: mot cau tra loi da trich dan chunk 42 thi
chunk 42 phai con nguyen van do — sua tai cho la lam moi trich dan cu noi doi.
"""

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agents.policy.injection import detect_injection
from infra.db import fetch, transaction
from infra.logger import get_logger
from knowledge.provenance import identity_from_row
from llm.embedder import EmbeddingIdentity, embedding_identity, get_embedder

from .chunk import Chunk, chunk_document
from .extract import extract_document

_log = get_logger()

#: Embed theo lo. Mot tai lieu vai tram chunk ma goi tung cai la vai tram vong mang.
_EMBED_BATCH = 64


@dataclass(frozen=True, slots=True)
class IngestResult:
    doc_id: int
    title: str
    version: int
    chunks: int
    skipped: bool


def contextualize(chunk: Chunk, title: str) -> str:
    """Van ban dem di EMBED. Khac `content` — cai do giu NGUYEN VAN de trich dan.

    Them mot dong ngu canh o dau: tai lieu nao, muc nao. Chunk cat ra khoi tai lieu
    thi mat het ngu canh — "trong vong 7 ngay lam viec" khong noi len dieu gi neu
    khong biet no thuoc muc "Chinh sach hoan tien" cua "So tay nhan vien 2026".
    Do la contextual retrieval, va o day no lam bang METADATA co san chu khong bang
    mot lan goi model cho tung chunk: hai cach cai thien gan bang nhau tren tai lieu
    co tieu de ro rang, ma cach nay khong ton tien va khong the bia.
    """
    section = chunk.section
    if not section:
        where = title
    elif section == title or section.startswith(f"{title} > "):
        # Tieu de cap mot cua tai lieu thuong CHINH LA ten tai lieu. Ghep them lan
        # nua thanh "So tay 2026 > So tay 2026 > Hoan tien" — vua ton token vua lam
        # trich dan doc nhu loi danh may.
        where = section
    else:
        where = f"{title} > {section}"
    return f"[{where}]\n{chunk.content}"


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_LATEST_DOCUMENT_SQL = """SELECT id, version, max(version) OVER () AS max_version,
                                checksum, title, pham_vi,
                                embedding_provider, embedding_model, embedding_dim,
                                embedding_revision
                           FROM kb_document
                          WHERE source_path = $1
                          ORDER BY la_ban_moi_nhat DESC, version DESC LIMIT 1"""


def _may_skip(existing: list[Any], checksum: str, identity: EmbeddingIdentity, ep: bool) -> bool:
    if not existing or ep:
        return False
    document = existing[0]
    if document["checksum"] != checksum:
        return False
    if identity_from_row(document) != identity:
        raise ValueError(
            "Tai lieu khong doi nhung embedding provenance chua biet hoac khong khop. "
            "Chi attest khi co bang chung; dung --nap-lai de tao phien ban embedding moi."
        )
    return True


def _validate_vectors(vectors: list[list[float]], count: int, identity: EmbeddingIdentity) -> None:
    if len(vectors) != count or any(
        len(vector) != identity.dimensions
        or any(type(value) not in (int, float) or not math.isfinite(value) for value in vector)
        for vector in vectors
    ):
        raise ValueError("Embedding response count/dimension/values do not match document identity")


async def ingest_file(
    path: Path, ingested_by: str, title: str | None = None, ep: bool = False
) -> IngestResult:
    doc_title = title or path.stem
    tai_lieu = extract_document(path)
    text = tai_lieu.text
    if not text.strip():
        raise ValueError(f"{path} khong co chu nao doc duoc")

    checksum = _checksum(text)
    source_path = str(path.resolve())

    # Nap lai y het thi khong lam gi: embed lai vai tram chunk de ra dung ket qua cu
    # la dot tien. So sanh checksum cua VAN BAN da trich, khong phai cua tep — mot
    # PDF sua metadata van cho ra cung noi dung.
    #
    # `ep=True` bo qua cho tat nay. Can no vi checksum chi biet VAN BAN doi hay khong,
    # no khong biet CACH CAT doi. Doi luat cat muc (chunk.py) hay luat lam sach ma
    # tep khong doi thi day la duong duy nhat de dua thay doi do vao CSDL — khong co
    # no thi ban vá nam trong ma nguon va khong bao gio toi duoc kho dang chay.
    identity = embedding_identity()
    existing = await fetch(_LATEST_DOCUMENT_SQL, source_path)
    if _may_skip(existing, checksum, identity, ep):
        _log.info("tai lieu khong doi, bo qua", path=source_path, version=existing[0]["version"])
        return IngestResult(
            doc_id=int(existing[0]["id"]),
            title=doc_title,
            version=int(existing[0]["version"]),
            chunks=0,
            skipped=True,
        )

    chunks = chunk_document(text, tai_lieu.ban_do_trang)
    if not chunks:
        raise ValueError(f"{path} khong cat duoc chunk nao")

    # INPUT RAILS cho tai lieu. Mot tep co cau ra lenh nhung se nam trong CSDL vector
    # va duoc keo vao prompt o MOI cau hoi lien quan — nguy hiem hon mot tin nhan, vi
    # no lap lai mai. Ghi nhan, khong chan: quyen quyet dinh thuoc ve nguoi nap, va ho
    # can biet de xem lai tep truoc khi de no phuc vu ca nhom.
    dang_ngo = [(c.ord, detect_injection(c.content)) for c in chunks]
    dang_ngo = [(o, q) for o, q in dang_ngo if q.suspicious]
    if dang_ngo:
        _log.warning(
            "tai lieu chua doan giong chi thi cho tro ly — VAN NAP, hay xem lai",
            title=doc_title,
            so_chunk=len(dang_ngo),
            vi_tri=[o for o, _ in dang_ngo][:10],
            mau=sorted({m for _, q in dang_ngo for m in q.patterns}),
        )

    embed_inputs = [contextualize(c, doc_title) for c in chunks]
    vectors: list[list[float]] = []
    embedder = get_embedder()
    for start in range(0, len(embed_inputs), _EMBED_BATCH):
        vectors.extend(await embedder.embed(embed_inputs[start : start + _EMBED_BATCH]))
        if embedding_identity() != identity:
            raise ValueError("Embedding configuration changed during ingestion")
    _validate_vectors(vectors, len(chunks), identity)

    # Mot transaction cho ca tai lieu: hong giua chung ma van de lai nua so chunk
    # nghia la bot tra loi dua tren nua tai lieu ma khong ai biet.
    async with transaction() as connection:
        # Concurrent ingesters may have read the same version before embedding.
        # Serialize the final state transition and recheck under this lock. A
        # hash collision only serializes unrelated sources; it cannot mix their rows.
        await connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", source_path
        )
        current = await connection.fetch(_LATEST_DOCUMENT_SQL, source_path)
        if _may_skip(current, checksum, identity, ep):
            return IngestResult(
                doc_id=int(current[0]["id"]), title=doc_title,
                version=int(current[0]["version"]), chunks=0, skipped=True,
            )
        version = int(current[0]["max_version"]) + 1 if current else 1
        # A forced version must never make a formerly private document public.
        pham_vi = current[0]["pham_vi"] if current else "chung"
        # Ha co ban cu TRUOC khi chen ban moi. Phai nam trong cung transaction: nam
        # ngoai thi co mot khoang thoi gian hoac khong ban nao la moi nhat (mat het
        # ket qua tim kiem), hoac hai ban cung la moi nhat (tron v1 voi v2).
        #
        # Chi muc UNIQUE o migration 0012 cuong che bat bien nay bang CSDL, nen quen
        # dong nay se thanh loi chen thay vi mot ket qua tim kiem sai am tham.
        await connection.execute(
            "UPDATE kb_document SET la_ban_moi_nhat = false "
            "WHERE source_path = $1 AND la_ban_moi_nhat",
            source_path,
        )
        row = await connection.fetchrow(
            """INSERT INTO kb_document (title, source_path, version, checksum, ingested_by,
                      pham_vi, embedding_provider, embedding_model, embedding_dim,
                      embedding_revision, embedding_provenance)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'ingested') RETURNING id""",
            doc_title,
            source_path,
            version,
            checksum,
            ingested_by,
            pham_vi,
            identity.provider,
            identity.model,
            identity.dimensions,
            identity.revision,
        )
        doc_id = int(row["id"])
        for chunk, embed_input, vector in zip(chunks, embed_inputs, vectors, strict=True):
            await connection.execute(
                """INSERT INTO kb_chunk
                     (doc_id, ord, section, page, content, embed_input, embedding, token_count)
                   VALUES ($1,$2,$3,$4,$5,$6,$7::vector,$8)""",
                doc_id,
                chunk.ord,
                chunk.section,
                # Truoc day la NULL cung, nen cong cu `search_knowledge_base` co san
                # nhanh in "trang {c.page}" ma chua bao gio chay.
                chunk.page,
                chunk.content,
                embed_input,
                "[" + ",".join(f"{v:.7f}" for v in vector) + "]",
                # Uoc luong bang cung ti le ma prompt budget dung. Do that tung
                # chunk la them vai tram lan goi API cho mot con so chi de bao cao.
                int(len(chunk.content) / 3.6) + 1,
            )

    _log.info("da nap tai lieu", title=doc_title, version=version, chunks=len(chunks))
    return IngestResult(
        doc_id=doc_id, title=doc_title, version=version, chunks=len(chunks), skipped=False
    )
