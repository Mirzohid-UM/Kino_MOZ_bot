# /home/mozcyber/PythonProject/service/search.py
from rapidfuzz import process, fuzz
from db import get_movies_like, get_movies_limit
from db.core import normalize
import logging

logger = logging.getLogger(__name__)

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
    return out