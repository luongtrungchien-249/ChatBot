"""Vong doi du lieu cua mot thread, atomic trong PostgreSQL."""

from agents.domain.thread import ThreadScope
from agents.ports.memory import DeleteMode, DeleteReport
from infra.db import transaction
from infra.thread_lifecycle import lock_web_thread

from .fact_repo import hard_delete_scope


def _count(status: str) -> int:
    return int(status.rsplit(" ", 1)[-1])


async def delete_thread(scope: ThreadScope, mode: DeleteMode) -> DeleteReport:
    """Xoa idempotent theo scope; ``all_data`` xoa them fact vinh vien."""
    async with transaction() as connection:
        await lock_web_thread(connection, scope)
        if scope.platform == "web":
            await connection.execute(
                """INSERT INTO web_thread_generation(thread_id,generation) VALUES($1,1)
                   ON CONFLICT(thread_id) DO UPDATE SET
                   generation=web_thread_generation.generation+1""",
                scope.thread_id,
            )
        facts = await hard_delete_scope(connection, scope) if mode == "all_data" else 0
        summaries = _count(
            await connection.execute(
                "DELETE FROM thread_summary WHERE platform = $1 AND thread_id = $2",
                scope.platform,
                scope.thread_id,
            )
        )
        messages = _count(
            await connection.execute(
                "DELETE FROM inbound_message WHERE platform = $1 AND thread_id = $2",
                scope.platform,
                scope.thread_id,
            )
        )
        metadata = _count(
            await connection.execute(
                "DELETE FROM thread_meta WHERE platform = $1 AND thread_id = $2",
                scope.platform,
                scope.thread_id,
            )
        )
        # Giu ownership sau xoa de request lap van idempotent va thread ID khong
        # bi nguoi khac claim lai (conversation mode van giu fact explicit).
    return DeleteReport(messages, summaries, facts, metadata)
