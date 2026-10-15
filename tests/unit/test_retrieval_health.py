import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from agents.domain.thread import ThreadScope
from knowledge.retrieve import service
from knowledge.retrieve.search import ChunkRow
from llm import reranker
from llm.reranker import RerankHit

SCOPE = ThreadScope("web", "synthetic")
ROW = ChunkRow(1, "synthetic", None, None, "synthetic content", 0.2)


@pytest.fixture
def branches(monkeypatch: pytest.MonkeyPatch) -> tuple[AsyncMock, AsyncMock, AsyncMock]:
    vector = AsyncMock(return_value=[ROW])
    lexical = AsyncMock(return_value=[])
    rank = AsyncMock(return_value=[RerankHit(0, 0.9)])
    monkeypatch.setattr(service, "vector_search", vector)
    monkeypatch.setattr(service, "lexical_search", lexical)
    monkeypatch.setattr(
        service, "get_settings", lambda: SimpleNamespace(RERANK_MIN_SCORE=0.5, RAG_MAX_DISTANCE=0.6)
    )
    monkeypatch.setattr(
        reranker, "get_reranker", lambda: SimpleNamespace(rerank=rank, diem_dang_tin=True)
    )
    return vector, lexical, rank


async def test_healthy_found_et_api_liste_compatible(branches: Any) -> None:
    vector, lexical, _ = branches
    backend = service.HybridKnowledge()
    result = await backend.search_detailed(SCOPE, "synthetic query", 5)
    assert len(result.chunks) == 1 and not result.filtered
    assert not result.retrieval_degraded and not result.rerank_degraded
    assert await backend.search(SCOPE, "synthetic query", 5) == result.chunks
    assert vector.await_args.args[0] == lexical.await_args.args[0] == SCOPE


async def test_vraie_absence_exige_deux_branches_saines(branches: Any) -> None:
    vector, lexical, rank = branches
    vector.return_value = lexical.return_value = []
    result = await service.HybridKnowledge().search_detailed(SCOPE, "q", 5)
    assert not result.chunks and not result.filtered and not result.retrieval_degraded
    rank.assert_not_awaited()


@pytest.mark.parametrize("side", ["vector", "lexical", "both"])
async def test_absence_partielle_ou_totale_en_panne_n_est_pas_empty(
    branches: Any, side: str
) -> None:
    vector, lexical, rank = branches
    vector.return_value = lexical.return_value = []
    if side in ("vector", "both"):
        vector.side_effect = RuntimeError("synthetic failure")
    if side in ("lexical", "both"):
        lexical.side_effect = RuntimeError("synthetic failure")
    with pytest.raises(service.RetrievalUnavailableError):
        await service.HybridKnowledge().search_detailed(SCOPE, "q", 5)
    rank.assert_not_awaited()


@pytest.mark.parametrize("failed_side", ["vector", "lexical"])
async def test_branche_survivante_avec_hits_reste_utilisable(
    branches: Any, failed_side: str
) -> None:
    vector, lexical, _ = branches
    failed, healthy = (vector, lexical) if failed_side == "vector" else (lexical, vector)
    failed.side_effect = RuntimeError("synthetic failure")
    healthy.return_value = [ROW]
    result = await service.HybridKnowledge().search_detailed(SCOPE, "q", 5)
    assert len(result.chunks) == 1 and result.retrieval_degraded
    assert not result.rerank_degraded


async def test_filtrage_sain_distinct_absence_et_panne(branches: Any) -> None:
    _, lexical, rank = branches
    rank.return_value = [RerankHit(0, 0.1)]
    backend = service.HybridKnowledge()
    result = await backend.search_detailed(SCOPE, "q", 5)
    assert result.filtered and not result.chunks and not result.retrieval_degraded
    lexical.side_effect = RuntimeError("synthetic failure")
    with pytest.raises(service.RetrievalUnavailableError):
        await backend.search_detailed(SCOPE, "q", 5)


@pytest.mark.parametrize(
    "hits",
    [
        [],
        [RerankHit(-1, 0.9)],
        [RerankHit(1, 0.9)],
        [RerankHit(0, float("nan"))],
        [RerankHit(0, float("inf"))],
        [RerankHit(0, 0.9), RerankHit(0, 0.8)],
        [RerankHit(True, 0.9)],
    ],
)
async def test_rerank_malforme_utilise_rrf_sans_faux_no_result(branches: Any, hits: Any) -> None:
    _, _, rank = branches
    rank.return_value = hits
    result = await service.HybridKnowledge().search_detailed(SCOPE, "q", 5)
    assert len(result.chunks) == 1 and result.rerank_degraded
    assert result.chunks[0].chunk_id == "1" and result.chunks[0].score == 0.0
    assert not result.filtered


async def test_timeout_rerank_utilise_rrf_et_ne_filtre_pas(branches: Any) -> None:
    _, _, rank = branches
    rank.side_effect = TimeoutError()
    result = await service.HybridKnowledge().search_detailed(SCOPE, "q", 5)
    assert result.rerank_degraded and result.chunks


@pytest.mark.parametrize("stage", ["retrieval", "rerank"])
async def test_annulation_ne_devient_pas_empty_ou_fallback(branches: Any, stage: str) -> None:
    vector, _, rank = branches
    (vector if stage == "retrieval" else rank).side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await service.HybridKnowledge().search_detailed(SCOPE, "q", 5)


async def test_query_vide_sans_io_et_k_invalide_refuse(branches: Any) -> None:
    vector, lexical, rank = branches
    backend = service.HybridKnowledge()
    assert await backend.search(SCOPE, "   ", 5) == []
    with pytest.raises(ValueError):
        await backend.search(SCOPE, "q", 0)
    for call in (vector, lexical, rank):
        call.assert_not_awaited()


async def test_branches_demarrent_en_parallele(branches: Any) -> None:
    vector, lexical, _ = branches
    both_started = asyncio.Event()
    started = 0

    async def search(*_: Any) -> list[ChunkRow]:
        nonlocal started
        started += 1
        if started == 2:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), 1)
        return [ROW]

    vector.side_effect = lexical.side_effect = search
    result = await service.HybridKnowledge().search_detailed(SCOPE, "q", 5)
    assert started == 2 and result.chunks
