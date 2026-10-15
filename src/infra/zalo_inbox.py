"""Durable pending receipts; PostgreSQL outbox is replayed before the next poll."""

import asyncio
import json

from agents.domain.message import InboundMessage

from .db import execute, transaction
from .queue import enqueue_reply, from_payload, to_payload


async def save_receipt(msg: InboundMessage) -> None:
    if msg.platform != "zalo_bot":
        raise ValueError("inbox only accepts zalo_bot messages")
    await execute(
        """INSERT INTO zalo_inbox(message_id,payload) VALUES($1,$2::jsonb)
           ON CONFLICT(message_id) DO NOTHING""",
        msg.message_id,
        json.dumps(to_payload(msg)),
    )


async def replay_pending(limit: int = 100) -> int:
    if not 1 <= limit <= 100:
        raise ValueError("inbox replay limit must be between 1 and 100")
    # Row locks prevent concurrent replay; a crash after enqueue but before commit
    # replays the same stable ARQ job ID, which remains deduplicated by the queue.
    async with transaction() as connection:
        rows = await connection.fetch(
            """SELECT message_id,payload FROM zalo_inbox WHERE queued_at IS NULL
               ORDER BY received_at,message_id LIMIT $1 FOR UPDATE SKIP LOCKED""",
            limit,
        )
        for row in rows:
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            # Do not hold database locks indefinitely when Redis is unavailable.
            async with asyncio.timeout(30):
                await enqueue_reply(from_payload(payload))
            await connection.execute(
                "UPDATE zalo_inbox SET payload=NULL,queued_at=now() WHERE message_id=$1",
                row["message_id"],
            )
    return len(rows)
