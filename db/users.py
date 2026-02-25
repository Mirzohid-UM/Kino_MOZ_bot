# db/users.py
from __future__ import annotations
import time
from db.core import get_pool

async def upsert_user(user_id: int, username: str | None, full_name: str | None) -> None:
    now = int(time.time())
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, username, full_name, joined_at, last_seen)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id) DO UPDATE SET
              username  = COALESCE(EXCLUDED.username, users.username),
              full_name = COALESCE(EXCLUDED.full_name, users.full_name),
              last_seen = EXCLUDED.last_seen
            """,
            int(user_id), username, full_name, now, now
        )

async def ensure_user_exists(user_id: int) -> None:
    now = int(time.time())
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (user_id, username, full_name, joined_at, last_seen)
            VALUES ($1, NULL, NULL, $2, $3)
            ON CONFLICT (user_id) DO NOTHING
            """,
            int(user_id), now, now
        )

async def count_users() -> int:
    pool = get_pool()
    async with pool.acquire() as conn:
        v = await conn.fetchval("SELECT COUNT(*) FROM users")
    return int(v or 0)