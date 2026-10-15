from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest

from infra.db import transaction
from main import web_owners


@pytest.fixture
async def isolated_owners(postgres_san_sang: None, monkeypatch: Any) -> AsyncIterator[Any]:
    async with transaction() as connection:
        for table in ("inbound_message", "web_thread_access", "web_thread_generation"):
            await connection.execute(
                f"CREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING ALL) ON COMMIT DROP"
            )
        for thread_id in ("legacy-one", "legacy-two"):
            await connection.execute(
                """INSERT INTO inbound_message
                     (platform,message_id,thread_id,sender_id,sender_name,text,is_group,from_bot)
                   VALUES('web',$1,$1,'old','Old','private test content',false,false)""", thread_id,
            )

        @asynccontextmanager
        async def use_connection() -> AsyncIterator[Any]:
            yield connection

        monkeypatch.setattr(web_owners, "transaction", use_connection)
        yield connection


async def _manifest(connection: Any) -> web_owners.OwnerManifest:
    rows = web_owners._snapshots(await connection.fetch(web_owners._SNAPSHOT_SQL, None))
    return web_owners.OwnerManifest.model_validate({
        "schema_version": 1, "assigned_by": "review-operator", "evidence": "test-only proof",
        "assignments": [{
            "thread_id": row["thread_id"], "user_id": "alice",
            "snapshot_sha256": row["snapshot_sha256"],
        } for row in rows],
    })


async def test_exact_snapshot_assignment_is_audited_and_cannot_overwrite(
    isolated_owners: Any,
) -> None:
    manifest = await _manifest(isolated_owners)
    await web_owners.assign_legacy_owners(manifest, "a" * 64)
    rows = await isolated_owners.fetch("SELECT user_id,owner_assignment FROM web_thread_access")
    assert len(rows) == 2 and all(row["user_id"] == "alice" for row in rows)
    assert all('"manifest_sha256": "' + "a" * 64 in row["owner_assignment"] for row in rows)
    with pytest.raises(ValueError):
        await web_owners.assign_legacy_owners(manifest, "b" * 64)


async def test_one_stale_snapshot_prevents_all_assignments(isolated_owners: Any) -> None:
    manifest = await _manifest(isolated_owners)
    await isolated_owners.execute("DELETE FROM inbound_message WHERE thread_id='legacy-two'")
    with pytest.raises(ValueError):
        await web_owners.assign_legacy_owners(manifest, "a" * 64)
    assert await isolated_owners.fetchval("SELECT count(*) FROM web_thread_access") == 0
