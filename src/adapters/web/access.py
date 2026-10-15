"""Ownership cho Web thread; thread cu khong owner khong duoc tu dong claim."""

from agents.domain.thread import ThreadScope
from infra.db import fetch, transaction


async def is_owner(scope: ThreadScope, user_id: str) -> bool:
    rows = await fetch(
        "SELECT 1 FROM web_thread_access WHERE thread_id=$1 AND user_id=$2",
        scope.thread_id,
        user_id,
    )
    return bool(rows)


async def claim_new_or_check_owner(scope: ThreadScope, user_id: str) -> bool:
    """Claim atomically only when thread has neither owner nor existing messages."""
    async with transaction() as connection:
        await connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended($1, 0))",
            f"web:{scope.thread_id}",
        )
        rows = await connection.fetch(
            "SELECT user_id FROM web_thread_access WHERE thread_id=$1 FOR UPDATE",
            scope.thread_id,
        )
        if rows:
            return str(rows[0]["user_id"]) == user_id
        existing = await connection.fetchval(
            "SELECT EXISTS(SELECT 1 FROM inbound_message WHERE platform='web' AND thread_id=$1)",
            scope.thread_id,
        )
        if existing:
            return False
        await connection.execute(
            "INSERT INTO web_thread_access(thread_id,user_id) VALUES($1,$2)",
            scope.thread_id,
            user_id,
        )
        return True
