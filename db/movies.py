# db/migrations.py
# db/movies.py
from __future__ import annotations
import time
from .core import get_conn
from .utils import normalize


def add_movie(title: str, message_id: int, channel_id: int) -> None:
    conn = get_conn()

    raw = (title or "").strip()
    if not raw:
        return

    norm = normalize(raw)
    now = int(time.time())

    conn.execute(
        """
        INSERT INTO movies (channel_id, title, title_raw, title_norm, message_id, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (channel_id, message_id) DO UPDATE SET
            title = EXCLUDED.title,
            title_raw = EXCLUDED.title_raw,
            title_norm = EXCLUDED.title_norm,
            created_at = EXCLUDED.created_at
        """,
        (int(channel_id), raw, raw, norm, int(message_id), int(now)),
    )
    conn.commit()


def add_alias(alias: str, message_id: int, channel_id: int) -> None:
    conn = get_conn()

    raw = (alias or "").strip()
    if not raw:
        return

    norm = normalize(raw)
    now = int(time.time())

    conn.execute(
        """
        INSERT INTO movie_aliases (channel_id, message_id, alias_raw, alias_norm, created_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (channel_id, message_id, alias_norm) DO NOTHING
        """,
        (int(channel_id), int(message_id), raw, norm, int(now)),
    )
    conn.commit()


def delete_movie_by_message_id(message_id: int, channel_id: int) -> None:
    conn = get_conn()

    conn.execute(
        """
        DELETE FROM movie_aliases
        WHERE message_id=%s AND channel_id=%s
        """,
        (int(message_id), int(channel_id)),
    )
    conn.execute(
        """
        DELETE FROM movies
        WHERE message_id=%s AND channel_id=%s
        """,
        (int(message_id), int(channel_id)),
    )
    conn.commit()


def get_movies_limit(limit: int = 300):
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT COALESCE(title_raw, title) AS title, message_id, channel_id
        FROM movies
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (int(limit),),
    ).fetchall()
    return [dict(r) for r in rows]




def get_movies_like(query: str, limit: int = 20):
    conn = get_conn()

    q = normalize(query).strip()
    if not q:
        return []

    tokens = [t for t in q.split() if len(t) >= 2]
    if not tokens:
        return []

    # 1) EXACT word match
    exact = conn.execute(
        """
        SELECT COALESCE(title_raw, title) AS title, message_id, channel_id
        FROM movies
        WHERE (' ' || COALESCE(title_norm,'') || ' ') LIKE ('%% ' || %s || ' %%')
        LIMIT %s
        """,
        (q, int(limit)),
    ).fetchall()
    if exact:
        return [dict(r) for r in exact]

    # 2) WORD-START style (har token bo‘yicha)
    # (' ' || title_norm || ' ') LIKE '% token%'
    clauses = []
    params = []
    for t in tokens:
        clauses.append("(' ' || COALESCE(title_norm,'') || ' ') LIKE %s")
        params.append(f"% {t}%")

    ws = conn.execute(
        f"""
        SELECT COALESCE(title_raw, title) AS title, message_id, channel_id
        FROM movies
        WHERE {" AND ".join(clauses)}
        ORDER BY LENGTH(COALESCE(title_norm,'')) ASC
        LIMIT %s
        """,
        (*params, int(limit)),
    ).fetchall()
    if ws:
        return [dict(r) for r in ws]

    # 3) CONTAINS (fallback)
    clauses = []
    params = []
    for t in tokens:
        clauses.append("COALESCE(title_norm,'') LIKE %s")
        params.append(f"%{t}%")

    ct = conn.execute(
        f"""
        SELECT COALESCE(title_raw, title) AS title, message_id, channel_id
        FROM movies
        WHERE {" AND ".join(clauses)}
        ORDER BY LENGTH(COALESCE(title_norm,'')) ASC
        LIMIT %s
        """,
        (*params, int(limit)),
    ).fetchall()
    return [dict(r) for r in ct]