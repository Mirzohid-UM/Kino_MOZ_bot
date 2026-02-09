# /home/mozcyber/PythonProject/db.py
from __future__ import annotations

import os
import re
import sqlite3
import threading
import time
from typing import Optional, Iterable

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "movies.db")

DEFAULT_CHANNEL_ID = -1002297106905  # sizning kino kanal ID

_local = threading.local()


# -------------------------
# Connection
# -------------------------
def _get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row

        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")

        _local.conn = conn
    return conn


# -------------------------
# Helpers
# -------------------------
def normalize(text: str) -> str:
    s = (text or "").lower()
    s = re.sub(r"[@#]\w+", " ", s)
    s = re.sub(
        r"\b(1080p|720p|480p|4k|hdr|hevc|x265|x264|bluray|brrip|web[- ]?dl|webrip|dvdrip|cam)\b",
        " ",
        s,
    )
    s = re.sub(r"\b(19\d{2}|20\d{2})\b", " ", s)
    s = s.replace("|", " ").replace("_", " ").replace("-", " ")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return bool(row)


def _column_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == col for r in cols)


# -------------------------
# Migrations
# -------------------------
def _migrate_movies_table(conn: sqlite3.Connection) -> None:
    """
    Eski schema: movies(id, title, message_id)
    Yangi schema: movies(id, channel_id, title, message_id, created_at)
    """
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
        return

    if not _column_exists(conn, "movies", "channel_id"):
        conn.execute("ALTER TABLE movies ADD COLUMN channel_id INTEGER;")
        conn.execute(
            "UPDATE movies SET channel_id = ? WHERE channel_id IS NULL;",
            (DEFAULT_CHANNEL_ID,),
        )

    if not _column_exists(conn, "movies", "created_at"):
        conn.execute("ALTER TABLE movies ADD COLUMN created_at INTEGER;")
        conn.execute(
            "UPDATE movies SET created_at = ? WHERE created_at IS NULL;",
            (int(time.time()),),
        )

    conn.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS uq_movies_channel_msg
    ON movies(channel_id, message_id)
    """)

    conn.execute("""
    CREATE INDEX IF NOT EXISTS idx_movies_title
    ON movies(title)
    """)


def init_db() -> None:
    """Bot startida 1 marta chaqirilishi shart."""
    conn = _get_conn()

    # movies migratsiya
    _migrate_movies_table(conn)

    # users
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

    # access
    conn.execute("""
    CREATE TABLE IF NOT EXISTS user_access (
        user_id INTEGER PRIMARY KEY,
        expires_at INTEGER NOT NULL
    )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_access_expires ON user_access(expires_at)")

    # audit
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

    # search logs
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


# -------------------------
# Users
# -------------------------
def ensure_user_exists(user_id: int) -> None:
    """Grant/extend qilganda ham users jadvalini to‘ldirib boradi."""
    conn = _get_conn()
    now = int(time.time())
    conn.execute("""
        INSERT OR IGNORE INTO users (user_id, username, full_name, joined_at, last_seen)
        VALUES (?, NULL, NULL, ?, ?)
    """, (int(user_id), now, now))
    conn.commit()


def upsert_user(user_id: int, username: str | None, full_name: str | None) -> None:
    conn = _get_conn()
    now = int(time.time())
    conn.execute("""
        INSERT INTO users (user_id, username, full_name, joined_at, last_seen)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            full_name=excluded.full_name,
            last_seen=excluded.last_seen
    """, (int(user_id), username, full_name, now, now))
    conn.commit()


def count_users() -> int:
    conn = _get_conn()
    return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])


# -------------------------
# Movies
# -------------------------
def add_movie(title: str, message_id: int, channel_id: int) -> None:
    conn = _get_conn()
    t = normalize(title)
    now = int(time.time())
    conn.execute("""
        INSERT INTO movies (channel_id, title, message_id, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(channel_id, message_id)
        DO UPDATE SET title=excluded.title
    """, (int(channel_id), t, int(message_id), now))
    conn.commit()


def delete_movie_by_message_id(message_id: int, channel_id: int) -> None:
    conn = _get_conn()
    conn.execute(
        "DELETE FROM movies WHERE channel_id=? AND message_id=?",
        (int(channel_id), int(message_id)),
    )
    conn.commit()


def get_movies_like(query: str, limit: int = 20):
    conn = _get_conn()
    q = normalize(query)
    return conn.execute(
        "SELECT title, message_id, channel_id FROM movies WHERE title LIKE ? LIMIT ?",
        (f"%{q}%", int(limit)),
    ).fetchall()


def get_movies_limit(limit: int = 50):
    conn = _get_conn()
    return conn.execute(
        "SELECT title, message_id, channel_id FROM movies ORDER BY id DESC LIMIT ?",
        (int(limit),),
    ).fetchall()


# -------------------------
# Access (subs)
# -------------------------
def grant_access(user_id: int, days: int = 1) -> None:
    ensure_user_exists(user_id)
    conn = _get_conn()
    expires_at = int(time.time()) + int(days) * 86400
    conn.execute("""
        INSERT INTO user_access (user_id, expires_at)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET expires_at=excluded.expires_at
    """, (int(user_id), expires_at))
    conn.commit()


def extend_access(user_id: int, days: int = 30) -> int:
    ensure_user_exists(user_id)
    conn = _get_conn()
    now = int(time.time())

    row = conn.execute(
        "SELECT expires_at FROM user_access WHERE user_id=?",
        (int(user_id),),
    ).fetchone()

    base = int(row["expires_at"]) if row and int(row["expires_at"]) > now else now
    new_expires = base + int(days) * 86400

    conn.execute("""
        INSERT INTO user_access (user_id, expires_at)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET expires_at=excluded.expires_at
    """, (int(user_id), new_expires))
    conn.commit()
    return int(new_expires)


def has_access(user_id: int) -> bool:
    conn = _get_conn()
    now = int(time.time())
    row = conn.execute(
        "SELECT expires_at FROM user_access WHERE user_id=?",
        (int(user_id),),
    ).fetchone()
    return bool(row and int(row["expires_at"]) > now)


def count_active_subs() -> int:
    conn = _get_conn()
    now = int(time.time())
    return int(conn.execute(
        "SELECT COUNT(*) FROM user_access WHERE expires_at > ?",
        (now,),
    ).fetchone()[0])


def list_active_users(limit: int = 50):
    conn = _get_conn()
    now = int(time.time())
    return conn.execute("""
        SELECT user_id, expires_at
        FROM user_access
        WHERE expires_at > ?
        ORDER BY expires_at ASC
        LIMIT ?
    """, (now, int(limit))).fetchall()


def list_active_user_ids() -> list[int]:
    conn = _get_conn()
    now = int(time.time())
    rows = conn.execute(
        "SELECT user_id FROM user_access WHERE expires_at > ?",
        (now,),
    ).fetchall()
    return [int(r["user_id"]) for r in rows]


# -------------------------
# Audit + Search logs
# -------------------------
def audit(
    actor_id: int,
    action: str,
    target_id: Optional[int] = None,
    meta: Optional[str] = None,
) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT INTO audit_log (actor_id, action, target_id, meta, created_at) VALUES (?, ?, ?, ?, ?)",
        (int(actor_id), str(action), target_id, meta, int(time.time())),
    )
    conn.commit()


def last_audit(limit: int = 20):
    conn = _get_conn()
    return conn.execute(
        "SELECT actor_id, action, target_id, meta, created_at FROM audit_log ORDER BY id DESC LIMIT ?",
        (int(limit),),
    ).fetchall()


def log_search(user_id: int, query: str, found: int) -> None:
    conn = _get_conn()
    conn.execute(
        "INSERT INTO search_logs (user_id, query, found, created_at) VALUES (?, ?, ?, ?)",
        (int(user_id), normalize(query), int(found), int(time.time())),
    )
    conn.commit()
