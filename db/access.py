# db/access.py
from __future__ import annotations

import time
from typing import Any, Sequence

import asyncpg

from .core import get_pool    # <-- endi pool qaytaradi deb faraz qilamiz
from .users import ensure_user_exists


async def grant_access(user_id: int, days: int = 1) -> None:
    await ensure_user_exists(user_id)   # agar bu ham async bo'lsa

    pool = get_pool()
    expires_at = int(time.time()) + days * 86400

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_access (user_id, expires_at)
            VALUES ($1, $2)
            ON CONFLICT(user_id) DO UPDATE SET expires_at=EXCLUDED.expires_at
            """,
            user_id,
            expires_at
        )


async def extend_access(user_id: int, days: int = 30) -> int:
    await ensure_user_exists(user_id)

    pool = get_pool()
    now = int(time.time())

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT expires_at FROM user_access WHERE user_id=$1",
            user_id
        )

        base = int(row["expires_at"]) if row and int(row["expires_at"]) > now else now
        new_expires = base + days * 86400

        await conn.execute(
            """
            INSERT INTO user_access (user_id, expires_at)
            VALUES ($1, $2)
            ON CONFLICT(user_id) DO UPDATE SET expires_at=EXCLUDED.expires_at
            """,
            user_id,
            new_expires
        )

        return new_expires


async def has_access(user_id: int) -> bool:
    pool = get_pool()
    now = int(time.time())

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT expires_at FROM user_access WHERE user_id=$1",
            user_id
        )
        return bool(row and int(row["expires_at"]) > now)


async def count_active_subs() -> int:
    pool = get_pool()
    now = int(time.time())

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT COUNT(*) AS cnt FROM user_access WHERE expires_at > $1",
            now
        )
        return int(row["cnt"])


async def list_active_users(limit: int = 50) -> list[asyncpg.Record]:
    pool = get_pool()
    now = int(time.time())

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT user_id, expires_at
            FROM user_access
            WHERE expires_at > $1
            ORDER BY expires_at ASC
            LIMIT $2
            """,
            now,
            limit
        )
        return rows


async def list_active_user_ids() -> list[int]:
    pool = get_pool()
    now = int(time.time())

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id FROM user_access WHERE expires_at > $1",
            now
        )
        return [int(r["user_id"]) for r in rows]


async def list_active_users_with_profiles(limit: int = 200) -> list[asyncpg.Record]:
    pool = get_pool()
    now = int(time.time())

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ua.user_id, ua.expires_at, u.username, u.full_name
            FROM user_access ua
            LEFT JOIN users u ON u.user_id = ua.user_id
            WHERE ua.expires_at > $1
            ORDER BY ua.expires_at ASC
            LIMIT $2
            """,
            now,
            limit
        )
        return rows


async def get_expiring_between(
    start_ts: int,
    end_ts: int,
    limit: int = 500
) -> list[asyncpg.Record]:
    pool = get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ua.user_id, ua.expires_at, u.username, u.full_name
            FROM user_access ua
            LEFT JOIN users u ON u.user_id = ua.user_id
            WHERE ua.expires_at >= $1 AND ua.expires_at < $2
            ORDER BY ua.expires_at ASC
            LIMIT $3
            """,
            start_ts,
            end_ts,
            limit
        )
        return rows


async def was_notified(user_id: int, kind: str, expires_at: int) -> bool:
    pool = get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM access_notifs WHERE user_id=$1 AND kind=$2 AND expires_at=$3",
            user_id,
            kind,
            expires_at
        )
        return bool(row)


async def mark_notified(user_id: int, kind: str, expires_at: int) -> None:
    pool = get_pool()
    sent_at = int(time.time())

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO access_notifs (user_id, kind, expires_at, sent_at)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, kind, expires_at) DO NOTHING
            """,
            user_id,
            kind,
            expires_at,
            sent_at
        )

