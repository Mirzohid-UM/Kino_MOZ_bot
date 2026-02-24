# /home/mozcyber/PythonProject/handlers/channel.py
from aiogram import Router, types
import logging
import re
import inspect
import asyncio
from db import add_movie,add_alias
from db import auditj

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
        if not line:
            continue
        if _NOISE_LINE.match(line):
            continue

        line = _HASHTAG.sub("", line).strip()
        line = re.sub(r"\s+", " ", line).strip()

        # "3 mkv" / "2 mp4" kabi bo'lsa qabul qilmaymiz
        if _BAD_TITLE.match(line):
            continue

        # ✅ Alias: A | B | C
        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p and not _BAD_TITLE.match(p)]
        if not parts:
            return "", []

        # dublikatlarni olib tashlash (case-insensitive)
        seen = set()
        uniq = []
        for p in parts:
            k = p.lower()
            if k not in seen:
                seen.add(k)
                uniq.append(p[:150])

        main_title = uniq[0]
        aliases = uniq  # main ham alias sifatida kirsin (muammo qilmaydi)
        return main_title, aliases

    return "", []

async def _maybe_await(fn, *args, **kwargs):
    res = fn(*args, **kwargs)
    if inspect.isawaitable(res):
        return await res
    return res

@router.channel_post()
async def channel_post_handler(message: types.Message):
    # faqat kino fayllari (video yoki document) kelganda DBga yozamiz
    if not (message.video or message.document):
        return

    if not message.caption:
        return


    main_title, aliases = extract_title_and_aliases(message.caption)
    if not main_title:
        return

    main_title = main_title[:150]  # optional safety

    await add_movie(
        title=main_title,
        message_id=message.message_id,
        channel_id=message.chat.id,
    )

    for a in aliases:
        await add_alias(
            alias=a,
            message_id=message.message_id,
            channel_id=message.chat.id,
        )

    try:
        await _maybe_await(
            auditj,
            actor_id=0,
            action="add_movie",
            target_id=message.message_id,
            meta_obj={
                "channel_id": message.chat.id,
                "message_id": message.message_id,
                "title": main_title,
            }
        )
    except Exception:
        logger.exception("audit add_movie failed")

    logger.info("Added movie: %r aliases=%r (channel=%s msg=%s)",
                main_title, aliases, message.chat.id, message.message_id)