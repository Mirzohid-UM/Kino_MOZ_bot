# db/broadcast.py
from __future__ import annotations

import time
from typing import List
from .core import get_pool


async def list_all_users() -> List[int]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id FROM users WHERE is_blocked = FALSE"
        )
        return [int(r["user_id"]) for r in rows]


async def list_unsubscribed_users() -> List[int]:
    pool = get_pool()
    now = int(time.time())

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT u.user_id
            FROM users u
            LEFT JOIN user_access ua ON u.user_id = ua.user_id
            WHERE (ua.expires_at IS NULL OR ua.expires_at <= $1)
            AND u.is_blocked = FALSE
            """,
            now
        )
        return [int(r["user_id"]) for r in rows]


async def set_user_blocked(user_id: int) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET is_blocked = TRUE WHERE user_id=$1",
            user_id
        )