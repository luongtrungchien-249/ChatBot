"""Nap mot tep vao knowledge base: extract -> chunk -> contextualize -> embed -> upsert.

CHI ADMIN duoc nap (master-plan section 3.4). Cuong che o tang lenh: chi co
`uv run python -m main.cli ingest <path>` goi duoc ham nay, khong co route HTTP nao.
Moi lan nap ghi lai nguoi nap vao `kb_document.ingested_by`.

Ban ghi la BAT BIEN theo phien ban: nap lai cung mot tep voi noi dung khac se tao
`version` moi chu khong sua ban cu. Ly do: mot cau tra loi da trich dan chunk 42 thi
chunk 42 phai con nguyen van do — sua tai cho la lam moi trich dan cu noi doi.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from infra.db import fetch, transaction
from infra.logger import get_logger
from llm.embedder import get_embedder

from .chunk import Chunk, chunk_document
from .extract import extract_text

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


async def ingest_file(path: Path, ingested_by: str, title: str | None = None) -> IngestResult:
    doc_title = title or path.stem
    text = extract_text(path)
    if not text.strip():
        raise ValueError(f"{path} khong co chu nao doc duoc")

    checksum = _checksum(text)
    source_path = str(path.resolve())

    # Nap lai y het thi khong lam gi: embed lai vai tram chunk de ra dung ket qua cu
    # la dot tien. So sanh checksum cua VAN BAN da trich, khong phai cua tep — mot
    # PDF sua metadata van cho ra cung noi dung.
    existing = await fetch(
        """SELECT id, version, checksum FROM kb_document
            WHERE source_path = $1 ORDER BY version DESC LIMIT 1""",
        source_path,
    )
    if existing and existing[0]["checksum"] == checksum:
        _log.info("tai lieu khong doi, bo qua", path=source_path, version=existing[0]["version"])
        return IngestResult(
            doc_id=int(existing[0]["id"]),
            title=doc_title,
            version=int(existing[0]["version"]),
            chunks=0,
            skipped=True,
        )

    version = int(existing[0]["version"]) + 1 if existing else 1
    chunks = chunk_document(text)
    if not chunks:
        raise ValueError(f"{path} khong cat duoc chunk nao")

    embed_inputs = [contextualize(c, doc_title) for c in chunks]
    vectors: list[list[float]] = []
    embedder = get_embedder()
    for start in range(0, len(embed_inputs), _EMBED_BATCH):
        vectors.extend(await embedder.embed(embed_inputs[start : start + _EMBED_BATCH]))

    # Mot transaction cho ca tai lieu: hong giua chung ma van de lai nua so chunk
    # nghia la bot tra loi dua tren nua tai lieu ma khong ai biet.
    async with transaction() as connection:
        row = await connection.fetchrow(
            """INSERT INTO kb_document (title, source_path, version, checksum, ingested_by)
               VALUES ($1, $2, $3, $4, $5) RETURNING id""",
            doc_title,
            source_path,
            version,
            checksum,
            ingested_by,
        )
        doc_id = int(row["id"])
        for chunk, embed_input, vector in zip(chunks, embed_inputs, vectors, strict=True):
            await connection.execute(
                """INSERT INTO kb_chunk
                     (doc_id, ord, section, page, content, embed_input, embedding, token_count)
                   VALUES ($1,$2,$3,NULL,$4,$5,$6::vector,$7)""",
                doc_id,
                chunk.ord,
                chunk.section,
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
