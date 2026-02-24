# db/utils.py
import re
_ws = re.compile(r"\s+")
_punct = re.compile(r"[^\w\s]", re.UNICODE)

def normalize(s: str) -> str:
    s = (s or "").lower()

    # apostroflarni bir xil qilish
    s = s.replace("’", "'").replace("`", "'").replace("ʻ", "'")

    # kirill → lotin minimal mapping (kino bot uchun yetarli)
    s = s.replace("ё", "e").replace("й", "i")

    # punktuatsiyani space ga aylantiramiz
    s = _punct.sub(" ", s)

    # space’larni tekislaymiz
    s = _ws.sub(" ", s).strip()
    return s