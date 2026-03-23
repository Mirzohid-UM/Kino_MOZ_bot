from __future__ import annotations

import time
from db.core import get_pool


async def get_today_stats():
    pool = await get_pool()
    today_start = int(time.time()) - (int(time.time()) % 86400)

    async with pool.acquire() as conn:

        new_users = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE created_at >= $1",
            today_start
        )

        blocked = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE blocked = TRUE AND updated_at >= $1",
            today_start
        )

        expired = await conn.fetchval(
            """
            SELECT COUNT(*) FROM user_access
            WHERE expires_at < EXTRACT(EPOCH FROM NOW())
            AND expires_at >= $1
            """,
            today_start
        )

        grants = await conn.fetchval(
            """
            SELECT COUNT(*) FROM audit
            WHERE action='grant_access' AND created_at >= $1
            """,
            today_start
        )

        total_days = await conn.fetchval(
            """
            SELECT COALESCE(SUM((meta->>'days')::int),0)
            FROM audit
            WHERE action='grant_access' AND created_at >= $1
            """,
            today_start
        )

    return {
        "new_users": new_users,
        "blocked": blocked,
        "expired": expired,
        "grants": grants,
        "total_days": total_days
    }