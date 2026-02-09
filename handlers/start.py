from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

from db import grant_access, has_access,upsert_user

router = Router()
logger = logging.getLogger(__name__)

ADMIN_IDS = {7040085454}  # sizning ID


def request_access_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔐 Ruxsat so‘rash", callback_data="access:request")
    return kb.as_markup()


@router.message(F.text == "/start")
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    upsert_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.full_name
    )

    # ID ni doim ko'rsatamiz
    base_text = (
        "🎬 Kino botga xush kelibsiz!\n\n"
        f"🆔 Sizning ID: {user_id}\n\n"
    )

    # Access bo'lsa — qidirishni aytamiz
    if has_access(user_id):
        await message.answer(
            base_text +
            "✅ Sizda ruxsat bor.\n"
            "Kino nomini yozing (masalan: Avatar 2)"
        )
        return

    # Access bo'lmasa — tushuntiramiz
    await message.answer(
        base_text +
        "⛔ Sizda ruxsat yo‘q.\n"
        "Admin ruxsat bergandan keyin qidirish ishlaydi.\n\n"
        "Quyidagi tugma orqali ruxsat so‘rashingiz mumkin:",
        reply_markup=request_access_kb()
    )



