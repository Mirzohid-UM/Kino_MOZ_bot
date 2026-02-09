import asyncio
import logging
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)

async def delete_later(bot, chat_id: int, message_id: int, seconds: int = 86400):
    await asyncio.sleep(seconds)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramBadRequest as e:
        # allaqachon o'chirilgan / vaqt cheklovi / x.k.
        logger.warning(f"delete_message failed chat_id={chat_id} message_id={message_id}: {e}")
    except Exception:
        logger.exception("delete_message unexpected error")
