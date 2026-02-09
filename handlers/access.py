import time
import logging
from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import grant_access

router = Router()
logger = logging.getLogger(__name__)

ADMIN_IDS = {7040085454}  # sizning telegram ID

def make_request_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔐 Ruxsat so‘rash", callback_data="access:request")
    return kb.as_markup()

def make_admin_approve_kb(user_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Approve (1 kun)", callback_data=f"access:approve:{user_id}:1")
    kb.button(text="✅ Approve (7 kun)", callback_data=f"access:approve:{user_id}:7")
    kb.button(text="✅ Approve (10 kun)", callback_data=f"access:approve:{user_id}:10")
    kb.button(text="✅ Approve (30 kun)", callback_data=f"access:approve:{user_id}:30")
    kb.button(text="✅ Approve (90 kun)", callback_data=f"access:approve:{user_id}:90")
    kb.button(text="❌ Reject", callback_data=f"access:reject:{user_id}")
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data == "access:request")
async def access_request(call: types.CallbackQuery):
    user = call.from_user
    text = "🔔 Yangi ruxsat so‘rovi\n\n"
    text += f"User: {user.full_name}\n"
    if user.username:
         text += f"Username: @{user.username}\n"
    text += f"User ID: {user.id}\n"

    # Adminlarga yuboramiz
    for admin_id in ADMIN_IDS:
        try:
            await call.bot.send_message(
                chat_id=admin_id,
                text=text,
                reply_markup=make_admin_approve_kb(user.id)
            )
        except Exception as e:
            logger.exception(f"Failed to notify admin {admin_id}: {e}")

    await call.answer("So‘rov yuborildi. Admin tasdiqlashini kuting.", show_alert=True)

@router.callback_query(F.data.startswith("access:approve:"))
async def access_approve(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
        return

    _, _, user_id_s, days_s = call.data.split(":")
    user_id = int(user_id_s)
    days = int(days_s)

    grant_access(user_id, days=days)

    # Userga xabar
    await call.bot.send_message(
        chat_id=user_id,
        text=f"✅ Sizga ruxsat berildi: {days} kun."
    )
    await call.message.edit_reply_markup(reply_markup=None)  # ✅ tugmalarni o‘chiradi
    await call.answer("Tasdiqlandi.", show_alert=True)

@router.callback_query(F.data.startswith("access:reject:"))
async def access_reject(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("⛔ Ruxsat yo‘q.", show_alert=True)
        return

    _, _, user_id_s = call.data.split(":")
    user_id = int(user_id_s)

    await call.bot.send_message(
        chat_id=user_id,
        text="❌ Ruxsat berilmadi. Admin bilan bog‘laning."
    )
    await call.answer("Rad etildi.", show_alert=True)
