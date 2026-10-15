"""Composition service cho xoa thread: PostgreSQL truoc, Redis sau."""

from agents.domain.thread import ThreadScope
from agents.ports.memory import DeleteMode, DeleteReport
from infra.logger import get_logger
from infra.redis_client import aw, get_redis
from memory.repository.thread_repo import delete_thread

_log = get_logger()


def _glob_literal(value: str) -> str:
    return "".join("\\" + char if char in "\\*?[]" else char for char in value)


async def delete_thread_data(scope: ThreadScope, mode: DeleteMode) -> DeleteReport:
    report = await delete_thread(scope, mode)
    try:
        redis = get_redis()
        keys = [
            f"ctx:{scope.platform}:{scope.thread_id}",
            f"cancel:{scope.platform}:{scope.thread_id}",
        ]
        if scope.platform == "web":
            keys.append(f"web:final:{scope.thread_id}")
        prefix = _glob_literal(f"forget:{scope.platform}:{scope.thread_id}:")
        async for key in redis.scan_iter(match=prefix + "*"):
            # redis-py tra ``bytes`` khi decode_responses khong bat. Giu nguyen
            # gia tri; ``str(b"key")`` se tao "b'key'" va xoa nham mot key khac.
            keys.append(key)
        await aw(redis.delete(*keys))
    except Exception as error:
        _log.warning("Postgres da xoa nhung Redis chua don duoc", err=type(error).__name__)
    return report
