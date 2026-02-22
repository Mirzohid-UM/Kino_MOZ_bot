import sqlite3

# normalize qayerda bo'lsa shuni import qiling:
# Agar normalize service/search.py ichida bo'lsa:
from service.search import normalize

DB_PATH = "movies.db"

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

rows = cur.execute("SELECT id, COALESCE(title_raw, title) FROM movies").fetchall()

n = 0
for movie_id, title in rows:
    tn = normalize(title)
    cur.execute("UPDATE movies SET title_norm=? WHERE id=?", (tn, movie_id))
    n += 1

con.commit()
cur.execute("CREATE INDEX IF NOT EXISTS idx_movies_title_norm ON movies(title_norm)")
con.commit()
con.close()

print("Rebuilt title_norm for:", n)
