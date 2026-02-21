# db/users.py
from __future__ import annotations

import time
from .core import get_conn


def ensure_user_exists(user_id: int) -> None:
    """Grant/extend qilganda ham users jadvalini to‘ldirib boradi."""
    conn = get_conn()
    now = int(time.time())
    conn.execute(
        """
        INSERT OR IGNORE INTO users (user_id, username, full_name, joined_at, last_seen)
        VALUES (?, NULL, NULL, ?, ?)
        """,
        (int(user_id), now, now),
    )
    conn.commit()


def upsert_user(user_id: int, username: str | None, full_name: str | None) -> None:
    conn = get_conn()
    now = int(time.time())
    conn.execute(
        """
        INSERT INTO users (user_id, username, full_name, joined_at, last_seen)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username,
            full_name=excluded.full_name,
            last_seen=excluded.last_seen
        """,
        (int(user_id), username, full_name, now, now),
    )
    conn.commit()


def count_users() -> int:
    conn = get_conn()
    return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])