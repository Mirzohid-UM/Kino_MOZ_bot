from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class ParsedPost:
    title: str
    tili: str
    janri: str
    aliases: List[str]
    clean_text: str


# ------------------------------
# 1) Noise / promo detection
# ------------------------------
_PROMO_WORDS = {
    "premyera", "premiera", "premiere",
    "super premyera", "superpremyera",
    "bizdapremyera", "bizda premyera",
    "top film", "top_film", "topfilm",
    "kino vaqti", "kinofilm vaqti",
    "yangi kino", "yangikino",
    "bizga qoshiling", "bizga qo'shiling",
    "bizdan uzoqlashmang",
}

# link/channel/reklama/muloqot satrlari
_NOISE_PATTERNS = [
    r"http[s]?://",
    r"\bt\.me/\S+",
    r"\btelegram\.me/\S+",
    r"@\w+",
    r"\bgold\s+kinolar\b",
    r"\bkinolar\b",
    r"\bmultik\b",
    r"\bbot\b",
    r"\bobuna\b",
    r"\breklama\b",
    r"\bjoin\b",
    r"\bkanal\b",
]

# faqat bezak/ajratgich satrlar
_NOISE_LINE = re.compile(r"^(?:[-–—•·\s]+|➖+|_+|=+|\.+|,)+$")

# hashtag-only line: #Top_Film, #BizdaPremyera, #Ujas ...
_HASHTAG_ONLY = re.compile(r"^(?:\s*#\w+\s*){1,20}$", re.UNICODE)

# premyera line variants
_PREMYERA_LINE = re.compile(r"^\s*(?:🔥\s*)?(?:super\s*)?premyera\b.*$", re.I)


def _norm_spaces(s: str) -> str:
    return re.sub(r"\s{2,}", " ", (s or "").strip())


def _strip_quotes(s: str) -> str:
    return (s or "").strip().strip('"“”„‟’‘‹›«»')


def _is_noise_line(line: str) -> bool:
    s = (line or "").strip()
    if not s:
        return True
    low = s.lower()

    if _NOISE_LINE.match(s):
        return True
    if _HASHTAG_ONLY.match(s):
        # #Top_Film kabi — title emas
        return True
    if _PREMYERA_LINE.match(low):
        return True

    # promo keywordlar (tozalangan ko‘rinishda ham tekshiramiz)
    low2 = low.replace("#", "").replace("_", " ").strip()
    if low2 in _PROMO_WORDS:
        return True

    for p in _NOISE_PATTERNS:
        if re.search(p, low):
            return True

    return False


# ------------------------------
# 2) Title cleaning
# ------------------------------

# Title satrini boshidan kesiladigan dekor/emojilar (katta ro‘yxat)
_LEADING_DECOR = re.compile(
    r"""^[\s\-\–\—•·➖➺➡️👉👇⭐✨🔥❄️📌📍🗣📄🎬🎞🎥🎦💽📀📆📲💾🌏🌎🌍🇺🇿🇷🇺🇺🇸⚔️]+""",
    re.UNICODE,
)

# Title uchun “kalit prefikslar”
_TITLE_PREFIX = re.compile(
    r"""^\s*(?:
        kino|film|serial|multfilm|multik|nomi|film\s*nomi|kino\s*nomi|name|title
    )\s*[:：\-–—]\s*""",
    re.I | re.X,
)

# Title ichida olib tashlanadigan “meta”lar
_YEAR_PARENS = re.compile(r"\(\s*\d{4}\s*(?:[-–—]?\s*(?:yil|год))?\s*\)", re.I)
_EP_PARENS = re.compile(r"\(\s*\d+\s*[-–—]?\s*qism\s*\)", re.I)
_EP_INLINE = re.compile(r"\b\d+\s*[-–—]?\s*qism\b", re.I)

_QUALITY = re.compile(
    r"\b(480p|720p|1080p|2160p|4k|hdrip|bdrip|webrip|web[- ]?dl|bluray|full\s*hd|hd)\b",
    re.I,
)

# title ichida "O'zbek tilida" / "Uzbek tilida" kabi metalar titlega qo‘shilib ketmasin
_LANG_META = re.compile(r"\b(o['’]zbek|uzbek|rus|english|turk)\s+tilida\b.*$", re.I)

# "TV TARJIMA" / "TARJIMA" ham title meta, title oxiridan kesamiz
_TARJIMA_META = re.compile(r"\b(tv\s*tarjima|tarjima)\b.*$", re.I)

# "Kino:" kabi prefiks ba'zan qolib ketadi — title ichidan ham tozalaymiz
_INNER_PREFIX = re.compile(r"^\s*(kino|film)\s*:\s*", re.I)


def _clean_title_candidate(s: str) -> str:
    s = _norm_spaces(s)
    s = _strip_quotes(s)

    # dekor
    s = _LEADING_DECOR.sub("", s).strip()

    # prefikslar
    s = _TITLE_PREFIX.sub("", s).strip()
    s = _INNER_PREFIX.sub("", s).strip()

    # metalarni title’dan chiqarish
    s = _YEAR_PARENS.sub("", s)
    s = _EP_PARENS.sub("", s)
    s = _EP_INLINE.sub("", s)
    s = _QUALITY.sub("", s)

    s = _TARJIMA_META.sub("", s)
    s = _LANG_META.sub("", s)

    # ortiqcha qavs/bo‘shliq
    s = _norm_spaces(s)
    s = s.strip(" -–—•·➖:|")

    return _norm_spaces(s)


def _looks_like_bad_title(s: str) -> bool:
    # faqat "PREMYERA" yoki shunga o'xshash bo'lsa
    if not s:
        return True
    if _PREMYERA_LINE.match(s.lower()):
        return True
    # faqat format/extension bo'lsa
    if re.fullmatch(r"\d+\s*(mkv|mp4|avi|mov)", s, re.I):
        return True
    return False


def _extract_title(lines: List[str]) -> str:
    # 1) Avval "Nomi: ..." / "Film nomi: ..." bor satrlarni qidiramiz
    for ln in lines:
        if _is_noise_line(ln):
            continue
        cand = _clean_title_candidate(ln)

        # "Nomi:" bo'lsa juda ishonchli: lekin regexni satrning originalidan olamiz
        # agar prefiks mavjud bo'lsa
        if _TITLE_PREFIX.search(_LEADING_DECOR.sub("", ln.strip())):
            if not _looks_like_bad_title(cand):
                return cand

    # 2) Keyin birinchi “real” satr (noise emas)
    for ln in lines:
        if _is_noise_line(ln):
            continue

        # "1chi kino Ip Man 1" -> "Ip Man 1"
        ln2 = re.sub(r"^\s*\d+\s*chi\s*kino\s+", "", ln, flags=re.I)
        cand = _clean_title_candidate(ln2)

        if _looks_like_bad_title(cand):
            continue

        return cand

    return ""


# ------------------------------
# 3) Key-value parse (Tili / Janri)
# ------------------------------
_KEYVAL = re.compile(r"^\s*([A-Za-zÀ-ÿʻʼ’\u0400-\u04FF]+)\s*[:：]\s*(.+)\s*$", re.UNICODE)


def _parse_key_value(line: str) -> Optional[Tuple[str, str]]:
    if not line:
        return None
    s = _LEADING_DECOR.sub("", line.strip()).strip()
    if not s:
        return None

    m = _KEYVAL.match(s)
    if m:
        key = m.group(1).strip().lower()
        val = m.group(2).strip()
        return key, val

    # Colon'siz "O'zbek tilida" satrlarini ham tili deb olamiz
    low = s.lower()
    if "tilida" in low and not any(x in low for x in ("davlat", "yil", "format", "manba", "reyting", "sifat")):
        return "tili", s.strip()

    return None


def _normalize_genres(val: str) -> str:
    v = (val or "").replace("#", " ")
    v = re.sub(r"[,\.;]+", " ", v)
    v = _norm_spaces(v)
    return v


# ------------------------------
# 4) Alias builder (kuchli)
# ------------------------------
def _build_aliases(title: str) -> List[str]:
    if not title:
        return []

    aliases = set()

    t = _norm_spaces(title)
    aliases.add(t)

    # "/" -> ikkala tomonni alias qilamiz
    if "/" in t:
        for p in [x.strip() for x in t.split("/") if x.strip()]:
            aliases.add(p)

    # ":" -> o'ng tomoni alias
    if ":" in t:
        left, right = t.split(":", 1)
        right = right.strip()
        if right:
            aliases.add(right)

    # qo'shimcha normalizatsiya: 1+1 -> 1 plus 1
    aliases.add(_norm_spaces(t.replace("+", " plus ")))

    # «…» va "…" bo'lgan holatlar
    aliases.add(_strip_quotes(t))

    # Title case varianti (display uchun foydali bo‘lishi mumkin)
    # (normalize qidiruvda hal bo‘ladi, lekin ko‘rsatishda chiroyli)
    if len(t) <= 80:
        aliases.add(t.title())

    # uniq + tozalash
    out = []
    seen = set()
    for a in aliases:
        a2 = _clean_title_candidate(a)  # alias ham toza bo‘lsin
        if not a2:
            continue
        k = a2.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(a2[:150])

    return out


# ------------------------------
# 5) Main parse
# ------------------------------
def parse_movie_post(text: str) -> ParsedPost:
    if not text:
        return ParsedPost(title="", tili="", janri="", aliases=[], clean_text="")

    # bo‘sh satrlarni tashlaymiz, lekin tartib saqlansin
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    title = _extract_title(lines)

    tili = ""
    janri = ""

    for ln in lines:
        if _is_noise_line(ln):
            continue

        kv = _parse_key_value(ln)
        if not kv:
            continue

        key, val = kv
        k = key.lower()

        if k in ("til", "tili"):
            tili = _norm_spaces(val)
        elif k in ("janr", "janri"):
            janri = _normalize_genres(val)

    aliases = _build_aliases(title)

    # clean_text: faqat title + tili + janri
    out = []
    if title:
        out.append(title)
    meta = []
    if tili:
        meta.append(f"Tili: {tili}")
    if janri:
        meta.append(f"Janri: {janri}")
    if meta:
        out.append("\n".join(meta))
    clean_text = "\n\n".join(out).strip()

    return ParsedPost(
        title=title,
        tili=tili,
        janri=janri,
        aliases=aliases,
        clean_text=clean_text,
    )
