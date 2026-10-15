import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from agents.domain.thread import ThreadScope
from infra.ratelimit import rate_limit
from llm.embedder import EmbeddingIdentity
from main import memory_embeddings
from memory.repository import embedding_rebuild as rebuild

from .test_memory_provenance import row

SCOPE = ThreadScope("web", "synthetic-rebuild")
IDENTITY = EmbeddingIdentity("fake", "sha256", 2, "hash-vector-v1")


@pytest.fixture
def setup_rebuild(monkeypatch: Any) -> Any:
    original = row(embedding_provider=None, embedding_model=None,
                   embedding_dim=None, embedding_revision=None, created_by="test")
    rows = [original]
    schema = {"dimension": 2, "audit_ready": True}

    async def fetch(sql: str, *_: Any) -> list[Any]:
        return [schema] if "pg_attribute" in sql else rows

    connection = SimpleNamespace(fetch=AsyncMock(return_value=rows),
                                 execute=AsyncMock(return_value="UPDATE 1"))
    commits: list[str] = []

    @asynccontextmanager
    async def transaction() -> AsyncIterator[Any]:
        try:
            yield connection
        except BaseException:
            commits.append("rollback")
            raise
        else:
            commits.append("commit")

    embed = AsyncMock(return_value=[[1.0, 0.0]])
    monkeypatch.setattr(rebuild, "fetch", fetch)
    monkeypatch.setattr(rebuild, "transaction", transaction)
    monkeypatch.setattr(rebuild, "embedding_identity", lambda: IDENTITY)
    monkeypatch.setattr(rebuild, "get_embedder", lambda: SimpleNamespace(embed=embed))
    monkeypatch.setattr(rebuild, "lock_web_thread", AsyncMock())
    return SimpleNamespace(rows=rows, schema=schema, connection=connection,
                           embed=embed, commits=commits)


def selection(data: Any) -> list[rebuild.FactEmbeddingSelection]:
    snapshot = rebuild._snapshot(data)
    return [rebuild.FactEmbeddingSelection(7, snapshot.subject_id, snapshot.snapshot_sha256)]


async def test_dry_plan_has_no_api_or_write_and_never_outputs_content(setup_rebuild: Any) -> None:
    plan = await rebuild.plan_fact_embedding_rebuild(
        SCOPE, selection(setup_rebuild.rows[0]), IDENTITY,
    )
    assert plan.estimated_cost_upper_usd == 0 and plan.input_bytes > 0
    assert setup_rebuild.rows[0]["content"] not in json.dumps(asdict(plan), ensure_ascii=False)
    setup_rebuild.embed.assert_not_awaited()
    setup_rebuild.connection.execute.assert_not_awaited()


@pytest.mark.parametrize(
    "change", ["missing", "changed", "subject", "schema", "dimension", "bytes"],
)
async def test_invalid_plan_blocks_before_api_or_mutation(setup_rebuild: Any, change: str) -> None:
    chosen = selection(setup_rebuild.rows[0])
    bound = 8000
    if change == "missing":
        setup_rebuild.rows.clear()
    elif change == "changed":
        setup_rebuild.rows[0]["content"] = "new private text"
    elif change == "subject":
        setup_rebuild.rows[0]["subject_id"] = "user:other"
    elif change == "schema":
        setup_rebuild.schema["audit_ready"] = False
    elif change == "dimension":
        setup_rebuild.schema["dimension"] = 1024
    else:
        bound = 1
    with pytest.raises(ValueError):
        await rebuild.rebuild_fact_embeddings(
            SCOPE, chosen, IDENTITY, actor="operator", reason="repair", manifest_sha256="a" * 64,
            max_input_bytes=bound,
        )
    setup_rebuild.embed.assert_not_awaited()
    setup_rebuild.connection.execute.assert_not_awaited()


async def test_concurrent_change_after_api_rolls_back_without_writes(setup_rebuild: Any) -> None:
    chosen = selection(setup_rebuild.rows[0])
    setup_rebuild.connection.fetch.return_value = []
    with pytest.raises(ValueError):
        await rebuild.rebuild_fact_embeddings(
            SCOPE, chosen, IDENTITY, actor="operator", reason="repair", manifest_sha256="a" * 64,
        )
    assert setup_rebuild.embed.await_count == 1
    assert setup_rebuild.commits == ["rollback"]
    assert not any("UPDATE memory_fact" in call.args[0]
                   for call in setup_rebuild.connection.execute.await_args_list)


async def test_paid_rebuild_needs_cost_ceiling_and_live_daily_budget(
    setup_rebuild: Any, monkeypatch: Any,
) -> None:
    paid = EmbeddingIdentity("openai", "text-embedding-3-small", 2, "openai-embedding-v1")
    monkeypatch.setattr(rebuild, "embedding_identity", lambda: paid)
    budget = AsyncMock(return_value=False)
    monkeypatch.setattr(rate_limit, "within_daily_budget", budget)
    chosen = selection(setup_rebuild.rows[0])
    for ceiling in (None, 0.0, 0.01):
        with pytest.raises(ValueError):
            await rebuild.rebuild_fact_embeddings(
                SCOPE, chosen, paid, actor="operator", reason="repair", manifest_sha256="a" * 64,
                max_estimated_usd=ceiling,
            )
    setup_rebuild.embed.assert_not_awaited()
    assert budget.await_count == 1


@pytest.mark.parametrize("vectors", [[[float("nan"), 0.0]], [[0.0, 0.0]], [], [[1.0]]])
async def test_bad_provider_vectors_never_enter_transaction(
    setup_rebuild: Any, vectors: list[list[float]],
) -> None:
    setup_rebuild.embed.return_value = vectors
    with pytest.raises(ValueError):
        await rebuild.rebuild_fact_embeddings(
            SCOPE, selection(setup_rebuild.rows[0]), IDENTITY,
            actor="operator", reason="repair", manifest_sha256="a" * 64,
        )
    assert setup_rebuild.commits == []


async def test_cli_default_is_dry_run_and_hides_failure_values(
    tmp_path: Path, monkeypatch: Any, capsys: Any,
) -> None:
    manifest = tmp_path / "rebuild.json"
    manifest.write_text(json.dumps({
        "schema_version": 1, "actor": "operator", "reason": "repair", "scope": asdict(SCOPE),
        "target_identity": asdict(IDENTITY),
        "facts": [{"fact_id": 7, "subject_id": "user:nam", "snapshot_sha256": "a" * 64}],
    }), encoding="utf-8")
    plan = rebuild.FactRebuildPlan(IDENTITY, (), 0, 0)
    dry = AsyncMock(return_value=plan)
    apply = AsyncMock(side_effect=RuntimeError("private content sk-secret"))
    monkeypatch.setattr(memory_embeddings, "plan_fact_embedding_rebuild", dry)
    monkeypatch.setattr(memory_embeddings, "rebuild_fact_embeddings", apply)
    assert await memory_embeddings.memory_embeddings_command([
        "rebuild", "--manifest", str(manifest),
    ]) == 0
    apply.assert_not_awaited()
    assert json.loads(capsys.readouterr().out)["action"] == "dry_run"
    assert await memory_embeddings.memory_embeddings_command([
        "rebuild", "--manifest", str(manifest), "--apply",
    ]) == 1
    assert "sk-secret" not in capsys.readouterr().out
