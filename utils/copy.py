# utils/copy.py
import asyncio
import logging
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

from utils.ttl import delete_later

logger = logging.getLogger(__name__)

_MISSING_SRC_MARKERS = (
    "message to copy not found",
    "message_id_invalid",
    "message_to_copy_not_found",
    "message not found",
)

async def safe_copy_with_ttl(
    bot,
    chat_id: int,
    from_chat_id: int,
    message_id: int,
    ttl_sec: int = 86400,
    *,
    protect: bool = True,
    disable_notification: bool = False,
) -> bool:
    sent = None

    # 1) protect_content bilan urinib ko'ramiz
    if protect:
        try:
            sent = await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=from_chat_id,
                message_id=message_id,
                protect_content=True,
                disable_notification=disable_notification,
            )
        except TypeError:
            logger.info("copy_message: protect_content not supported, falling back")
        except TelegramBadRequest as e:
            s = str(e).lower()
            if any(m in s for m in _MISSING_SRC_MARKERS):
                logger.warning(
                    "copy_message missing source: from_chat_id=%s message_id=%s err=%s",
                    from_chat_id, message_id, s
                )
                return False
            raise
        except TelegramAPIError:
            logger.exception("copy_message failed with TelegramAPIError (protect path)")
            raise

    # 2) fallback copy
    if sent is None:
        try:
            sent = await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=from_chat_id,
                message_id=message_id,
                disable_notification=disable_notification,
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
        except TelegramAPIError:
            logger.exception("copy_message failed with TelegramAPIError (fallback path)")
            raise

    # 3) TTL delete -> background task (MUHIM!)
    try:
        asyncio.create_task(
            delete_later(bot, chat_id, sent.message_id, seconds=ttl_sec)
        )
    except Exception:
        logger.exception("delete_later scheduling failed (non-fatal)")

    return True