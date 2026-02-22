# db/core.py
from __future__ import annotations
import os, re, sqlite3, threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]   # project root: ~/PythonProject
DB_PATH = BASE_DIR / "movies.db"


_local = threading.local()

def get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)

    if conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row

        # Performance va stability
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")

        _local.conn = conn

    return conn

def normalize(text: str) -> str:
    s = (text or "").lower()

    # o‘zbek apostroflarini bir xil qilamiz
    s = s.replace("’", "'").replace("`", "'")

    # texnik belgilardan tozalash
    s = re.sub(r"[@#]\w+", " ", s)

    # sifat/codec so'zlarini olib tashlash
    s = re.sub(
        r"\b(1080p|720p|480p|4k|hdr|hevc|x265|x264|bluray|brrip|web[- ]?dl|webrip|dvdrip|cam)\b",
        " ",
        s,
    )

    # yillarni olib tashlash
    s = re.sub(r"\b(19\d{2}|20\d{2})\b", " ", s)

    # ajratkichlarni spacega aylantirish
    s = s.replace("|", " ").replace("_", " ").replace("-", " ").replace("/", " ")

    # faqat harf/raqam/space qoldiramiz (unicode friendly)
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)

    # ortiqcha space yo'qotamiz
    s = re.sub(r"\s+", " ", s).strip()

    return s