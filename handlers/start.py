import logging
from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import CommandStart

from db.access import has_access
from db.users import upsert_user
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter
import asyncio
router = Router()
logger = logging.getLogger(__name__)

ADMIN_IDS = {7040085454}

_LAST_REQ: dict[int, float] = {}
def request_access_kb() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔐 Ruxsat so‘rash", callback_data="access:request")
    return kb.as_markup()


@router.message(CommandStart())
async def start_cmd(message: types.Message):
    user = message.from_user
    user_id = int(user.id)
    username = user.username or None
    full_name = user.full_name or None

    # user profiling
    try:
        await upsert_user(user_id, username, full_name)
    except Exception:
        logger.exception("upsert_user failed (non-fatal)")

    base_text = (
        "🎬 Kino botga xush kelibsiz!\n\n"
        f"🆔 Sizning ID: {user_id}\n\n"
    )

    try:
        allowed = await has_access(user_id)
    except Exception:
        logger.exception("has_access failed, defaulting to no-access")
        allowed = False

    if allowed:
        await message.answer(
            base_text +
            "✅ Sizda ruxsat bor.\n"
            "Kino nomini yozing (masalan: Avatar 2)"
        )
        return

    await message.answer(
        base_text +
        "⛔ Sizda ruxsat yo‘q.\n"
        "Admin ruxsat bergandan keyin qidirish ishlaydi.\n\n"
        "Quyidagi tugma orqali ruxsat so‘rashingiz mumkin:",
        reply_markup=request_access_kb()
    )


@router.callback_query(F.data == "access:request")
async def access_request(call: types.CallbackQuery):
    user = call.from_user
    user_id = int(user.id)
    username = user.username or ""
    full_name = user.full_name or ""

    # cooldown 60s
    now = asyncio.get_event_loop().time()
    last = _LAST_REQ.get(user_id, 0.0)
    if now - last < 60:
        await call.answer("⏳ Biroz kuting, so‘rov allaqachon yuborilgan.", show_alert=True)
        return
    _LAST_REQ[user_id] = now

    await call.answer("✅ So‘rov yuborildi. Admin javobini kuting.", show_alert=True)

    text = "🔔 Ruxsat so‘rovi\n\n"
    text += f"👤 User: {full_name}\n"
    if username:
        text += f"@{username}\n"
    text += f"🆔 ID: {user_id}"

    for admin_id in ADMIN_IDS:
        try:
            await call.bot.send_message(admin_id, text)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await call.bot.send_message(admin_id, text)
            except Exception:
                logger.exception("Admin %s ga retrydan keyin ham yuborilmadi", admin_id)
        except (TelegramForbiddenError, TelegramBadRequest):
            logger.warning("Admin %s ga yuborilmadi (blocked/chat not found)", admin_id)
        except Exception:
            logger.exception("Admin %s ga xabar yuborib bo‘lmadi", admin_id)