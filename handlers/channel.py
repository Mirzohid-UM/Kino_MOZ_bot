# /home/mozcyber/PythonProject/handlers/channel.py
from aiogram import Router, types
import logging
import re

from db import add_movie

router = Router()
logger = logging.getLogger(__name__)

_HASHTAG = re.compile(r"#\w+", re.UNICODE)

def extract_title(caption: str) -> str:
    caption = (caption or "").strip()
    if not caption:
        return ""
    first = caption.splitlines()[0].strip()
    first = _HASHTAG.sub("", first).strip()
    first = re.sub(r"\s+", " ", first).strip()
    return first

@router.channel_post()
async def channel_post_handler(message: types.Message):
    if not message.caption:
        return

    # video/document shart emas — caption bo‘lsa yetadi
    title = extract_title(message.caption)
    if not title:
        return

    add_movie(title=title, message_id=message.message_id, channel_id=message.chat.id)
    logger.info("Added movie: %r (channel=%s msg=%s)", title, message.chat.id, message.message_id)
