# db/movies.py
from __future__ import annotations
import time
from typing import List
from db.core import get_pool
from db.utils import normalize

async def add_movie(*, title: str, message_id: int, channel_id: int) -> None:
    pool = get_pool()
    now = int(time.time())
    raw = (title or "").strip()[:150]
    norm = normalize(raw)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO movies (channel_id, message_id, title, title_raw, title_norm, created_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (channel_id, message_id) DO UPDATE SET
              title      = EXCLUDED.title,
              title_raw  = EXCLUDED.title_raw,
              title_norm = EXCLUDED.title_norm
            """,
            int(channel_id), int(message_id),
            raw, raw, norm, now
        )

async def add_alias(*, alias: str, message_id: int, channel_id: int) -> None:
    raw = (alias or "").strip()[:150]
    if not raw:
        return
    norm = normalize(raw)
    now = int(time.time())

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO movie_aliases (channel_id, message_id, alias_raw, alias_norm, created_at)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (channel_id, message_id, alias_norm) DO NOTHING
            """,
            int(channel_id), int(message_id), raw, norm, now
        )

async def add_movie_with_aliases(*, title: str, aliases: List[str], message_id: int, channel_id: int) -> None:
    raw_title = (title or "").strip()[:150]
    if not raw_title:
        return
    norm_title = normalize(raw_title)
    now = int(time.time())

    # aliaslarni uniq + normalize
    seen = set()
    cleaned = []
    for a in aliases or []:
        ar = (a or "").strip()[:150]
        if not ar:
            continue
        an = normalize(ar)
        if an in seen:
            continue
        seen.add(an)
        cleaned.append((ar, an))

    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO movies (channel_id, message_id, title, title_raw, title_norm, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (channel_id, message_id) DO UPDATE SET
                  title      = EXCLUDED.title,
                  title_raw  = EXCLUDED.title_raw,
                  title_norm = EXCLUDED.title_norm
                """,
                int(channel_id), int(message_id),
                raw_title, raw_title, norm_title, now
            )

            if cleaned:
                # bulk insert (UNNEST) with 2 arrays
                alias_raws = [x[0] for x in cleaned]
                alias_norms = [x[1] for x in cleaned]
                await conn.execute(
                    """
                    INSERT INTO movie_aliases (channel_id, message_id, alias_raw, alias_norm, created_at)
                    SELECT $1, $2, r, n, $3
                    FROM UNNEST($4::text[], $5::text[]) AS t(r, n)
                    ON CONFLICT (channel_id, message_id, alias_norm) DO NOTHING
                    """,
                    int(channel_id), int(message_id), now, alias_raws, alias_norms
                )

async def delete_movie_by_message_id(*, message_id: int, channel_id: int) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM movie_aliases WHERE message_id=$1 AND channel_id=$2",
                int(message_id), int(channel_id)
            )
            await conn.execute(
                "DELETE FROM movies WHERE message_id=$1 AND channel_id=$2",
                int(message_id), int(channel_id)
            )

async def get_movies_limit(limit: int = 300):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT COALESCE(title_raw, title) AS title, message_id, channel_id
            FROM movies
            ORDER BY created_at DESC
            LIMIT $1
            """,
            int(limit)
        )
    return [dict(r) for r in rows]

async def get_movies_like(query: str, limit: int = 20):
    q = normalize(query).strip()
    if not q:
        return []

    tokens = [t for t in q.split() if len(t) >= 2]
    if not tokens:
        return []

    pool = get_pool()
    async with pool.acquire() as conn:
        # 1) EXACT word match
        exact = await conn.fetch(
            """
            SELECT COALESCE(title_raw, title) AS title, message_id, channel_id
            FROM movies
            WHERE (' ' || COALESCE(title_norm,'') || ' ') LIKE ('% ' || $1 || ' %')
            LIMIT $2
            """,
            q, int(limit)
        )
        if exact:
            return [dict(r) for r in exact]

        # 2) WORD-START (word boundary-ish)
        clauses = []
        params = []
        i = 1
        for t in tokens:
            clauses.append(f"(' ' || COALESCE(title_norm,'') || ' ') LIKE ${i}")
            params.append(f"% {t}%")
            i += 1

        clauses_sql = " AND ".join(clauses)
        params.append(int(limit))

        ws = await conn.fetch(
            f"""
            SELECT COALESCE(title_raw, title) AS title, message_id, channel_id
            FROM movies
            WHERE {clauses_sql}
            ORDER BY created_at DESC
            LIMIT ${i}
            """,
            *params
        )
        if ws:
            return [dict(r) for r in ws]

        # 3) CONTAINS
        clauses = []
        params = []
        i = 1
        for t in tokens:
            clauses.append(f"COALESCE(title_norm,'') LIKE ${i}")
            params.append(f"%{t}%")
            i += 1
        params.append(int(limit))

        ct = await conn.fetch(
            f"""
            SELECT COALESCE(title_raw, title) AS title, message_id, channel_id
            FROM movies
            WHERE {" AND ".join(clauses)}
            ORDER BY created_at DESC
            LIMIT ${i}
            """,
            *params
        )
        return [dict(r) for r in ct]