import re
import sqlite3

DB_PATH = "movies.db"

NOISE_PATTERNS = [
    r"\bo['’`]?zbek\s+tilida\b",
    r"\bobuna\s+bo\s+ling\b",
    r"\basosiy\s+kanal\b",
    r"\bperona\s*tv\b",
    r"\bidub\s*tv\b",
    r"\bminxo\s*tv\b",
    r"\bmagic\s*tv\b",
    r"\bmira\s*tv\b",
    r"\bsifat\b",
    r"\bfull\s*hd\b",
    r"\bhd\b",
    r"\bfinal\b",
]

def normalize(text: str) -> str:
    s = (text or "").lower()
    s = s.replace("’", "'").replace("`", "'")
    s = re.sub(r"[@#]\w+", " ", s)
    s = re.sub(r"\b(1080p|720p|480p|4k|hdr|hevc|x265|x264|bluray|brrip|web[- ]?dl|webrip|dvdrip|cam)\b", " ", s)
    s = re.sub(r"\b(19\d{2}|20\d{2})\b", " ", s)
    s = s.replace("|", " ").replace("_", " ").replace("-", " ").replace("/", " ")
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def clean_title(raw: str) -> str:
    s = (raw or "").strip()
    s = s.replace("’", "'").replace("`", "'")

    # fayl nomlariga o'xshash axlatlarni kesish: "3 mkv", "2 mp4"
    if re.fullmatch(r"\d+\s*(mkv|mp4|avi|mov|wmv)", s.strip().lower()):
        return ""  # searchable emas

    # faqat raqam yoki "15 qism" kabi juda generic bo'lsa
    if re.fullmatch(r"\d+\s*qism", s.strip().lower()) or re.fullmatch(r"\d+", s.strip()):
        return ""

    # noise suffixlarni olib tashlash
    low = s.lower()
    for pat in NOISE_PATTERNS:
        low = re.sub(pat, " ", low, flags=re.IGNORECASE)

    # asl stringdan ham shunga yaqin tozalash uchun low'ni normalize qilib qayta "title" qilamiz
    # (yoki xohlasangiz raw'dan regex kesish ham qilamiz)
    cleaned = re.sub(r"\s+", " ", low).strip()

    # juda qisqa qolsa, bo'sh qilamiz
    if len(cleaned) < 2:
        return ""
    return cleaned

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

# movies jadvalida title_norm borligiga ishonch hosil qiling
# (agar yo'q bo'lsa, ALTER TABLE bilan qo'shish kerak bo'ladi)

rows = cur.execute("SELECT id, COALESCE(title_raw, title) FROM movies").fetchall()

updated = 0
disabled = 0

for movie_id, title_raw in rows:
    ct = clean_title(title_raw)
    if not ct:
        # searchable emas qilib belgilash uchun ustun bo'lsa:
        # cur.execute("UPDATE movies SET is_searchable=0 WHERE id=?", (movie_id,))
        disabled += 1
        continue

    tn = normalize(ct)
    cur.execute(
        "UPDATE movies SET title_norm=? WHERE id=?",
        (tn, movie_id)
    )
    updated += 1

con.commit()

# indeks: qidiruv tezlashadi
cur.execute("CREATE INDEX IF NOT EXISTS idx_movies_title_norm ON movies(title_norm)")
con.commit()

print("Updated title_norm:", updated)
print("Disabled (bad titles):", disabled)

con.close()
print("Done.")