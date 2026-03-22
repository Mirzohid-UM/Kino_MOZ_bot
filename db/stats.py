import asyncpg
import time

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            user='username', password='password',
            database='db_name', host='localhost'
        )
    return _pool

async def get_today_stats():
    pool = await get_pool()  # <-- bu yerda await kerak
    today_start = int(time.time()) - (int(time.time()) % 86400)

    async with pool.acquire() as conn:
        # yangi userlar
        new_users = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE created_at >= $1",
            today_start
        )

        # bloklanganlar
        blocked = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE blocked = TRUE AND updated_at >= $1",
            today_start
        )

        # obuna tugaganlar
        expired = await conn.fetchval(
            """
            SELECT COUNT(*) FROM user_access
            WHERE expires_at < EXTRACT(EPOCH FROM NOW())
            AND expires_at >= $1
            """,
            today_start
        )

        # nechta grant bo‘lgan
        grants = await conn.fetchval(
            """
            SELECT COUNT(*) FROM audit
            WHERE action='grant_access' AND created_at >= $1
            """,
            today_start
        )

        # jami berilgan kunlar
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