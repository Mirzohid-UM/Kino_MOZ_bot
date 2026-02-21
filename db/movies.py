# db/movies.py
from __future__ import annotations
import time
from .core import get_conn, normalize

def add_movie(title: str, message_id: int, channel_id: int) -> None:
    conn = get_conn()
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
    conn = get_conn()
    conn.execute(
        "DELETE FROM movies WHERE channel_id=? AND message_id=?",
        (int(channel_id), int(message_id)),
    )
    conn.commit()

def get_movies_like(query: str, limit: int = 20):
    conn = get_conn()
    q = normalize(query).strip()
    if not q:
        return []

    tokens = [t for t in q.split() if len(t) >= 2]
    if not tokens:
        return []

    # 1) exact
    exact = conn.execute(
        """
        SELECT title, message_id, channel_id
        FROM movies
        WHERE title = ?
        LIMIT ?
        """,
        (" ".join(tokens), int(limit)),
    ).fetchall()
    if exact:
        return exact

    # 2) startswith for each token
    where_start = " AND ".join(["title LIKE ?"] * len(tokens))
    params_start = [f"{t}%" for t in tokens] + [int(limit)]
    start_match = conn.execute(
        f"""
        SELECT title, message_id, channel_id
        FROM movies
        WHERE {where_start}
        LIMIT ?
        """,
        params_start,
    ).fetchall()
    if start_match:
        return start_match

    # 3) contains
    where = " AND ".join(["title LIKE ?"] * len(tokens))
    params = [f"%{t}%" for t in tokens] + [int(limit)]
    return conn.execute(
        f"""
        SELECT title, message_id, channel_id
        FROM movies
        WHERE {where}
        ORDER BY LENGTH(title) ASC
        LIMIT ?
        """,
        params,
    ).fetchall()

def get_movies_limit(limit: int = 50):
    conn = get_conn()
    return conn.execute(
        "SELECT title, message_id, channel_id FROM movies ORDER BY id DESC LIMIT ?",
        (int(limit),),
    ).fetchall()