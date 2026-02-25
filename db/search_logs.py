# db/search_logs.py
from __future__ import annotations
import time
from db.core import get_pool

async def log_search(*, user_id: int, query: str, found: int) -> None:
    now = int(time.time())
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO search_logs (user_id, query, found, created_at)
            VALUES ($1, $2, $3, $4)
            """,
            int(user_id), str(query), int(found), now
        )