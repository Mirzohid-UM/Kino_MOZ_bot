# /home/mozcyber/PythonProject/service/search.py
from rapidfuzz import process, fuzz
from db import get_movies_like, get_movies_limit, normalize
import logging

logger = logging.getLogger(__name__)

def find_top_movies(query: str, limit: int = 30, score_cutoff: int = 60):
    qn = normalize(query)
    candidates = get_movies_like(qn, limit=80)
    if not candidates:
        candidates = get_movies_limit(200)
        logger.info("Fallback fuzzy used for query=%r", query)

    if not candidates:
        return []

    titles = [row["title"] if hasattr(row, "keys") else row[0] for row in candidates]

    results = process.extract(
        qn,
        titles,
        scorer=fuzz.WRatio,
        limit=limit,
        score_cutoff=score_cutoff
    )

    out = []
    for title, score, idx in results:
        row = candidates[idx]
        # row: (title, message_id, channel_id) yoki sqlite Row
        message_id = row["message_id"] if hasattr(row, "keys") else row[1]
        channel_id = row["channel_id"] if hasattr(row, "keys") else row[2]
        out.append({"title": title, "message_id": int(message_id), "channel_id": int(channel_id), "score": int(score)})
    return out
