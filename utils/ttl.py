import asyncio
import logging
import time
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
try:
    from aiogram.exceptions import TelegramRetryAfter
except Exception:  # ImportError yoki boshqa
    TelegramRetryAfter = None  # aiogram 3 da bor

logger = logging.getLogger(__name__)

# delete qilishga urinishda "normal" deb qabul qilinadigan xabarlar
_SOFT_BADREQUEST_MARKERS = (
    "message to delete not found",
    "message_id_invalid",
    "message can't be deleted",
    "message cant be deleted",
    "message is too old",
    "chat not found",
)

def _is_soft_badrequest(e: TelegramBadRequest) -> bool:
    s = str(e).lower()
    return any(m in s for m in _SOFT_BADREQUEST_MARKERS)

async def _sleep_chunked(total_seconds: int, *, chunk: int = 60) -> None:
    """
    total_seconds ni bo'laklab uxlaydi.
    Bu uzoq TTL'larda event loop cancel/restart signal'larini "yumshoq" qayta ishlashga yordam beradi.
    """
    remaining = int(total_seconds)
    while remaining > 0:
        step = min(chunk, remaining)
        await asyncio.sleep(step)
        remaining -= step

async def delete_later(
    bot,
    chat_id: int,
    message_id: int,
    seconds: int = 86400,
    *,
    max_delete_retries: int = 5,
    sleep_chunk: int = 60,
) -> bool:
    """
    TTL bo'yicha xabar o'chiradi.
    Return:
      True  -> delete success
      False -> delete qilinmadi (soft fail yoki retries tugadi)

    Eslatma: bu runtime ichida mustahkam. Restart bo'lsa TTL yo'qoladi.
    """
    if seconds < 0:
        seconds = 0

    due_at = time.time() + seconds
    logger.info("TTL scheduled: chat=%s msg=%s in %ss", chat_id, message_id, seconds)

    # 1) deadline'ga yetguncha bo'laklab kutamiz
    try:
        while True:
            now = time.time()
            remaining = int(due_at - now)
            if remaining <= 0:
                break
            await _sleep_chunked(remaining, chunk=sleep_chunk)
    except asyncio.CancelledError:
        logger.warning("TTL cancelled: chat=%s msg=%s", chat_id, message_id)
        return False

    # 2) delete qilish: retry + floodwait handling
    attempt = 0
    while attempt < max_delete_retries:
        attempt += 1
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.info("TTL deleted: chat=%s msg=%s (attempt=%s)", chat_id, message_id, attempt)
            return True


        except Exception as e:
            if TelegramRetryAfter is not None and isinstance(e, TelegramRetryAfter):
                wait_for = int(getattr(e, "retry_after", 1)) + 1
                logger.warning(
                    "TTL delete floodwait: chat=%s msg=%s retry_after=%ss (attempt=%s/%s)",
                    chat_id, message_id, wait_for, attempt, max_delete_retries
                )
                try:
                    await asyncio.sleep(wait_for)
                except asyncio.CancelledError:
                    logger.warning("TTL cancelled during floodwait: chat=%s msg=%s", chat_id, message_id)
                    return False
                continue
            raise

        except TelegramBadRequest as e:
            # bu yerda ko'p “normal” holatlar bor: already deleted, too old, can't delete...
            if _is_soft_badrequest(e):
                logger.info(
                    "TTL delete soft-fail: chat=%s msg=%s err=%s",
                    chat_id, message_id, str(e)
                )
                return False

            # boshqa BadRequest - retry qilib ko'ramiz (ba'zan vaqtinchalik)
            logger.warning(
                "TTL delete badrequest: chat=%s msg=%s err=%s (attempt=%s/%s)",
                chat_id, message_id, str(e), attempt, max_delete_retries
            )
            await asyncio.sleep(min(2 * attempt, 10))
            continue

        except TelegramAPIError as e:
            # network/timeouts va boshqa API xatolari bo'lishi mumkin
            logger.warning(
                "TTL delete apierror: chat=%s msg=%s err=%s (attempt=%s/%s)",
                chat_id, message_id, str(e), attempt, max_delete_retries
            )
            await asyncio.sleep(min(2 * attempt, 10))
            continue

        except Exception:
            logger.exception(
                "TTL delete unexpected error: chat=%s msg=%s (attempt=%s/%s)",
                chat_id, message_id, attempt, max_delete_retries
            )
            await asyncio.sleep(min(2 * attempt, 10))
            continue

    logger.error("TTL delete failed after retries: chat=%s msg=%s", chat_id, message_id)
    return False