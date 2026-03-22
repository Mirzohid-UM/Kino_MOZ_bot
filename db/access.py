# db/access.py
from __future__ import annotations

import time
from typing import Any, Sequence

import asyncpg

from .core import get_pool    # <-- endi pool qaytaradi deb faraz qilamiz
from .users import ensure_user_exists

from typing import Optional

# Har bir admin uchun kun balansini boshqarish funksiyasi (misol)
async def decrement_admin_days(admin_id: int, days: int) -> None:
    """
    Adminning kun balansini kamaytiradi.
    Agar balans jadvalda bo'lmasa, uni 0 deb qabul qiladi.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO admin_days (admin_id, remaining_days)
            VALUES ($1, GREATEST(0, $2))
            ON CONFLICT(admin_id) DO UPDATE 
            SET remaining_days = GREATEST(0, admin_days.remaining_days - $2)
            """,
            admin_id,
            days
        )


async def grant_access(user_id: int, days: int = 1, admins: Optional[list[int]] = None) -> int:
    """
    Foydalanuvchiga ruxsat beradi va agar admins berilgan bo'lsa,
    ularning kunlarini ham avtomatik kamaytiradi.
    Qaytaradi: expires_at timestamp
    """
    await ensure_user_exists(user_id)
    now = int(time.time())
    expires_at = now + days * 86400

    # Adminlar kunlarini kamaytirish
    if admins:
        for admin_id in admins:
            await decrement_admin_days(admin_id, days)

    pool = get_pool()
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
    return expires_at


async def extend_access(user_id: int, days: int = 30) -> int:
    """
    Foydalanuvchi obunasini uzaytiradi.
    Qaytaradi: yangi expires_at timestamp
    """
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
    """
    Foydalanuvchida aktiv obuna mavjudligini tekshiradi
    """
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

async def get_access_info(user_id: int) -> dict | None:
    pool = get_pool()
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