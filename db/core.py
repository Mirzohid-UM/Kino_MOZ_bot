# db/core.py
from __future__ import annotations
import os, re, sqlite3, threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # db/ papkasi
DB_PATH = os.path.join(os.path.dirname(BASE_DIR), "movies.db")  # eski joylashuvga mos

_local = threading.local()

def get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
        _local.conn = conn
    return conn

def normalize(text: str) -> str:
    s = (text or "").lower()
    s = re.sub(r"[@#]\w+", " ", s)
    s = re.sub(
        r"\b(1080p|720p|480p|4k|hdr|hevc|x265|x264|bluray|brrip|web[- ]?dl|webrip|dvdrip|cam)\b",
        " ",
        s,
    )
    s = re.sub(r"\b(19\d{2}|20\d{2})\b", " ", s)
    s = s.replace("|", " ").replace("_", " ").replace("-", " ")
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s