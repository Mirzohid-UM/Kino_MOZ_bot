# utils/copy.py
import logging
from aiogram.exceptions import TelegramBadRequest
from utils.ttl import delete_later

logger = logging.getLogger(__name__)

_MISSING_SRC_MARKERS = (
    "message to copy not found",
    "message_id_invalid",
    "message_to_copy_not_found",
)

async def safe_copy_with_ttl(
    bot,
    chat_id: int,
    from_chat_id: int,
    message_id: int,
    ttl_sec: int = 86400,
) -> bool:
    try:
        sent = await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=from_chat_id,
            message_id=message_id,
        )
    except TelegramBadRequest as e:
        s = str(e).lower()
        if any(m in s for m in _MISSING_SRC_MARKERS):
            logger.warning(
                "copy_message missing source: from_chat_id=%s message_id=%s err=%s",
                from_chat_id, message_id, s
            )
            return False
        raise

    try:
        await delete_later(bot, chat_id, sent.message_id, seconds=ttl_sec)
    except Exception:
        logger.exception("delete_later failed (non-fatal)")

    return True
