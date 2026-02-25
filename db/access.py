# db/access.py
from __future__ import annotations

import time
from typing import List, Dict, Any

from .core import get_conn
from .users import ensure_user_exists


def grant_access(user_id: int, days: int = 1) -> None:
    ensure_user_exists(user_id)
    conn = get_conn()
    expires_at = int(time.time()) + days * 86400

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO user_access (user_id, expires_at)
            VALUES (%s, %s)
            ON CONFLICT (user_id) 
            DO UPDATE SET expires_at = EXCLUDED.expires_at
        """, (user_id, expires_at))
        conn.commit()


def extend_access(user_id: int, days: int = 30) -> int:
    ensure_user_exists(user_id)
    conn = get_conn()
    now = int(time.time())

    with conn.cursor() as cur:
        cur.execute(
            "SELECT expires_at FROM user_access WHERE user_id = %s",
            (user_id,)
        )
        row = cur.fetchone()

        base = int(row["expires_at"]) if row and int(row["expires_at"]) > now else now
        new_expires = base + days * 86400

        cur.execute("""
            INSERT INTO user_access (user_id, expires_at)
            VALUES (%s, %s)
            ON CONFLICT (user_id) 
            DO UPDATE SET expires_at = EXCLUDED.expires_at
        """, (user_id, new_expires))

        conn.commit()
        return new_expires


def has_access(user_id: int) -> bool:
    conn = get_conn()
    now = int(time.time())

    with conn.cursor() as cur:
        cur.execute(
            "SELECT expires_at FROM user_access WHERE user_id = %s",
            (user_id,)
        )
        row = cur.fetchone()
        return bool(row and int(row["expires_at"]) > now)


def count_active_subs() -> int:
    conn = get_conn()
    now = int(time.time())

    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM user_access WHERE expires_at > %s",
            (now,)
        )
        return int(cur.fetchone()[0])


def list_active_users(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_conn()
    now = int(time.time())

    with conn.cursor() as cur:
        cur.execute("""
            SELECT user_id, expires_at
            FROM user_access
            WHERE expires_at > %s
            ORDER BY expires_at ASC
            LIMIT %s
        """, (now, limit))
        return cur.fetchall()


def list_active_user_ids() -> List[int]:
    conn = get_conn()
    now = int(time.time())

    with conn.cursor() as cur:
        cur.execute(
            "SELECT user_id FROM user_access WHERE expires_at > %s",
            (now,)
        )
        rows = cur.fetchall()
        return [int(r["user_id"]) for r in rows]


def list_active_users_with_profiles(limit: int = 200) -> List[Dict[str, Any]]:
    """
    user_access + users join.
    returns rows: user_id, expires_at, username, full_name
    """
    conn = get_conn()
    now = int(time.time())

    with conn.cursor() as cur:
        cur.execute("""
            SELECT ua.user_id, ua.expires_at, u.username, u.full_name
            FROM user_access ua
            LEFT JOIN users u ON u.user_id = ua.user_id
            WHERE ua.expires_at > %s
            ORDER BY ua.expires_at ASC
            LIMIT %s
        """, (now, limit))
        return cur.fetchall()


def get_expiring_between(start_ts: int, end_ts: int, limit: int = 500) -> List[Dict[str, Any]]:
    """
    expires_at start_ts..end_ts oralig'ida bo'lgan aktivlar
    """
    conn = get_conn()

    with conn.cursor() as cur:
        cur.execute("""
            SELECT ua.user_id, ua.expires_at, u.username, u.full_name
            FROM user_access ua
            LEFT JOIN users u ON u.user_id = ua.user_id
            WHERE ua.expires_at >= %s AND ua.expires_at < %s
            ORDER BY ua.expires_at ASC
            LIMIT %s
        """, (start_ts, end_ts, limit))
        return cur.fetchall()


def was_notified(user_id: int, kind: str, expires_at: int) -> bool:
    conn = get_conn()

    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM access_notifs WHERE user_id = %s AND kind = %s AND expires_at = %s",
            (user_id, kind, expires_at)
        )
        row = cur.fetchone()
        return bool(row)


def mark_notified(user_id: int, kind: str, expires_at: int) -> None:
    conn = get_conn()

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO access_notifs (user_id, kind, expires_at, sent_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (user_id, kind, expires_at, int(time.time())))
        conn.commit()