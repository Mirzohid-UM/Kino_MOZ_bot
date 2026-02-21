# db/access.py
from __future__ import annotations

import time
from .core import get_conn
from .users import ensure_user_exists


def grant_access(user_id: int, days: int = 1) -> None:
    ensure_user_exists(user_id)
    conn = get_conn()
    expires_at = int(time.time()) + int(days) * 86400
    conn.execute(
        """
        INSERT INTO user_access (user_id, expires_at)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET expires_at=excluded.expires_at
        """,
        (int(user_id), int(expires_at)),
    )
    conn.commit()


def extend_access(user_id: int, days: int = 30) -> int:
    ensure_user_exists(user_id)
    conn = get_conn()
    now = int(time.time())

    row = conn.execute(
        "SELECT expires_at FROM user_access WHERE user_id=?",
        (int(user_id),),
    ).fetchone()

    base = int(row["expires_at"]) if row and int(row["expires_at"]) > now else now
    new_expires = base + int(days) * 86400

    conn.execute(
        """
        INSERT INTO user_access (user_id, expires_at)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET expires_at=excluded.expires_at
        """,
        (int(user_id), int(new_expires)),
    )
    conn.commit()
    return int(new_expires)


def has_access(user_id: int) -> bool:
    conn = get_conn()
    now = int(time.time())
    row = conn.execute(
        "SELECT expires_at FROM user_access WHERE user_id=?",
        (int(user_id),),
    ).fetchone()
    return bool(row and int(row["expires_at"]) > now)


def count_active_subs() -> int:
    conn = get_conn()
    now = int(time.time())
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM user_access WHERE expires_at > ?",
            (int(now),),
        ).fetchone()[0]
    )


def list_active_users(limit: int = 50):
    conn = get_conn()
    now = int(time.time())
    return conn.execute(
        """
        SELECT user_id, expires_at
        FROM user_access
        WHERE expires_at > ?
        ORDER BY expires_at ASC
        LIMIT ?
        """,
        (int(now), int(limit)),
    ).fetchall()


def list_active_user_ids() -> list[int]:
    conn = get_conn()
    now = int(time.time())
    rows = conn.execute(
        "SELECT user_id FROM user_access WHERE expires_at > ?",
        (int(now),),
    ).fetchall()
    return [int(r["user_id"]) for r in rows]


def list_active_users_with_profiles(limit: int = 200):
    """
    user_access + users join.
    returns rows: user_id, expires_at, username, full_name
    """
    conn = get_conn()
    now = int(time.time())
    return conn.execute(
        """
        SELECT ua.user_id, ua.expires_at, u.username, u.full_name
        FROM user_access ua
        LEFT JOIN users u ON u.user_id = ua.user_id
        WHERE ua.expires_at > ?
        ORDER BY ua.expires_at ASC
        LIMIT ?
        """,
        (now, int(limit)),
    ).fetchall()

def get_expiring_between(start_ts: int, end_ts: int, limit: int = 500):
    """
    expires_at start_ts..end_ts oralig'ida bo'lgan aktivlar
    """
    conn = get_conn()
    return conn.execute(
        """
        SELECT ua.user_id, ua.expires_at, u.username, u.full_name
        FROM user_access ua
        LEFT JOIN users u ON u.user_id = ua.user_id
        WHERE ua.expires_at >= ? AND ua.expires_at < ?
        ORDER BY ua.expires_at ASC
        LIMIT ?
        """,
        (int(start_ts), int(end_ts), int(limit)),
    ).fetchall()

def was_notified(user_id: int, kind: str, expires_at: int) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM access_notifs WHERE user_id=? AND kind=? AND expires_at=?",
        (int(user_id), str(kind), int(expires_at)),
    ).fetchone()
    return bool(row)

def mark_notified(user_id: int, kind: str, expires_at: int) -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT OR IGNORE INTO access_notifs (user_id, kind, expires_at, sent_at)
        VALUES (?, ?, ?, ?)
        """,
        (int(user_id), str(kind), int(expires_at), int(time.time())),
    )
    conn.commit()