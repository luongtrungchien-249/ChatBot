"""Stage 4 — rate limit ba tang.

Cai de sai nhat khong phai viec CHAN, ma la viec BAO. Mot nguoi spam 100 tin ma
nhan 100 cau "cham lai" thi bot da tu bien thanh ke spam nhom — dung cai lam nguoi
ta kick no ra. Nen phan lon test o day noi ve im lang.
"""

from typing import Any

import pytest

from agents.domain.thread import ThreadScope
from agents.pipeline.handle_message import Handled, handle_message
from agents.pipeline.stages.ratelimit import (
    RATE_LIMITED_TEXT,
    Pass,
    Silent,
    Warn,
    check_rate_limit,
)
from agents.ports.ratelimit import Denied

from .fakes import FakeRateLimit
from .test_handle_message import make_deps

SCOPE = ThreadScope(platform="cli", thread_id="t1")
DENIED_USER = Denied(retry_after_ms=4_500, tier="user")


class TestStage:
    async def test_con_luot_thi_di_tiep(self) -> None:
        assert isinstance(await check_rate_limit(FakeRateLimit(), SCOPE, "u1"), Pass)

    async def test_het_luot_va_chua_nhac_thi_Warn(self) -> None:
        limit = FakeRateLimit(denied=DENIED_USER, warn_allowed=True)

        outcome = await check_rate_limit(limit, SCOPE, "u1")

        assert outcome == Warn(tier="user", retry_after_ms=4_500)

    async def test_het_luot_va_DA_nhac_roi_thi_Silent(self) -> None:
        limit = FakeRateLimit(denied=DENIED_USER, warn_allowed=False)

        outcome = await check_rate_limit(limit, SCOPE, "u1")

        assert outcome == Silent(tier="user", retry_after_ms=4_500)

    async def test_KHONG_hoi_cooldown_khi_van_con_luot(self) -> None:
        # Goi Redis mot lan vo ich o moi tin nhan binh thuong la lang phi ngay
        # tren duong phan hoi.
        limit = FakeRateLimit()

        await check_rate_limit(limit, SCOPE, "u1")

        assert limit.warn_calls == 0


class TestTrongDuongOng:
    def _deps(self, **over: Any) -> Any:
        return make_deps(rate_limit=FakeRateLimit(**over))

    async def test_bi_chan_lan_dau_thi_nhac_MOT_cau_ngan(self) -> None:
        deps = self._deps(denied=DENIED_USER, warn_allowed=True)

        result = await handle_message_(deps)

        assert result == Handled(replied=True)
        assert deps.channel.sent == [RATE_LIMITED_TEXT]

    async def test_bi_chan_lan_sau_thi_IM_LANG(self) -> None:
        deps = self._deps(denied=DENIED_USER, warn_allowed=False)

        result = await handle_message_(deps)

        assert result == Handled(replied=False)
        assert deps.channel.sent == []

    async def test_bi_chan_thi_KHONG_goi_model(self) -> None:
        # Ca diem cua rate limit la khong tieu tien cho tin bi chan.
        deps = self._deps(denied=DENIED_USER)

        await handle_message_(deps)

        assert deps.llm.calls == []

    async def test_bi_chan_thi_KHONG_ghi_vao_lich_su(self) -> None:
        # Ghi tin bi chan se lam nhieu hoi thoai bang nhung cau bot khong he tra loi,
        # va sau nay L2 se tom tat ca dong spam do.
        deps = self._deps(denied=DENIED_USER)

        await handle_message_(deps)

        assert deps.memory.appended == []

    async def test_bi_chan_thi_KHONG_cham_toi_budget_guard(self) -> None:
        # Thu tu stage: 4 ratelimit -> 5 budget. Dao lai la moi tin spam deu ton
        # mot lan doc Redis cua chot chan ngan sach.
        deps = self._deps(denied=DENIED_USER)

        await handle_message_(deps)

        assert deps.rate_limit.budget_calls == 0

    @pytest.mark.parametrize("tier", ["user", "thread"])
    async def test_chan_o_tang_nao_cung_cho_ra_cung_mot_cau(self, tier: str) -> None:
        # Nguoi dung khong can biet ho cham tran nao. Noi ra chi giup nguoi muon
        # lach biet phai doi bao lau va o dau.
        deps = self._deps(denied=Denied(retry_after_ms=1_000, tier=tier))  # type: ignore[arg-type]

        await handle_message_(deps)

        assert deps.channel.sent == [RATE_LIMITED_TEXT]

    async def test_cau_nhac_khong_noi_ra_con_so(self) -> None:
        assert "phút" not in RATE_LIMITED_TEXT
        assert not any(c.isdigit() for c in RATE_LIMITED_TEXT)


async def handle_message_(deps: Any) -> Any:
    from .fakes import make_msg

    return await handle_message(make_msg(), deps)
