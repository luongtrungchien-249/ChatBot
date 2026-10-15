"""Telemetry never inspects answer/tool text or changes pipeline semantics."""

import asyncio
from dataclasses import asdict
from typing import Any

import pytest

from agents.domain.telemetry import GenerationStats
from agents.pipeline.handle_message import Failed, handle_message
from agents.pipeline.stages.generate import generate
from agents.policy.access import AccessRules
from agents.ports.ratelimit import Denied
from shared.result import Ok

from .fakes import FakeLlm, FakeLogger, FakeRateLimit, FakeTools, answer, make_msg, wants_tools
from .test_handle_message import make_deps
from .test_react_loop import CTX, KB_TOOL, PROMPT
from .test_react_loop import make_deps as react_deps


@pytest.mark.parametrize(
    "replies,over,expected",
    [
        ([answer("secret answer")], {}, GenerationStats("answer", 1, 0, 0)),
        (
            [wants_tools("web_search", "paper_search"), answer("secret")],
            {},
            GenerationStats("answer", 2, 2, 0),
        ),
        (
            [wants_tools("web_search"), answer("secret")],
            {"tools": FakeTools(ok=False)},
            GenerationStats("answer", 2, 1, 1),
        ),
        (
            [answer("secret")],
            {"tools": FakeTools(definitions=(KB_TOOL,))},
            GenerationStats("answer", 2, 0, 0),
        ),
        ([answer("secret")], {"deadline_ms": -1}, GenerationStats("deadline", 0, 0, 0)),
        (
            [answer("secret")],
            {"rate_limit": FakeRateLimit(budget_ok=False)},
            GenerationStats("budget", 0, 0, 0),
        ),
        (
            [wants_tools("web_search", text="partial secret")],
            {"rate_limit": FakeRateLimit(budget_sequence=[True, False])},
            GenerationStats("budget", 1, 1, 0),
        ),
        (
            [wants_tools("web_search", text="partial secret")],
            {"max_iterations": 2},
            GenerationStats("max_iterations", 2, 2, 0),
        ),
        (
            [answer("secret")],
            {"llm": FakeLlm(error=Exception("503"))},
            GenerationStats("error", 1, 0, 0),
        ),
        ([answer("  ")], {}, GenerationStats("error", 1, 0, 0)),
    ],
)
async def test_report_compte_vrais_appels_et_raison_sans_contenu(
    replies: Any, over: Any, expected: GenerationStats
) -> None:
    reports: list[GenerationStats] = []
    deps, _ = react_deps(replies, on_metrics=reports.append, **over)
    await generate(deps, PROMPT, CTX, FakeLogger())
    assert reports == [expected]
    assert set(asdict(reports[0])) == {
        "reason", "iterations", "tool_calls", "tool_errors", "retrieved_chunks"
    }


async def test_user_stop_compte_seulement_les_appels_commences() -> None:
    reports: list[GenerationStats] = []
    stopped = False

    async def stop() -> bool:
        nonlocal stopped
        previous = stopped
        stopped = True
        return previous

    deps, _ = react_deps(
        [wants_tools("web_search", text="partial")], should_stop=stop, on_metrics=reports.append
    )
    await generate(deps, PROMPT, CTX, FakeLogger())
    assert reports == [GenerationStats("user_stopped", 1, 1, 0)]


async def test_cancelled_generation_emet_erreur_et_releve_cancel() -> None:
    reports: list[GenerationStats] = []
    deps, _ = react_deps(
        [answer("secret")],
        llm=FakeLlm(error=asyncio.CancelledError()),
        on_metrics=reports.append,
    )
    with pytest.raises(asyncio.CancelledError):
        await generate(deps, PROMPT, CTX, FakeLogger())
    assert reports == [GenerationStats("error", 1, 0, 0)]


async def test_sink_metrics_en_panne_ne_change_pas_reponse() -> None:
    def broken(_: GenerationStats) -> None:
        raise RuntimeError("sink unavailable")

    deps, _ = react_deps([answer("answer")], on_metrics=broken)
    result = await generate(deps, PROMPT, CTX, FakeLogger())
    assert result == Ok("answer")


@pytest.mark.parametrize("final_attempt,fallback", [(False, False), (True, True)])
async def test_retry_silencieux_n_est_pas_fallback(final_attempt: bool, fallback: bool) -> None:
    class UnavailableError(Exception):
        status_code = 503

    deps = make_deps(llm=FakeLlm(error=UnavailableError()), is_final_attempt=final_attempt)
    result = await handle_message(make_msg(), deps)
    assert isinstance(result, Failed)
    assert result.replied is fallback
    assert result.telemetry.fallback is fallback
    assert result.telemetry.generation == GenerationStats("error", 1, 0, 0)


@pytest.mark.parametrize("warn", [True, False])
async def test_rate_limit_silencieux_et_averti_sont_mesures(warn: bool) -> None:
    deps = make_deps(rate_limit=FakeRateLimit(denied=Denied(1000, "user"), warn_allowed=warn))
    result = await handle_message(make_msg(), deps)
    assert result.replied is warn
    assert result.telemetry.reason == "rate_limited"
    assert result.telemetry.fallback is False
    assert result.telemetry.generation is None


@pytest.mark.parametrize(
    "text,over,reason",
    [
        ("question", {"rate_limit": FakeRateLimit(budget_ok=False)}, "budget"),
        (
            "question",
            {"access_rules": AccessRules("allowlist", "allowlist", frozenset())},
            "ignored_access",
        ),
        ("help", {}, "command"),
        ("question", {}, "answer"),
    ],
)
async def test_pipeline_retourne_raison_et_pas_faux_fallback(
    text: str, over: Any, reason: str
) -> None:
    result = await handle_message(make_msg(text), make_deps(**over))
    assert result.telemetry.reason == reason
    assert result.telemetry.fallback is False


async def test_arret_budget_avec_texte_partiel_est_incomplet_pas_fallback() -> None:
    deps = make_deps(
        llm=FakeLlm(replies=[wants_tools("web_search", text="partial")]),
        tools=FakeTools(),
        rate_limit=FakeRateLimit(budget_sequence=[True, True, False]),
    )
    result = await handle_message(make_msg(), deps)
    assert result.ok and result.replied
    assert result.telemetry.reason == "budget"
    assert result.telemetry.fallback is False
    assert result.telemetry.generation == GenerationStats("budget", 1, 1, 0)
