import uuid

from evals.corpus_contract import check_corpus, corpus_fingerprint
from evals.dataset_contract import GoldenRecord
from infra.db import execute, fetch


async def test_real_corpus_preflight_rejects_stale_scope_and_missing(
    postgres_san_sang: None,
) -> None:
    documents: list[int] = []
    path = "synthetic-preflight-" + uuid.uuid4().hex
    before = await corpus_fingerprint()
    try:
        chunks: list[str] = []
        for index, (latest, scope) in enumerate(
            ((True, "chung"), (False, "chung"), (True, "web:other"))
        ):
            doc = (
                await fetch(
                    """INSERT INTO kb_document
                   (title,source_path,checksum,ingested_by,la_ban_moi_nhat,pham_vi)
                   VALUES('synthetic',$1,'synthetic','test',$2,$3) RETURNING id""",
                    f"{path}-{index}",
                    latest,
                    scope,
                )
            )[0]["id"]
            documents.append(doc)
            vector = "[" + ",".join(["0"] * 1024) + "]"
            chunk = (
                await fetch(
                    """INSERT INTO kb_chunk(doc_id,ord,content,embed_input,embedding,token_count)
                   VALUES($1,0,'synthetic','synthetic',$2::vector,1) RETURNING id""",
                    doc,
                    vector,
                )
            )[0]["id"]
            chunks.append(str(chunk))
        records = [
            GoldenRecord(
                f"q{index}",
                "Synthetic",
                "Expected",
                (identifier,),
                (),
                (),
                "single_chunk",
                True,
                "chung",
                "",
            )
            for index, identifier in enumerate([*chunks, "-1"])
        ]
        checked = await check_corpus(records)
        assert checked.exit_code == 1
        assert [issue.code for issue in checked.issues] == [
            "stale_version",
            "scope_mismatch",
            "missing_chunk",
        ]
        assert checked.fingerprint != before
        assert checked.fingerprint == await corpus_fingerprint()
    finally:
        await execute("DELETE FROM kb_document WHERE id=ANY($1::bigint[])", documents)
    assert before == await corpus_fingerprint()
