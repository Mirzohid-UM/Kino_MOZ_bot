# db/search_logs.py
from __future__ import annotations

import time
from .core import get_conn, normalize


def log_search(user_id: int, query: str, found: int) -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO search_logs (user_id, query, found, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (int(user_id), normalize(query), int(found), int(time.time())),
    )
    conn.commit()