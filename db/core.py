from __future__ import annotations

import os
import logging
from typing import Optional
import asyncpg

logger = logging.getLogger(__name__)

_pool: Optional[asyncpg.Pool] = None


def _dsn() -> str:
    dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set")

    # railway sometimes gives postgres://
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://"):]

    return dsn


async def init_pool(
    dsn: str | None = None,
    min_size: int = 1,
    max_size: int = 10,
):
    global _pool

    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=dsn or _dsn(),
            min_size=min_size,
            max_size=max_size,
            command_timeout=30,
        )
        logger.info("asyncpg pool initialized")

    return _pool


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized. Call init_pool() on startup.")
    return _pool