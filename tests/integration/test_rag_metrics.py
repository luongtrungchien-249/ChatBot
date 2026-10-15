import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from agents.domain.telemetry import RagObservation
from agents.domain.thread import ThreadScope
from agents.ports.llm import CallContext, ToolCall
from infra.db import execute, fetch
from infra.metrics import _rag_prometheus
from infra.runtime_metrics import record_rag
from knowledge.retrieve import service
from knowledge.retrieve.search import ChunkRow
from llm import reranker
from llm.reranker import RerankHit
from tools import knowledge_search, registry


async def test_rag_attempts_distincts_meme_trace_et_sans_contenu(postgres_san_sang: None) -> None:
    trace = uuid.uuid4().hex
    try:
        await record_rag(trace, "web", RagObservation("error", retrieval_degraded=True), 100)
        await record_rag(trace, "web", RagObservation("found", rerank_degraded=True), 200)
        rows = await fetch("SELECT * FROM rag_telemetry WHERE trace_id=$1 ORDER BY id", trace)
        assert len(rows) == 2 and rows[0]["id"] != rows[1]["id"]
        assert rows[0]["outcome"] == "error" and rows[1]["outcome"] == "found"
        assert rows[0]["retrieval_degraded"] and rows[1]["rerank_degraded"]
        assert all(field not in rows[0] for field in ("query", "content", "thread_id", "sender_id"))
        rendered = "\n".join(await _rag_prometheus())
        assert (
            trace not in rendered and "sender_id=" not in rendered and "thread_id=" not in rendered
        )
    finally:
        await execute("DELETE FROM rag_telemetry WHERE trace_id=$1", trace)


@pytest.mark.parametrize("scenario", ["found", "uncertain", "filtered", "error"])
async def test_outcome_natif_tool_jusqua_db_sans_api_externe(
    postgres_san_sang: None,
    monkeypatch: pytest.MonkeyPatch,
    scenario: str,
) -> None:
    trace = uuid.uuid4().hex
    ctx = CallContext(ThreadScope("web", "synthetic"), "synthetic", trace)
    row = ChunkRow(
        1, "synthetic", None, None, "synthetic content", 0.56 if scenario == "uncertain" else 0.2
    )
    vector = AsyncMock(return_value=[row])
    lexical = AsyncMock(return_value=[])
    if scenario == "error":
        vector.side_effect = lexical.side_effect = RuntimeError("synthetic retrieval failure")
    monkeypatch.setattr(service, "vector_search", vector)
    monkeypatch.setattr(service, "lexical_search", lexical)
    monkeypatch.setattr(
        service, "get_settings", lambda: SimpleNamespace(RERANK_MIN_SCORE=0.5, RAG_MAX_DISTANCE=0.6)
    )
    monkeypatch.setattr(
        reranker,
        "get_reranker",
        lambda: SimpleNamespace(
            diem_dang_tin=True,
            rerank=AsyncMock(return_value=[RerankHit(0, 0.1 if scenario == "filtered" else 0.9)]),
        ),
    )
    monkeypatch.setattr(
        knowledge_search, "get_settings", lambda: SimpleNamespace(RAG_HOI_LAI_TU=0.5)
    )
    monkeypatch.setattr(
        registry,
        "_REGISTRY",
        (
            registry.Registration(
                knowledge_search.KNOWLEDGE_SEARCH_DEFINITION,
                knowledge_search.run_observed_knowledge_search,
                "synthetic",
                lambda: True,
            ),
        ),
    )
    monkeypatch.setattr(registry, "_ghi_so", AsyncMock(return_value=1))
    try:
        result = await registry._run_one(
            ToolCall("c", "search_knowledge_base", {"query": "q"}), ctx
        )
        rows = await fetch("SELECT * FROM rag_telemetry WHERE trace_id=$1", trace)
        assert len(rows) == 1
        assert rows[0]["outcome"] == scenario
        assert rows[0]["retrieval_degraded"] is (scenario == "error")
        assert rows[0]["low_confidence"] is (scenario == "uncertain")
        assert result.ok is (scenario != "error")
        assert vector.await_count == lexical.await_count == (2 if scenario == "uncertain" else 1)
    finally:
        await execute("DELETE FROM rag_telemetry WHERE trace_id=$1", trace)


async def test_rag_fenetre_ignore_historique_et_annulations_pour_degradation(
    postgres_san_sang: None,
) -> None:
    trace = uuid.uuid4().hex

    async def totals() -> dict[str, float]:
        return {
            name: float(value)
            for name, value in (
                line.rsplit(" ", 1) for line in await _rag_prometheus() if not line.startswith("#")
            )
        }

    before = await totals()
    try:
        await record_rag(trace, "web", RagObservation("filtered"), 100)
        await execute(
            "UPDATE rag_telemetry SET created_at=now()-interval '6 minutes' WHERE trace_id=$1",
            trace,
        )
        await record_rag(trace, "web", RagObservation("cancelled", True, True), 500)
        await record_rag(trace, "web", RagObservation("uncertain", False, False, True), 300)
        after = await totals()
        assert (
            after['cp_rag_requests{outcome="filtered"}']
            == before['cp_rag_requests{outcome="filtered"}']
        )
        assert (
            after['cp_rag_requests{outcome="cancelled"}']
            == before['cp_rag_requests{outcome="cancelled"}'] + 1
        )
        assert (
            after['cp_rag_requests{outcome="uncertain"}']
            == before['cp_rag_requests{outcome="uncertain"}'] + 1
        )
        assert (
            after['cp_rag_degraded_requests{stage="any"}']
            == before['cp_rag_degraded_requests{stage="any"}']
        )
        assert (
            after["cp_rag_low_confidence_requests"] == before["cp_rag_low_confidence_requests"] + 1
        )
    finally:
        await execute("DELETE FROM rag_telemetry WHERE trace_id=$1", trace)
