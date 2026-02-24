# db/migrations.py
from __future__ import annotations
import time
from .core import get_conn

DEFAULT_CHANNEL_ID = -1002297106905


def _table_exists(conn, name: str, schema: str = "public") -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema=%s AND table_name=%s
        """,
        (schema, name),
    ).fetchone()
    return bool(row)


def _column_exists(conn, table: str, col: str, schema: str = "public") -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema=%s AND table_name=%s AND column_name=%s
        """,
        (schema, table, col),
    ).fetchone()
    return bool(row)


def migrate_movies_table(conn) -> None:
    # movies
    if not _table_exists(conn, "movies"):
        conn.execute(
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
        # eski jadval bo'lsa kolonka qo'shamiz
        if not _column_exists(conn, "movies", "title_raw"):
            conn.execute("ALTER TABLE movies ADD COLUMN title_raw TEXT;")
        if not _column_exists(conn, "movies", "title_norm"):
            conn.execute("ALTER TABLE movies ADD COLUMN title_norm TEXT;")

        if not _column_exists(conn, "movies", "channel_id"):
            conn.execute("ALTER TABLE movies ADD COLUMN channel_id BIGINT;")
            conn.execute(
                "UPDATE movies SET channel_id=%s WHERE channel_id IS NULL;",
                (int(DEFAULT_CHANNEL_ID),),
            )

        if not _column_exists(conn, "movies", "created_at"):
            conn.execute("ALTER TABLE movies ADD COLUMN created_at BIGINT;")
            conn.execute(
                "UPDATE movies SET created_at=%s WHERE created_at IS NULL;",
                (int(time.time()),),
            )

    # indekslar
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_movies_channel_msg
        ON movies(channel_id, message_id)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_movies_title_norm
        ON movies(title_norm)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_movies_title_raw
        ON movies(title_raw)
        """
    )

    # movie_aliases
    conn.execute(
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
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_aliases_norm
        ON movie_aliases(alias_norm)
        """
    )


def init_db() -> None:
    conn = get_conn()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        actor_id BIGINT NOT NULL,
        action TEXT NOT NULL,
        target_id BIGINT,
        meta JSONB,
        created_at BIGINT NOT NULL
    )
    """)

    migrate_movies_table(conn)

    # qolgan jadvallar (users, user_access, access_notifs, audit_log, search_logs)
    # sizda bor init_db()ni shu yerga qo‘shib qo‘ygan edik
    # (xohlasangiz men sizning final init_db()ni bitta faylga jamlab beraman)

    conn.commit()