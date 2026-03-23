from __future__ import annotations

import time
from typing import Optional

import asyncpg

from .core import get_pool
from .users import ensure_user_exists


# =========================
# ADMIN DAYS
# =========================



# =========================
# SAFE ACCESS (ENG MUHIM)
# =========================
async def grant_access(user_id: int, days: int, admin_id: int) -> bool:
    await ensure_user_exists(user_id)

    pool = await get_pool()
    now = int(time.time())

    async with pool.acquire() as conn:
        async with conn.transaction():

            # 🔴 oldin tekshiramiz (double approve oldini oladi)
            exists = await conn.fetchval(
                "SELECT 1 FROM user_access WHERE user_id=$1 AND expires_at > $2",
                user_id,
                now
            )

            if exists:
                return False

            expires_at = now + days * 86400

            # ✅ ACCESS BERISH
            await conn.execute(
                """
                INSERT INTO user_access (user_id, expires_at)
                VALUES ($1, $2)
                ON CONFLICT(user_id) DO UPDATE SET expires_at=$2
                """,
                user_id,
                expires_at
            )

            # ✅ LOG (kim berdi saqlanadi)
            await conn.execute(
                """
                INSERT INTO audit (user_id, admin_id, action, meta, created_at)
                VALUES ($1, $2, 'grant_access', jsonb_build_object('days', $3), $4)
                """,
                user_id,
                admin_id,
                days,
                now
            )

            return True

# =========================
# EXTEND ACCESS
# =========================
async def extend_access(user_id: int, days: int = 30) -> int:
    await ensure_user_exists(user_id)

    pool = await get_pool()
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
            ON CONFLICT(user_id) DO UPDATE SET expires_at=$2
            """,
            user_id,
            new_expires
        )

    return new_expires


# =========================
# CHECK ACCESS
# =========================
async def has_access(user_id: int) -> bool:
    pool = await get_pool()
    now = int(time.time())

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT expires_at FROM user_access WHERE user_id=$1",
            user_id
        )
        return bool(row and int(row["expires_at"]) > now)


# =========================
# COUNT
# =========================
async def count_active_subs() -> int:
    pool = await get_pool()
    now = int(time.time())

    async with pool.acquire() as conn:
        val = await conn.fetchval(
            "SELECT COUNT(*) FROM user_access WHERE expires_at > $1",
            now
        )
        return int(val or 0)


# =========================
# LIST USERS
# =========================
async def list_active_users(limit: int = 50) -> list[asyncpg.Record]:
    pool = await get_pool()
    now = int(time.time())

    async with pool.acquire() as conn:
        return await conn.fetch(
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


async def list_active_user_ids() -> list[int]:
    pool = await get_pool()
    now = int(time.time())

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id FROM user_access WHERE expires_at > $1",
            now
        )
        return [int(r["user_id"]) for r in rows]


async def list_active_users_with_profiles(limit: int = 200) -> list[asyncpg.Record]:
    pool = await get_pool()
    now = int(time.time())

    async with pool.acquire() as conn:
        return await conn.fetch(
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


# =========================
# EXPIRING USERS
# =========================
async def get_expiring_between(start_ts: int, end_ts: int, limit: int = 500):
    pool = await get_pool()

    async with pool.acquire() as conn:
        return await conn.fetch(
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


# =========================
# NOTIFICATIONS
# =========================
async def was_notified(user_id: int, kind: str, expires_at: int) -> bool:
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM access_notifs WHERE user_id=$1 AND kind=$2 AND expires_at=$3",
            user_id,
            kind,
            expires_at
        )
        return bool(row)


async def mark_notified(user_id: int, kind: str, expires_at: int) -> None:
    pool = await get_pool()
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


# =========================
# ACCESS INFO
# =========================
async def get_access_info(user_id: int) -> dict | None:
    pool = await get_pool()
    now = int(time.time())

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT expires_at FROM user_access WHERE user_id=$1",
            user_id
        )

        if not row:
            return None

        exp = int(row["expires_at"])

        return {
            "expires_at": exp,
            "is_active": exp > now,
            "remaining": max(0, exp - now)
        }