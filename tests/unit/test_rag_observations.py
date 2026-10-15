import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from agents.domain.telemetry import RagObservation
from agents.ports.llm import ToolCall
from infra import runtime_metrics
from knowledge.retrieve import service
from tools import knowledge_search, registry
from tools.knowledge_search import KnowledgeToolOutput, run_observed_knowledge_search

from .test_knowledge_tool import CTX, chunk


@pytest.fixture
def search(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    mock = AsyncMock(return_value=service.RetrievalResult([]))
    monkeypatch.setattr(service.knowledge, "search_detailed", mock)
    monkeypatch.setattr(
        knowledge_search, "get_settings", lambda: SimpleNamespace(RAG_HOI_LAI_TU=0.5)
    )
    return mock


@pytest.mark.parametrize("filtered,outcome", [(False, "empty"), (True, "filtered")])
async def test_no_result_classifie_par_donnees_pas_texte(
    search: AsyncMock, filtered: bool, outcome: str
) -> None:
    search.return_value = service.RetrievalResult([], filtered=filtered)
    result = await run_observed_knowledge_search({"query": "q"}, CTX)
    assert result.observation.outcome == outcome
    assert "Không tìm thấy" in result.text


async def test_texte_contenant_fallback_n_est_pas_un_no_result(search: AsyncMock) -> None:
    search.return_value = service.RetrievalResult(
        [chunk("Không tìm thấy — ceci est du contenu cité, pas le résultat de recherche")],
        retrieval_degraded=True,
        rerank_degraded=True,
    )
    result = await run_observed_knowledge_search({"query": "q"}, CTX)
    assert result.observation == RagObservation("found", True, True)
    assert search.await_args is not None and search.await_args.args[0] == CTX.scope


async def test_uncertain_deux_searches_une_observation_et_flags_combines(search: AsyncMock) -> None:
    search.side_effect = [
        service.RetrievalResult([chunk("first", distance=0.56)], retrieval_degraded=True),
        service.RetrievalResult([chunk("second", distance=0.57)], rerank_degraded=True),
    ]
    result = await run_observed_knowledge_search({"query": "q"}, CTX)
    assert search.await_count == 2
    assert result.observation == RagObservation("uncertain", True, True, True)
    assert "KẾT QUẢ KHÔNG CHẮC" in result.text


async def test_expansion_en_panne_garde_candidats_premiere_passe(search: AsyncMock) -> None:
    search.side_effect = [
        service.RetrievalResult([chunk("first", distance=0.56)]),
        service.RetrievalUnavailableError(),
    ]
    result = await run_observed_knowledge_search({"query": "q"}, CTX)
    assert result.observation == RagObservation("uncertain", True, False, True)
    assert "first" in result.text


async def test_deep_selection_faible_confiance_ne_redemande_pas_choix(search: AsyncMock) -> None:
    search.return_value = service.RetrievalResult([chunk("first", distance=0.9)])
    result = await run_observed_knowledge_search({"query": "q", "chon": "Muc"}, CTX)
    assert search.await_count == 1
    assert result.observation == RagObservation("found", low_confidence=True)
    assert "KẾT QUẢ KHÔNG CHẮC" not in result.text


@pytest.fixture
def tool_runner(monkeypatch: pytest.MonkeyPatch) -> tuple[AsyncMock, AsyncMock]:
    run = AsyncMock(return_value=KnowledgeToolOutput("synthetic text", RagObservation("found")))
    monkeypatch.setattr(
        registry,
        "_REGISTRY",
        (
            registry.Registration(
                knowledge_search.KNOWLEDGE_SEARCH_DEFINITION,
                run,
                "synthetic",
                lambda: True,
            ),
        ),
    )
    monkeypatch.setattr(registry, "_ghi_so", AsyncMock(return_value=1))
    monkeypatch.setattr(
        registry, "_compress_if_too_long", AsyncMock(side_effect=lambda text, *_: text)
    )
    record = AsyncMock()
    monkeypatch.setattr(registry, "record_rag", record)
    return run, record


async def test_registry_emet_une_mesure_et_garde_tool_port(tool_runner: Any) -> None:
    _, record = tool_runner
    result = await registry._run_one(ToolCall("c", "search_knowledge_base", {"query": "q"}), CTX)
    assert result.ok and "synthetic text" in result.content
    assert record.await_count == 1
    assert record.await_args.args[:3] == (CTX.trace_id, CTX.scope.platform, RagObservation("found"))


async def test_registry_erreur_de_retrieval_n_est_pas_success_empty(tool_runner: Any) -> None:
    run, record = tool_runner
    run.side_effect = service.RetrievalUnavailableError()
    result = await registry._run_one(ToolCall("c", "search_knowledge_base", {"query": "q"}), CTX)
    assert result.ok is False and "chưa tra cứu được" in result.content
    assert record.await_count == 1
    assert record.await_args.args[2] == RagObservation("error", retrieval_degraded=True)


async def test_registry_annulation_propage_et_mesure_cancelled(tool_runner: Any) -> None:
    run, record = tool_runner
    run.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await registry._run_one(ToolCall("c", "search_knowledge_base", {"query": "q"}), CTX)
    assert record.await_count == 1
    assert record.await_args.args[2].outcome == "cancelled"


async def test_sink_db_en_panne_ne_modifie_pas_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    execute = AsyncMock(side_effect=RuntimeError("synthetic failure"))
    monkeypatch.setattr(runtime_metrics, "execute", execute)
    await runtime_metrics.record_rag("synthetic", "web", RagObservation("found"), 1)
    execute.assert_awaited_once()


async def test_non_rag_tool_ne_pollue_pas_metrics_rag(
    tool_runner: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, record = tool_runner
    monkeypatch.setattr(registry, "_REGISTRY", ())
    await registry._run_one(ToolCall("c", "web_search", {"query": "q"}), CTX)
    record.assert_not_awaited()
