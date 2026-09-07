"""Vong doi ket noi dung chung + dieu kien tien quyet cua test tich hop.

VAN DE DA GAP (vong doi): fixture cua tung file goi `close_db()` khi teardown, trong
khi `infra/db.py` giu pool o bien TOAN CUC va pytest-asyncio tao event loop MOI cho
moi test. Ba thu do cong lai thanh mot cuoc dua lam test do lac loi. Cach sua: MOT
event loop cho ca lan chay (asyncio_default_*_loop_scope trong pyproject.toml), pool
tao mot lan, dong dung mot lan o day.

VAN DE DA GAP (bo qua im lang): 40 test — trong do co CA BAY test cross-thread-leak —
tu bo qua khi khong co Postgres/Redis. Tren CI dieu do co nghia chung KHONG BAO GIO
CHAY, ma bao cao van mau xanh. Mot bo test bao mat chet dung theo cach do: khong ai
xoa no, no chi lang le thoi chay.

Nen o day "bo qua" co hai nghia khac nhau:
  - May ban: bo qua. Khong ai phai bat Docker de sua mot dong docstring.
  - CI (bien CI=true, GitHub Actions tu dat): DO.
"""

import os
from collections.abc import AsyncIterator
from typing import NoReturn

import pytest

from config import get_settings
from infra.db import close_db, fetch
from infra.redis_client import aw, close_redis, get_redis


def _thieu_dieu_kien(ly_do: str, *, bat_buoc_tren_ci: bool = True) -> NoReturn:
    """`bat_buoc_tren_ci=False` cho thu ma repo co the CO Y khong cau hinh.

    Postgres va Redis do chinh workflow dung len, nen thieu chung la loi cau hinh CI
    -> DO. Con khoa OpenAI phai do chu repo tu them vao Secrets; khong co no la mot
    lua chon hop le, nhung phai KEU TO chu khong duoc lang le xanh.
    """
    if os.getenv("CI"):
        if bat_buoc_tren_ci:
            pytest.fail(
                f"CI BAT BUOC phai chay test nay nhung thieu dieu kien: {ly_do}. "
                "Xem khoi `services:` va `env:` trong .github/workflows/ci.yml."
            )
        # Chu thich cua GitHub Actions — hien tren tab Summary, khong chim trong log.
        print(f"::warning title=Test bao mat KHONG chay::{ly_do}")
    pytest.skip(f"{ly_do} — bo qua o may local, nhung CI se DO neu thieu")


@pytest.fixture(scope="session", autouse=True)
async def dong_ket_noi_cuoi_cung() -> AsyncIterator[None]:
    yield
    # Con treo mot pool Postgres la process test khong bao gio thoat.
    await close_db()
    await close_redis()


@pytest.fixture
async def postgres_san_sang() -> None:
    try:
        await fetch("SELECT 1")
    except Exception as error:
        _thieu_dieu_kien(f"khong co Postgres ({error})")


@pytest.fixture
async def redis_san_sang() -> None:
    try:
        await aw(get_redis().ping())
    except Exception as error:
        _thieu_dieu_kien(f"khong co Redis ({error})")


@pytest.fixture
async def embedding_that(postgres_san_sang: None) -> None:
    """Embedder gia sinh vector tu hash — moi khoang cach cosine deu vo nghia.

    Chong trung, phat hien mau thuan va tim theo y nghia deu dua tren khoang cach do,
    nen chay chung voi embedder gia la tu lua: test xanh ma khong chung minh gi.
    """
    if get_settings().EMBEDDING_PROVIDER.lower() != "openai":
        _thieu_dieu_kien(
            "EMBEDDING_PROVIDER khong phai 'openai' — 23 test (16 fact_repo + 7 "
            "cross-thread-leak) khong duoc bao ve. Them OPENAI_API_KEY vao repo "
            "Secrets de bat chung len.",
            bat_buoc_tren_ci=False,
        )
