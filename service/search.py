# /home/mozcyber/PythonProject/service/search.py
from rapidfuzz import process, fuzz
from db import get_movies_like, get_movies_limit
from db.utils import normalize
import logging

import re
logger = logging.getLogger(__name__)
EP_PATTERNS = [
    re.compile(r"\b(?:qism|q|ep|episode|seriya|серия)\s*[-:#]?\s*(\d{1,4})\b", re.I),
    re.compile(r"\bS(\d{1,2})\s*E(\d{1,4})\b", re.I),
    re.compile(r"\b(\d{1,4})\s*[- ]?\s*(?:qism|q)\b", re.I),
    # oxirida faqat 1-3 xonali raqam (2025 kabi yilni ushlamaydi)
    re.compile(r"(?:^|\s)(\d{1,3})\s*$"),
]



def extract_episode(title: str):
    t = (title or "").strip()

    # SxxExx
    m = EP_PATTERNS[1].search(t)
    if m:
        season = int(m.group(1))
        ep = int(m.group(2))
        return season, ep

    # boshqa patternlar
    for rx in (EP_PATTERNS[0], EP_PATTERNS[2], EP_PATTERNS[3]):
        m = rx.search(t)
        if m:
            return None, int(m.group(1))

    return None, None
def series_key(title: str) -> str:
    tn = normalize(title).strip()
    # eng ko‘p uchraydigan epizod/season belgilari
    tn = re.sub(r"\b(s\d{1,2}e?\d{1,4}|e\d{1,4}|qism|q|ep|episode|seriya|серия|[sS]\d{1,2})\b", " ", tn, flags=re.I)
    tn = re.sub(r"\b\d{1,4}\b", " ", tn)           # barcha 1–4 raqamli sonlarni olib tashlash
    tn = re.sub(r"[-:#×*.,!]+", " ", tn)           # keraksiz belgilarni tozalash
    tn = re.sub(r"\s+", " ", tn).strip()
    return tn
def _row_title(row):
    return row["title"] if hasattr(row, "keys") else row[0]

def _row_mid(row):
    return row["message_id"] if hasattr(row, "keys") else row[1]

def _row_cid(row):
    return row["channel_id"] if hasattr(row, "keys") else row[2]

def find_top_movies(query: str, limit: int = 30, score_cutoff: int = 70):
    qn = normalize(query).strip()
    if not qn:
        return []

    # Candidate pool (DB search)
    candidates = get_movies_like(qn, limit=120)
    if not candidates:
        candidates = get_movies_limit(300)
        logger.info("Fallback fuzzy used for query=%r", query)

    if not candidates:
        return []

    # --- SHORT QUERY GUARD (tor -> doktor muammosini kesadi) ---
    tokens = qn.split()
    if len(tokens) == 1 and len(tokens[0]) < 4:
        needle = tokens[0]

        exact = []
        word_prefix = []
        rest = []

        for row in candidates:
            t = _row_title(row) or ""
            tn = normalize(t).strip()
            words = tn.split()

            if tn == needle:
                exact.append(row)
            elif any(w == needle or w.startswith(needle) for w in words):
                # faqat so'zlar bo'yicha prefix/exact
                word_prefix.append(row)
            else:
                rest.append(row)

        ordered = exact + word_prefix + rest

        out = []
        for row in ordered[:limit]:
            out.append({
                "title": _row_title(row),
                "message_id": int(_row_mid(row)),
                "channel_id": int(_row_cid(row)),
                "score": 100,
            })
        return out
    # Fuzzy uchun titles
    titles = [_row_title(r) for r in candidates]

    # scorer tanlash: WRatio ko'pincha partial matchni kuchaytiradi
    scorer = fuzz.token_set_ratio if len(tokens) > 1 else fuzz.QRatio

    results = process.extract(
        qn,
        titles,
        scorer=scorer,
        limit=limit,
        score_cutoff=score_cutoff,
    )

    out = []
    for title, score, idx in results:
        row = candidates[idx]
        out.append({
            "title": title,
            "message_id": int(_row_mid(row)),
            "channel_id": int(_row_cid(row)),
            "score": int(score),
        })
    # ✅ agar ko'p natija bir serialga o'xshasa, ep bo'yicha sort qilamiz
    if out:
        qkey = series_key(query)
        if qkey:
            same_series = [x for x in out if series_key(x["title"]) == qkey]
            if len(same_series) >= 3:  # kamida 3 ta bo'lsa serial deb olamiz
                def k(x):
                    s, e = extract_episode(x["title"])
                    # season yo'q bo'lsa 0 deb olamiz, ep yo'q bo'lsa katta son qilib oxirga tushiramiz
                    return (s or 0, e if e is not None else 10 ** 9, len(x["title"]))

                out.sort(key=k)
    return out