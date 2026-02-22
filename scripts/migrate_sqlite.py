import sqlite3, os

DB_PATH = os.getenv("DB_PATH", "movies.db")
TABLE = "movies"

def col_exists(cur, table, col):
    cur.execute(f"PRAGMA table_info({table});")
    return any(r[1] == col for r in cur.fetchall())

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

if not col_exists(cur, TABLE, "title_raw"):
    cur.execute(f"ALTER TABLE {TABLE} ADD COLUMN title_raw TEXT;")
    if col_exists(cur, TABLE, "title"):
        cur.execute(f"UPDATE {TABLE} SET title_raw = title WHERE title_raw IS NULL;")
    con.commit()
    print("✅ Migrated: added title_raw")
else:
    print("✅ title_raw already exists")

con.close()