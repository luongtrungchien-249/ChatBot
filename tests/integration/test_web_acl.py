import asyncio
import uuid

from adapters.web.access import claim_new_or_check_owner, is_owner
from agents.domain.thread import ThreadScope
from infra.db import execute
from memory.repository.thread_repo import delete_thread


async def test_thread_moi_chi_mot_user_claim_duoc(postgres_san_sang: None) -> None:
    scope = ThreadScope("web", f"acl-{uuid.uuid4().hex}")

    assert await claim_new_or_check_owner(scope, "user-a")
    assert await claim_new_or_check_owner(scope, "user-a")
    assert not await claim_new_or_check_owner(scope, "user-b")
    assert await is_owner(scope, "user-a")
    assert not await is_owner(scope, "user-b")

    await execute("DELETE FROM web_thread_access WHERE thread_id=$1", scope.thread_id)


async def test_claim_dong_thoi_chi_mot_owner_va_xoa_khong_cho_chiem_lai(
    postgres_san_sang: None,
) -> None:
    scope = ThreadScope("web", f"race-{uuid.uuid4().hex}")
    results = await asyncio.gather(
        claim_new_or_check_owner(scope, "a"), claim_new_or_check_owner(scope, "b")
    )
    assert sum(results) == 1
    winner, loser = ("a", "b") if results[0] else ("b", "a")
    for mode in ("conversation", "all_data"):
        await delete_thread(scope, mode)
        assert await is_owner(scope, winner)
        assert not await claim_new_or_check_owner(scope, loser)
    await execute("DELETE FROM web_thread_access WHERE thread_id=$1", scope.thread_id)


async def test_thread_cu_khong_owner_khong_duoc_tu_dong_chiem(
    postgres_san_sang: None,
) -> None:
    scope = ThreadScope("web", f"legacy-{uuid.uuid4().hex}")
    await execute(
        """INSERT INTO inbound_message
             (platform,message_id,thread_id,sender_id,sender_name,text,is_group,from_bot)
           VALUES('web',$1,$2,'legacy','Legacy','secret',false,false)""",
        uuid.uuid4().hex,
        scope.thread_id,
    )

    assert not await claim_new_or_check_owner(scope, "user-a")
    assert not await is_owner(scope, "user-a")

    await execute(
        "DELETE FROM inbound_message WHERE platform='web' AND thread_id=$1", scope.thread_id
    )
