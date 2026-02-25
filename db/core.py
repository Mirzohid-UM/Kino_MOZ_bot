# db/core.py
from __future__ import annotations

import os
import logging
from typing import Optional, Any, Iterable

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")


class PgConn:
    """
    sqlite-like wrapper:
      - conn.execute(sql, params).fetchone()/fetchall()
      - conn.commit()
    """
    def __init__(self, raw_conn: psycopg2.extensions.connection):
        self._c = raw_conn

    def execute(self, sql: str, params: Optional[Iterable[Any]] = None):
        cur = self._c.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params or ())
        return cur  # cursor has fetchone/fetchall

    def commit(self) -> None:
        self._c.commit()

    def rollback(self) -> None:
        self._c.rollback()

    def close(self) -> None:
        self._c.close()


_conn: Optional[PgConn] = None


def get_conn() -> PgConn:
    global _conn
    if _conn is None:
        url = DATABASE_URL.strip()
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        raw = psycopg2.connect(url)
        raw.autocommit = False
        _conn = PgConn(raw)
        logger.info("Connected to PostgreSQL")
    return _conn