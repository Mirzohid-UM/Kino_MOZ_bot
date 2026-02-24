# scripts/migrate_sqlite.py
import os, sqlite3

DB_PATH = os.getenv("DB_PATH", "movies.db")
TABLE = os.getenv("MOVIES_TABLE", "movies")

def table_exists(cur, table: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (table,))
    return cur.fetchone() is not None

def col_exists(cur, table: str, col: str) -> bool:
    cur.execute(f"PRAGMA table_info({table});")
    return any(r[1] == col for r in cur.fetchall())

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

# 1) Jadval yo‘q bo‘lsa — bu DB bo‘sh degani.
if not table_exists(cur, TABLE):
    print(f"⚠️ Table '{TABLE}' not found in {DB_PATH}. DB is empty or wrong path.")
    print("✅ Skipping ALTER. Create schema first (seed DB or run your initial migrations).")
    con.close()
    raise SystemExit(0)

# 2) title_raw ustuni
if not col_exists(cur, TABLE, "title_raw"):
    cur.execute(f"ALTER TABLE {TABLE} ADD COLUMN title_raw TEXT;")
    # Agar title bo'lsa, to'ldiramiz
    if col_exists(cur, TABLE, "title"):
        cur.execute(f"UPDATE {TABLE} SET title_raw = title WHERE title_raw IS NULL;")
    con.commit()
    print("✅ Migrated: added title_raw")
else:
    print("✅ OK: title_raw exists")

con.close()