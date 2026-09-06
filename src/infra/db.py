"""Mot noi duy nhat mo ket noi Postgres.

Postgres la NGUON THAT cho L1/L2/L3/L4; Redis chi la cache doc
(xem ARCHITECTURE.md section 6.1).
"""

# asyncpg.Pool chi generic voi type checker, KHONG subscript duoc luc chay:
# `asyncpg.Pool[Any]` nem TypeError ngay khi import. Future import nay bien moi
# annotation thanh chuoi nen mypy van doc duoc ma runtime khong danh gia.
from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg

from config import get_settings

from .logger import get_logger

_pool: asyncpg.Pool[Any] | None = None
_log = get_logger()


async def get_pool() -> asyncpg.Pool[Any]:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=get_settings().DATABASE_URL,
            min_size=1,
            max_size=10,
            # Chan cau truy van chay mai. Vector search hong van phai tra loi trong
            # ngan sach latency.
            command_timeout=10.0,
        )
        assert _pool is not None
    return _pool


async def fetch(sql: str, *args: Any) -> list[Any]:
    """L6: moi loi goi ra ngoai co log va do thoi gian.

    Khong biet cai gi cham thi khong toi uu duoc cai gi.
    """
    pool = await get_pool()
    started = time.monotonic()
    try:
        rows: list[Any] = await pool.fetch(sql, *args)
        _log.debug("sql", ms=int((time.monotonic() - started) * 1000), rows=len(rows))
        return rows
    except Exception as error:
        _log.error(
            "sql loi", ms=int((time.monotonic() - started) * 1000), sql=sql, err=str(error)
        )
        raise


async def execute(sql: str, *args: Any) -> str:
    pool = await get_pool()
    started = time.monotonic()
    try:
        status: str = await pool.execute(sql, *args)
        _log.debug("sql", ms=int((time.monotonic() - started) * 1000))
        return status
    except Exception as error:
        _log.error(
            "sql loi", ms=int((time.monotonic() - started) * 1000), sql=sql, err=str(error)
        )
        raise


@asynccontextmanager
async def transaction() -> AsyncIterator[Any]:
    """Chay nhieu cau trong MOT transaction.

    Dung cho migrate: hong giua chung thi khong de lai nua vet.
    """
    pool = await get_pool()
    async with pool.acquire() as connection, connection.transaction():
        yield connection


async def close_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
