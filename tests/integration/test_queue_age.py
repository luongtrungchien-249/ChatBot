import time
import uuid

from arq.constants import job_key_prefix
from arq.jobs import serialize_job

from infra.queue import get_queue
from infra.queue_metrics import queue_age


async def test_deferred_score_does_not_reset_original_age(redis_san_sang: None) -> None:
    redis = await get_queue()
    identifier = "synthetic-age-" + uuid.uuid4().hex
    queue_name = "synthetic-queue-" + uuid.uuid4().hex
    key = job_key_prefix + identifier
    try:
        job = await redis.enqueue_job(
            "synthetic", _job_id=identifier, _queue_name=queue_name, _defer_by=3600
        )
        assert job is not None
        await redis.set(
            key, serialize_job("synthetic", (), {}, 1, int((time.time() - 600) * 1000)), ex=3600
        )
        age = await queue_age(queue_name)
        assert age.complete and age.oldest_seconds is not None
        assert 600 <= age.oldest_seconds < 610
    finally:
        await redis.delete(queue_name, key)
