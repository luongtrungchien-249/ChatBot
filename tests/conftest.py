"""Vong doi ket noi dung chung cho toan bo lan chay test.

VAN DE DA GAP: cac fixture cua tung file goi `close_db()` khi teardown, trong khi
`infra/db.py` giu pool o mot bien TOAN CUC va pytest-asyncio tao mot event loop MOI
cho moi test. Ba thu do cong lai thanh mot cuoc dua:

  - Test A tao pool trong loop A. Test B chay trong loop B nhung dung lai pool cu.
  - Teardown cua test A dong pool trong khi test B dang cam no.

Trieu chung khong on dinh va rat de bi coi thuong: mot test do lac loi trong mot lan
chay, va mot fixture "skip vi khong co Postgres" trong khi Postgres van chay. Lan do
dau tien roi trung vao mot test BAO MAT — do la loai flake nguy hiem nhat, vi no day
nguoi ta toi thoi quen bo qua test bao mat.

Cach sua: MOT event loop cho ca lan chay (xem asyncio_default_*_loop_scope trong
pyproject.toml), pool tao mot lan, va chi dong dung mot lan o day khi moi thu da xong.
"""

from collections.abc import AsyncIterator

import pytest

from infra.db import close_db
from infra.redis_client import close_redis


@pytest.fixture(scope="session", autouse=True)
async def dong_ket_noi_cuoi_cung() -> AsyncIterator[None]:
    yield
    # Con treo mot pool Postgres la process test khong bao gio thoat.
    await close_db()
    await close_redis()
