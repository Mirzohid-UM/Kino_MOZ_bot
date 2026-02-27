from __future__ import annotations

import re
import logging
import asyncio
from typing import Any

from rapidfuzz import process, fuzz

from db.movies import get_movies_like, get_movies_limit  # ✅ aniq moduldan
from db.utils import normalize

logger = logging.getLogger(__name__)

EP_PATTERNS = [
    re.compile(r"\b(?:qism|q|ep|episode|seriya|серия)\s*[-:#]?\s*(\d{1,4})\b", re.I),
    re.compile(r"\bS(\d{1,2})\s*E(\d{1,4})\b", re.I),
    re.compile(r"\b(\d{1,4})\s*[- ]?\s*(?:qism|q)\b", re.I),
    re.compile(r"(?:^|\s)(\d{1,3})\s*$"),
]


def extract_episode(title: str | None) -> tuple[int | None, int | None]:
    t = (title or "").strip()
    if not t:
        return None, None

    m = EP_PATTERNS[1].search(t)  # SxxExx
    if m:
        return int(m.group(1)), int(m.group(2))

    for rx in (EP_PATTERNS[0], EP_PATTERNS[2], EP_PATTERNS[3]):
        m = rx.search(t)
        if m:
            return None, int(m.group(1))

    return None, None


def series_key(title: str | None) -> str:
    if not title:
        return ""
    tn = normalize(title).strip()
    tn = re.sub(r"\b(s\d{1,2}e?\d{1,4}|e\d{1,4}|qism|q|ep|episode|seriya|серия|[sS]\d{1,2})\b", " ", tn, flags=re.I)
    tn = re.sub(r"\b\d{1,4}\b", " ", tn)
    tn = re.sub(r"[-:#×*.,!]+", " ", tn)
    tn = re.sub(r"\s+", " ", tn).strip()
    return tn


def _row_title(row: Any) -> str:
    if hasattr(row, "keys"):
        return (row.get("title") or "")
    if isinstance(row, (list, tuple)) and row:
        return row[0] or ""
    return ""


def _row_mid(row: Any) -> int:
    if hasattr(row, "keys"):
        return int(row.get("message_id") or 0)
    if isinstance(row, (list, tuple)) and len(row) > 1:
        return int(row[1] or 0)
    return 0


def _row_cid(row: Any) -> int:
    if hasattr(row, "keys"):
        return int(row.get("channel_id") or 0)
    if isinstance(row, (list, tuple)) and len(row) > 2:
        return int(row[2] or 0)
    return 0


async def find_top_movies(query: str, limit: int = 30, score_cutoff: int = 70) -> list[dict]:
    qn = normalize(query).strip()
    if not qn:
        return []

    # ✅ DB async
    candidates = await get_movies_like(qn, limit=120)
    if not candidates:
        tokens = qn.split()
        if len(tokens) == 1 and len(tokens[0]) < 4:
            return []  # ✅ 1-3 harfga latest fallback yo‘q
        candidates = await get_movies_limit(2000)
        logger.info("Fallback fuzzy used for query=%r", query)

    if not candidates:
        logger.warning("SEARCH db_like empty -> fallback_limit=300 query=%r qn=%r", query, qn)
        candidates = await get_movies_limit(300)
        logger.info("SEARCH fallback_limit: rows=%d", len(candidates))

    logger.info("SEARCH in: query=%r", query)
    qn = normalize(query).strip()
    logger.info("SEARCH norm: qn=%r len=%d", qn, len(qn))
    tokens = qn.split()
    logger.info("SEARCH tokens: %s", tokens)

    # --- SHORT QUERY GUARD ---
    if len(tokens) == 1 and len(tokens[0]) < 4:
        needle = tokens[0]
        exact, word_prefix = [], []

        for row in candidates:
            tn = normalize(_row_title(row)).strip()
            words = tn.split()

            if tn == needle:
                exact.append(row)
            elif any(w == needle or w.startswith(needle) for w in words):
                word_prefix.append(row)

        ordered = exact + word_prefix

        # ✅ MUHIM: hech narsa topilmasa, oxirgilarni qaytarmaymiz
        if not ordered:
            return []

        return [
            {
                "title": _row_title(row),
                "message_id": _row_mid(row),
                "channel_id": _row_cid(row),
                "score": 100,
            }
            for row in ordered[:limit]
        ]
    titles = [_row_title(r) for r in candidates]
    scorer = fuzz.token_set_ratio if len(tokens) > 1 else fuzz.QRatio

    # ✅ CPU ishni threadga chiqaramiz (event loop bloklanmasin)
    results = await asyncio.to_thread(
        process.extract,
        qn,
        titles,
        scorer=scorer,
        limit=limit,
        score_cutoff=score_cutoff,
    )

    out: list[dict] = []
    for title, score, idx in results:
        row = candidates[idx]
        out.append(
            {
                "title": title,
                "message_id": _row_mid(row),
                "channel_id": _row_cid(row),
                "score": int(score),
            }
        )

    # serial sort
    if out:
        qkey = series_key(query)
        if qkey:
            same_series = [x for x in out if series_key(x["title"]) == qkey]
            if len(same_series) >= 3:
                def sort_key(x: dict):
                    s, e = extract_episode(x["title"])
                    return (s or 0, e if e is not None else 10**9, len(x["title"]))

                out.sort(key=sort_key)

    return out