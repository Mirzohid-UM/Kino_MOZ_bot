import os
import sqlite3
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "movies.db")

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

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT id, title_raw FROM movies").fetchall()

    changed = 0
    for r in rows:
        raw = r["title_raw"] or ""
        norm = normalize(raw)
        conn.execute("UPDATE movies SET title_norm=? WHERE id=?", (norm, r["id"]))
        changed += 1

    conn.commit()
    print("Backfilled title_norm:", changed)

if __name__ == "__main__":
    main()