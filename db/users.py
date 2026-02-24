# db/users.py
# db/users.py
from __future__ import annotations
import time
from .core import get_conn


def upsert_user(user_id: int, username: str | None, full_name: str | None) -> None:
    conn = get_conn()
    now = int(time.time())

    conn.execute(
        """
        INSERT INTO users (user_id, username, full_name, joined_at, last_seen)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            username  = COALESCE(EXCLUDED.username, users.username),
            full_name = COALESCE(EXCLUDED.full_name, users.full_name),
            last_seen = EXCLUDED.last_seen
        """,
        (int(user_id), username, full_name, now, now),
    )
    conn.commit()


def ensure_user_exists(user_id: int) -> None:
    conn = get_conn()
    now = int(time.time())

    conn.execute(
        """
        INSERT INTO users (user_id, username, full_name, joined_at, last_seen)
        VALUES (%s, NULL, NULL, %s, %s)
        ON CONFLICT (user_id) DO NOTHING
        """,
        (int(user_id), now, now),
    )
    conn.commit()


def count_users() -> int:
    conn = get_conn()
    row = conn.execute("SELECT COUNT(*) AS cnt FROM users").fetchone()
    return int(row["cnt"])