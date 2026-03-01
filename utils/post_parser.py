from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


@dataclass
class ParsedPost:
    title: str
    tili: str
    janri: str
    aliases: List[str]
    clean_text: str


PROMO_WORDS = {
    "premyera", "premiera", "premiere",
    "super premyera", "superpremyera",
    "top_film", "topfilm",
    "bizdapremyera", "bizda premyera",
    "yangi kino", "yangikino",
    "gold kinolar",
    "bizda ujas kino", "bizdaujaskino",
}

NOISE_PATTERNS = [
    r"http[s]?://",
    r"t\.me/",
    r"telegram\.me/",
    r"@\w+",
    r"\bgold kinolar\b",
    r"\bbizdan uzoqlashmang\b",
    r"\bmultik bot\b",
    r"\bkino bot\b",
]


def _is_noise_line(line: str) -> bool:
    low = line.lower().strip()
    if not low:
        return True

    if re.fullmatch(r"(#\w+[\s]*){1,30}", low):
        return True

    if re.fullmatch(r"(super\s*)?premyera[\W_]*", low):
        return True

    for p in NOISE_PATTERNS:
        if re.search(p, low):
            return True

    normalized = low.replace("#", "").replace("_", " ").strip()
    if normalized in PROMO_WORDS:
        return True

    return False


def _strip_leading_decor(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^[\s\-\–\—\•\·\➖\➺\➡️\🎬\🎞️\🎥\❄️\🔥\⭐️\✨\📌\🌏\🌎\🇺🇿\⚔\📆\💾\📲]+", "", s)
    return s.strip()


def _remove_quality_and_year(title: str) -> str:
    t = title.strip()

    # (2011), (2018-yil), (2020 ) -> remove
    t = re.sub(r"\(\s*\d{4}[^)]*\)", "", t)

    # [HD] kabi
    t = re.sub(r"\[[^\]]*\]", "", t)

    # 480p/720p/1080p, WEB-DL, HDRip, BluRay, Full HD, TV TARJIMA
    t = re.sub(
        r"\b(480p|720p|1080p|2160p|4k|web[- ]?dl|webrip|hdrip|bdrip|bluray|full\s*hd|hd|tv\s*tarjima)\b",
        "",
        t,
        flags=re.I,
    )

    t = re.sub(r"\s{2,}", " ", t).strip()
    return t


def _extract_title(lines: List[str]) -> str:
    # 1) Nomi: bo'lsa prioritet
    for ln in lines:
        s = _strip_leading_decor(ln)
        if not s:
            continue
        m = re.match(r"^(?:nomi|name|title)\s*:\s*(.+)$", s, flags=re.I)
        if m:
            title = m.group(1).strip().strip('"“”‘’\'')
            return _remove_quality_and_year(title)

    # 2) bo'lmasa birinchi real title
    for ln in lines:
        s = _strip_leading_decor(ln)
        if not s:
            continue
        if _is_noise_line(s):
            continue

        # "1chi kino Ip Man 1" -> "Ip Man 1"
        s = re.sub(r"^\s*\d+\s*chi\s*kino\s+", "", s, flags=re.I).strip()

        # qo'shtirnoq
        s = s.strip().strip('"“”‘’\'')

        s = _remove_quality_and_year(s)
        return s

    return ""


def _parse_key_value(line: str):
    raw = line.strip()
    if not raw:
        return None
    s = _strip_leading_decor(raw)
    if not s:
        return None

    # Key: value
    m = re.match(r"^([A-Za-zÀ-ÿʻʼ’\u0400-\u04FF]+)\s*:\s*(.+)$", s)
    if m:
        return m.group(1).strip().lower(), m.group(2).strip()

    # Colon'siz til satri: "O'zbek tilida"
    low = s.lower()
    if "tilida" in low and not any(x in low for x in ("davlat", "yil", "format", "manba", "reyting", "sifat")):
        return "tili", s.strip()

    return None


def _normalize_genres(val: str) -> str:
    v = val.replace("#", " ")
    v = re.sub(r"\s{2,}", " ", v).strip()
    return v


def _build_aliases(title: str) -> List[str]:
    aliases = set()
    t = title.strip()
    if not t:
        return []

    aliases.add(t)

    # "/" bo'lsa bo'lib alias qilamiz
    if "/" in t:
        for p in [x.strip() for x in t.split("/")]:
            if p:
                aliases.add(p)

    # ":" bo'lsa o'ng tomonni alias qilamiz (1+1: ...)
    if ":" in t:
        _, right = t.split(":", 1)
        right = right.strip()
        if right:
            aliases.add(right)

    # "+" normalizatsiya
    aliases.add(re.sub(r"\s{2,}", " ", t.replace("+", " plus ")).strip())

    return [a for a in aliases if a]


def parse_movie_post(text: str) -> ParsedPost:
    if not text:
        return ParsedPost(title="", tili="", janri="", aliases=[], clean_text="")

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
        if key in ("til", "tili"):
            tili = val.strip()
        elif key in ("janr", "janri"):
            janri = _normalize_genres(val)

    aliases = _build_aliases(title)

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

    return ParsedPost(title=title, tili=tili, janri=janri, aliases=aliases, clean_text=clean_text)
