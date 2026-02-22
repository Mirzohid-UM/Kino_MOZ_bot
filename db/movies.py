# db/movies.py
from __future__ import annotations
import time
from .core import get_conn, normalize

def add_movie(title: str, message_id: int, channel_id: int) -> None:
    conn = get_conn()
    raw = (title or "").strip()
    norm = normalize(raw)
    now = int(time.time())

    conn.execute("""
        INSERT INTO movies (channel_id, title, title_raw, title_norm, message_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(channel_id, message_id)
        DO UPDATE SET
            title=excluded.title,
            title_raw=excluded.title_raw,
            title_norm=excluded.title_norm
    """, (int(channel_id), raw, raw, norm, int(message_id), now))
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

    # 1️⃣ EXACT PHRASE (eng kuchli)
    exact = conn.execute(
        """
        SELECT COALESCE(title_raw, title) AS title, message_id, channel_id
        FROM movies
        WHERE ' ' || title_norm || ' ' LIKE '% ' || :q || ' %'
        LIMIT ?
        """,
        (q, int(limit)),
    ).fetchall()
    if exact:
        return exact

    # 2️⃣ WORD-START MATCH (so‘z boshidan mos)
    where = " AND ".join(
        ["' ' || title_norm || ' ' LIKE ?"] * len(tokens)
    )
    params = [f"% {t}%" for t in tokens] + [int(limit)]

    word_start = conn.execute(
        f"""
        SELECT COALESCE(title_raw, title) AS title, message_id, channel_id
        FROM movies
        WHERE {where}
        ORDER BY LENGTH(title_norm) ASC
        LIMIT ?
        """,
        params,
    ).fetchall()
    if word_start:
        return word_start

    # 3️⃣ CONTAINS fallback (oxirgi chora)
    where = " AND ".join(["title_norm LIKE ?"] * len(tokens))
    params = [f"%{t}%" for t in tokens] + [int(limit)]

    return conn.execute(
        f"""
        SELECT COALESCE(title_raw, title) AS title, message_id, channel_id
        FROM movies
        WHERE {where}
        ORDER BY LENGTH(title_norm) ASC
        LIMIT ?
        """,
        params,
    ).fetchall()

def get_movies_limit(limit: int = 50):
    conn = get_conn()
    return conn.execute(
        """
        SELECT COALESCE(title_raw, title) AS title, message_id, channel_id
        FROM movies
        ORDER BY id DESC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()