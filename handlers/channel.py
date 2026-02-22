# /home/mozcyber/PythonProject/handlers/channel.py
from aiogram import Router, types
import logging
import re
import inspect
import asyncio
from db import add_movie
from db import auditj

router = Router()
logger = logging.getLogger(__name__)

_HASHTAG = re.compile(r"#\w+", re.UNICODE)
_NOISE_LINE = re.compile(r"^(?:[-–—•·\s]+|➖+|$)$")
_BAD_TITLE  = re.compile(r"^\s*(\d+)\s*(mkv|mp4|avi|mov)\s*$", re.I)

def extract_title(caption: str) -> str:
    caption = (caption or "").strip()
    if not caption:
        return ""

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

        return line

    return ""

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

    title = extract_title(message.caption)
    if not title:
        return

    title = title[:150]  # optional safety

    await asyncio.to_thread(
        add_movie,
        title=title,
        message_id=message.message_id,
        channel_id=message.chat.id,
    )
    try:
        auditj(
            actor_id=0,
            action="add_movie",
            target_id=message.message_id,
            meta_obj={
                "channel_id": message.chat.id,
                "message_id": message.message_id,
                "title": title,
            }
        )
    except Exception:
        logger.exception("audit add_movie failed")

    logger.info("Added movie: %r (channel=%s msg=%s)", title, message.chat.id, message.message_id)