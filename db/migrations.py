# db/migrations.py
from __future__ import annotations
import time
from .core import get_conn

DEFAULT_CHANNEL_ID = -1002297106905

def _table_exists(conn, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return bool(row)

def _column_exists(conn, table: str, col: str) -> bool:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == col for r in cols)

def migrate_movies_table(conn) -> None:
    if not _table_exists(conn, "movies"):
        conn.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            created_at INTEGER NOT NULL
        )
        """)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_movies_channel_msg ON movies(channel_id, message_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_movies_title ON movies(title)")
        return

    if not _column_exists(conn, "movies", "channel_id"):
        conn.execute("ALTER TABLE movies ADD COLUMN channel_id INTEGER;")
        conn.execute("UPDATE movies SET channel_id=? WHERE channel_id IS NULL;", (DEFAULT_CHANNEL_ID,))

    if not _column_exists(conn, "movies", "created_at"):
        conn.execute("ALTER TABLE movies ADD COLUMN created_at INTEGER;")
        conn.execute("UPDATE movies SET created_at=? WHERE created_at IS NULL;", (int(time.time()),))

    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_movies_channel_msg ON movies(channel_id, message_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_movies_title ON movies(title)")

def init_db() -> None:
    conn = get_conn()

    migrate_movies_table(conn)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id   INTEGER PRIMARY KEY,
        username  TEXT,
        full_name TEXT,
        joined_at INTEGER NOT NULL,
        last_seen INTEGER NOT NULL,
        is_admin  INTEGER NOT NULL DEFAULT 0,
        is_banned INTEGER NOT NULL DEFAULT 0
    )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_last_seen ON users(last_seen)")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS user_access (
        user_id INTEGER PRIMARY KEY,
        expires_at INTEGER NOT NULL
    )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_access_expires ON user_access(expires_at)")

    # db/migrations.py  ichida init_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS access_notifs (
        user_id    INTEGER NOT NULL,
        kind       TEXT NOT NULL,          -- 'd3' yoki 'd1'
        expires_at INTEGER NOT NULL,
        sent_at    INTEGER NOT NULL,
        PRIMARY KEY (user_id, kind, expires_at)
    )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_access_notifs_sent ON access_notifs(sent_at)")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        target_id INTEGER,
        meta TEXT,
        created_at INTEGER NOT NULL
    )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at)")

    conn.execute("""
    CREATE TABLE IF NOT EXISTS search_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        query TEXT NOT NULL,
        found INTEGER NOT NULL,
        created_at INTEGER NOT NULL
    )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_search_created ON search_logs(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_search_user ON search_logs(user_id)")

    conn.commit()
