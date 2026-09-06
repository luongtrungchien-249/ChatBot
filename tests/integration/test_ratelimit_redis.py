"""Token bucket chay tren REDIS THAT.

Unit test khong chung minh duoc gi ve doan Lua: no la mot chuoi, va mot chuoi sai
cu phap van "chay" cho toi khi Redis tu choi no. Cac test o day goi that.

Tu bo qua khi khong co Redis (CI hien chua dung Docker), nhung KHONG duoc bo qua
im lang: dong skip co neu ly do.

Chay: docker compose -f ops/docker-compose.yml up -d redis && uv run pytest tests/integration
"""

import time
import uuid
from collections.abc import AsyncIterator
from typing import Any, cast

import pytest

from agents.domain.thread import ThreadScope
from agents.ports.ratelimit import Allowed, Denied
from infra.ratelimit import _BUCKET_SCRIPT, RedisRateLimit, bucket_args
from infra.redis_client import aw, get_redis


@pytest.fixture
async def redis_san_sang() -> AsyncIterator[None]:
    try:
        await aw(get_redis().ping())
    except Exception as error:
        pytest.skip(f"khong co Redis: {error}")
    yield


def scope_moi() -> ThreadScope:
    """Moi test mot thread rieng — bucket khong dinh sang nhau giua cac lan chay."""
    return ThreadScope(platform="cli", thread_id=f"it-{uuid.uuid4()}")


def nguoi_moi() -> str:
    """Moi test mot sender_id rieng.

    BAT BUOC, khong phai cho gon: khoa cua tang user la
    `rl:u:{platform}:{sender_id}` — KHONG kem thread_id. Nghia la han muc cua mot
    nguoi di theo ho qua moi thread (dung thiet ke, xem section 6.5), nen dung lai
    mot sender_id giua cac test se lam test sau ke thua bucket da can cua test truoc.
    Da troi that mot lan khi viet bo test nay.
    """
    return f"u-{uuid.uuid4()}"


async def goi(scope: ThreadScope, sender_id: str, user_cap: int, thread_cap: int) -> object:
    """Goi thang script, khong qua get_settings() — de khoi phai sua .env khi test."""
    raw = await aw(
        get_redis().eval(
            _BUCKET_SCRIPT,
            2,
            f"rl:u:{scope.platform}:{sender_id}",
            f"rl:t:{scope.platform}:{scope.thread_id}",
            *bucket_args(user_cap, thread_cap, int(time.time() * 1000)),
        )
    )
    result = cast(list[Any], raw)
    if int(result[0]) == 0:
        return Allowed()
    return Denied(retry_after_ms=int(result[1]), tier=cast(Any, str(result[2])))


@pytest.mark.usefixtures("redis_san_sang")
class TestTokenBucket:
    async def test_cho_qua_dung_capacity_lan_roi_chan(self) -> None:
        scope, toi = scope_moi(), nguoi_moi()
        for i in range(3):
            assert isinstance(await goi(scope, toi, 3, 100), Allowed), f"luot {i + 1}"

        verdict = await goi(scope, toi, 3, 100)
        assert isinstance(verdict, Denied)
        assert verdict.tier == "user"

    async def test_bao_dung_tang_bi_cham_tran(self) -> None:
        scope = scope_moi()
        # Tran thread thap hon tran user: hai NGUOI KHAC NHAU cung dot tran thread.
        assert isinstance(await goi(scope, nguoi_moi(), 100, 2), Allowed)
        assert isinstance(await goi(scope, nguoi_moi(), 100, 2), Allowed)

        verdict = await goi(scope, nguoi_moi(), 100, 2)
        assert isinstance(verdict, Denied)
        assert verdict.tier == "thread"

    async def test_het_tran_thread_thi_KHONG_tru_luot_cua_user(self) -> None:
        """Day la ly do hai tang nam trong MOT script.

        Goi rieng tung tang thi khi thread het luot, luot cua nguoi dung DA bi tru
        mat cho mot cau bot khong tra loi — ho bi phat vi loi cua nguoi khac.
        """
        scope, toi = scope_moi(), nguoi_moi()
        await goi(scope, nguoi_moi(), 5, 1)  # nguoi khac dot sach tran thread

        assert isinstance(await goi(scope, toi, 5, 1), Denied)

        # Sang mot thread khac, 'toi' phai con NGUYEN ca 5 luot.
        khac = scope_moi()
        for i in range(5):
            assert isinstance(await goi(khac, toi, 5, 100), Allowed), f"luot {i + 1}"

    async def test_retry_after_duong_va_hop_ly(self) -> None:
        scope, toi = scope_moi(), nguoi_moi()
        await goi(scope, toi, 1, 100)

        verdict = await goi(scope, toi, 1, 100)
        assert isinstance(verdict, Denied)
        # 1 token/phut -> cho gan mot phut de co lai mot token.
        assert 0 < verdict.retry_after_ms <= 60_000

    async def test_khoa_co_TTL_khong_song_mai(self) -> None:
        """Thieu TTL thi Redis phinh theo so nguoi dung va khong bao gio co lai."""
        scope, toi = scope_moi(), nguoi_moi()
        await goi(scope, toi, 10, 30)

        ttl = await aw(get_redis().pttl(f"rl:u:{scope.platform}:{toi}"))
        assert isinstance(ttl, int) and ttl > 0

    async def test_moi_nen_tang_mot_bucket_rieng(self) -> None:
        # Khoa gom ca platform: cung mot thread_id o Zalo va o web la hai cho khac
        # nhau, khong duoc dung chung han muc.
        trung = f"trung-{uuid.uuid4()}"
        a = ThreadScope(platform="cli", thread_id=trung)
        b = ThreadScope(platform="web", thread_id=trung)
        await goi(a, nguoi_moi(), 100, 1)

        assert isinstance(await goi(b, nguoi_moi(), 100, 1), Allowed)

    async def test_han_muc_cua_mot_NGUOI_di_theo_ho_qua_moi_thread(self) -> None:
        """Dung thiet ke, khong phai lo: khoa tang user khong kem thread_id.

        Neu tinh rieng theo tung thread thi mot nguoi chi can mo hai nhom la nhan
        doi han muc — tran 10/phut tro thanh vo nghia.
        """
        toi = nguoi_moi()
        assert isinstance(await goi(scope_moi(), toi, 1, 100), Allowed)

        # Thread khac, van con nguoi do: het luot.
        assert isinstance(await goi(scope_moi(), toi, 1, 100), Denied)


@pytest.mark.usefixtures("redis_san_sang")
class TestCoCanhBao:
    async def test_lan_dau_duoc_nhac_lan_hai_thi_khong(self) -> None:
        scope = scope_moi()
        limiter = RedisRateLimit()

        assert await limiter.should_warn(scope) is True
        assert await limiter.should_warn(scope) is False

    async def test_moi_thread_mot_co_rieng(self) -> None:
        limiter = RedisRateLimit()
        assert await limiter.should_warn(scope_moi()) is True
        assert await limiter.should_warn(scope_moi()) is True
