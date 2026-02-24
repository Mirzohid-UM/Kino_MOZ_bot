# db/core.py
# db/core.py  (POSTGRES ONLY)
from __future__ import annotations

import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

_conn: Optional[psycopg2.extensions.connection] = None


def get_conn():
    global _conn

    if _conn is None:
        url = DATABASE_URL.strip()

        # Ba'zi hostinglarda postgres:// format bo‘ladi
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]

        _conn = psycopg2.connect(
            url,
            cursor_factory=RealDictCursor,
        )
        _conn.autocommit = False

        logger.info("Connected to PostgreSQL")

    return _conn