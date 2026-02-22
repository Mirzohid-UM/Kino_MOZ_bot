import sqlite3

DB_PATH = "movies.db"

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

cur.execute("""
UPDATE movies
SET title = title_raw
WHERE title_raw IS NOT NULL AND TRIM(title_raw) <> '';
""")

cur.execute("""
CREATE UNIQUE INDEX IF NOT EXISTS uq_movies_channel_msg
ON movies(channel_id, message_id);
""")

con.commit()
con.close()
print("Done.")