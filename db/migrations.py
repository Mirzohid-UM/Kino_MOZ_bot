# db/migrations.py
from __future__ import annotations
import time
from db.core import get_pool

DEFAULT_CHANNEL_ID = -1002297106905

async def _table_exists(conn, name: str, schema: str = "public") -> bool:
    v = await conn.fetchval(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema=$1 AND table_name=$2
        """,
        schema, name,
    )
    return bool(v)

async def _column_exists(conn, table: str, col: str, schema: str = "public") -> bool:
    v = await conn.fetchval(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema=$1 AND table_name=$2 AND column_name=$3
        """,
        schema, table, col,
    )
    return bool(v)

async def migrate_movies_table(conn) -> None:
    if not await _table_exists(conn, "movies"):
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS movies (
                id SERIAL PRIMARY KEY,
                channel_id BIGINT NOT NULL,
                title TEXT NOT NULL,
                title_raw TEXT,
                title_norm TEXT,
                message_id BIGINT NOT NULL,
                created_at BIGINT NOT NULL
            )
            """
        )
    else:
        if not await _column_exists(conn, "movies", "title_raw"):
            await conn.execute("ALTER TABLE movies ADD COLUMN title_raw TEXT;")
        if not await _column_exists(conn, "movies", "title_norm"):
            await conn.execute("ALTER TABLE movies ADD COLUMN title_norm TEXT;")
        if not await _column_exists(conn, "movies", "channel_id"):
            await conn.execute("ALTER TABLE movies ADD COLUMN channel_id BIGINT;")
            await conn.execute(
                "UPDATE movies SET channel_id=$1 WHERE channel_id IS NULL;",
                int(DEFAULT_CHANNEL_ID),
            )
        if not await _column_exists(conn, "movies", "created_at"):
            await conn.execute("ALTER TABLE movies ADD COLUMN created_at BIGINT;")
            await conn.execute(
                "UPDATE movies SET created_at=$1 WHERE created_at IS NULL;",
                int(time.time()),
            )

    await conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_movies_channel_msg
        ON movies(channel_id, message_id)
        """
    )
    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_movies_title_norm
        ON movies(title_norm)
        """
    )
    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_movies_title_raw
        ON movies(title_raw)
        """
    )

    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS movie_aliases (
            channel_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            alias_raw TEXT NOT NULL,
            alias_norm TEXT NOT NULL,
            created_at BIGINT NOT NULL DEFAULT 0,
            PRIMARY KEY (channel_id, message_id, alias_norm)
        )
        """
    )
    await conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_aliases_norm
        ON movie_aliases(alias_norm)
        """
    )

async def init_db() -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id SERIAL PRIMARY KEY,
                actor_id BIGINT NOT NULL,
                action TEXT NOT NULL,
                target_id BIGINT,
                meta JSONB,
                created_at BIGINT NOT NULL
            )
            """)

            await migrate_movies_table(conn)

            await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id   BIGINT PRIMARY KEY,
                username  TEXT,
                full_name TEXT,
                joined_at BIGINT NOT NULL,
                last_seen BIGINT NOT NULL,
                is_admin  INTEGER NOT NULL DEFAULT 0,
                is_banned INTEGER NOT NULL DEFAULT 0
            )
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen)")

            await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_access (
                user_id BIGINT PRIMARY KEY,
                expires_at BIGINT NOT NULL
            )
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_access_expires ON user_access(expires_at)")

            await conn.execute("""
            CREATE TABLE IF NOT EXISTS access_notifs (
                user_id    BIGINT NOT NULL,
                kind       TEXT NOT NULL,
                expires_at BIGINT NOT NULL,
                sent_at    BIGINT NOT NULL,
                PRIMARY KEY (user_id, kind, expires_at)
            )
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_access_notifs_sent ON access_notifs(sent_at)")

            await conn.execute("""
            CREATE TABLE IF NOT EXISTS search_logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                query TEXT NOT NULL,
                found INTEGER NOT NULL,
                created_at BIGINT NOT NULL
            )
            """)
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_search_created ON search_logs(created_at)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_search_user ON search_logs(user_id)")