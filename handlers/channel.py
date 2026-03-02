# handlers/channel.py
# handlers/channel.py
from aiogram import Router, types
import logging
import re
from utils.post_parser import parse_movie_post
from db.movies import add_movie_with_aliases
from db.audit import auditj
from utils.search_cache import SEARCH_CACHE
router = Router()
logger = logging.getLogger(__name__)

_HASHTAG = re.compile(r"#\w+", re.UNICODE)
_NOISE_LINE = re.compile(r"^(?:[-–—•·\s]+|➖+|$)$")
_BAD_TITLE  = re.compile(r"^\s*(\d+)\s*(mkv|mp4|avi|mov)\s*$", re.I)

def extract_title_and_aliases(caption: str) -> tuple[str, list[str]]:
    caption = (caption or "").strip()
    if not caption:
        return "", []

    for line in caption.splitlines():
        line = line.strip()
        if not line or _NOISE_LINE.match(line):
            continue

        line = _HASHTAG.sub("", line).strip()
        line = re.sub(r"\s+", " ", line).strip()

        if _BAD_TITLE.match(line):
            continue

        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p and not _BAD_TITLE.match(p)]
        if not parts:
            return "", []

        seen = set()
        uniq = []
        for p in parts:
            k = p.lower()
            if k not in seen:
                seen.add(k)
                uniq.append(p[:150])

        main_title = uniq[0][:150]
        aliases = uniq
        return main_title, aliases

    return "", []

@router.channel_post()
async def channel_post_handler(message: types.Message):
    if not (message.video or message.document):
        return
    if not message.caption:
        return

    parsed = parse_movie_post(message.caption)

    if not parsed.title:
        return

    await add_movie_with_aliases(
        title=parsed.title,
        aliases=parsed.aliases,
        message_id=message.message_id,
        channel_id=message.chat.id,
    )
    SEARCH_CACHE.clear()

    try:
        await auditj(
            actor_id=0,
            action="add_movie",
            target_id=message.message_id,
            meta={
                "channel_id": message.chat.id,
                "message_id": message.message_id,
                "title": parsed.title,
                "aliases": parsed.aliases[:10],
                "clean_text": parsed.clean_text[:300],
            },
        )
    except Exception:
        logger.exception("audit add_movie failed")

    logger.info(
        "Added movie: %r aliases=%r (channel=%s msg=%s)",
        parsed.title, parsed.aliases, message.chat.id, message.message_id
    )
