from __future__ import annotations
import time
import datetime
import logging
from typing import Optional

from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db.access import grant_access
from db.users import ensure_user_exists
from db.audit import auditj

router = Router()
logger = logging.getLogger(__name__)

ADMIN_IDS = {7040085454, 123456789}  # misol: admin 1 va admin 2

# pending_requests[user_id] = {"message_id": x, "chat_id": y, "days": z}
pending_requests: dict[int, dict] = {}

# Tugmalar
def request_kb(user_id: int, days: int):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Ruxsat ber ({days} kun)", callback_data=f"grant_{user_id}_{days}")],
        [InlineKeyboardButton(text="❌ Rad etildi", callback_data=f"deny_{user_id}")]
    ])
    return kb


# Foydalanuvchi ruxsat so‘rov yuborganida
@router.message(F.text.startswith("/request_access"))
async def request_access(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /request_access <days>")
        return
    try:
        days = int(parts[1])
        if days <= 0:
            await message.answer("❌ Kunlar 0 dan katta bo‘lishi kerak.")
            return
    except ValueError:
        await message.answer("❌ Noto‘g‘ri format")
        return

    user_id = message.from_user.id
    await ensure_user_exists(user_id)
    pending_requests[user_id] = {
        "days": days,
        "admin_msgs": []
    }

    for admin_id in ADMIN_IDS:
        try:
            msg = await message.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🔔 Yangi ruxsat so‘rovi\n\n"
                    f"👤 Ism: {message.from_user.full_name}\n"
                    f"🧾 Username: @{message.from_user.username or 'none'}\n"
                    f"🆔 User ID: {user_id}\n"
                    f"Necha kun: {days}"
                ),
                reply_markup=request_kb(user_id, days)
            )

            # 🔥 MUHIM: message_id saqlaymiz
            pending_requests[user_id]["admin_msgs"].append((admin_id, msg.message_id))

        except Exception as e:
            logger.exception("admin=%s xato: %s", admin_id, e)

# Admin tugmani bosganda
@router.callback_query(F.data.startswith("grant_"))
async def grant_cb(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Siz admin emassiz.", show_alert=True)
        return

    _, user_id, days = callback.data.split("_")
    user_id = int(user_id)
    days = int(days)

    req = pending_requests.get(user_id)

    if not req:
        await callback.answer("❌ Allaqachon bajarilgan", show_alert=True)
        return

    # 🔥 faqat birinchi admin ishlaydi
    pending_requests.pop(user_id)

    expires_at = await grant_access(
        user_id,
        days=days,
        admins=[callback.from_user.id]
    )

    # 🔥 BARCHA adminlarda tugmalarni o‘chirish
    for admin_id, msg_id in req["admin_msgs"]:
        try:
            await callback.bot.edit_message_reply_markup(
                chat_id=admin_id,
                message_id=msg_id,
                reply_markup=None
            )
        except Exception:
            pass

    # 🔥 BARCHA adminlarda textni yangilash
    dt = datetime.datetime.fromtimestamp(expires_at)

    for admin_id, msg_id in req["admin_msgs"]:
        try:
            await callback.bot.edit_message_text(
                chat_id=admin_id,
                message_id=msg_id,
                text=(
                    f"✅ Ruxsat berildi\n\n"
                    f"🆔 User: {user_id}\n"
                    f"👤 Admin: {callback.from_user.id}\n"
                    f"📅 {days} kun\n"
                    f"🕒 {dt:%Y-%m-%d %H:%M}"
                )
            )
        except Exception:
            pass

    await callback.answer("✅ Ruxsat berildi")


@router.callback_query(F.data.startswith("deny_"))
async def deny_cb(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    _, user_id = callback.data.split("_")
    user_id = int(user_id)

    req = pending_requests.pop(user_id, None)

    if not req:
        await callback.answer("❌ Allaqachon yopilgan", show_alert=True)
        return

    for admin_id, msg_id in req["admin_msgs"]:
        try:
            await callback.bot.edit_message_text(
                chat_id=admin_id,
                message_id=msg_id,
                text="❌ Ruxsat rad etildi"
            )
        except Exception:
            pass

    await callback.answer("❌ Rad etildi")