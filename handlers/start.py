import asyncio
import logging
from aiogram import Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import CommandStart

from db import has_access, upsert_user

router = Router()
logger = logging.getLogger(__name__)

ADMIN_IDS = {7040085454}

def request_access_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔐 Ruxsat so‘rash", callback_data="access:request")
    return kb.as_markup()

@router.message(CommandStart())
async def start_cmd(message: types.Message):
    user = message.from_user
    user_id = user.id
    username = user.username or ""
    full_name = user.full_name or ""

    # ✅ DB sync -> thread
    try:
        await asyncio.to_thread(upsert_user, user_id, username, full_name)
    except Exception:
        logger.exception("upsert_user failed (non-fatal)")

    base_text = (
        "🎬 Kino botga xush kelibsiz!\n\n"
        f"🆔 Sizning ID: {user_id}\n\n"
    )

    # ✅ DB sync -> thread
    try:
        allowed = await asyncio.to_thread(has_access, user_id)
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