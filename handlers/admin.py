# handlers/admin.py
from __future__ import annotations

import logging
import datetime
import time
import asyncio
from db.stats import get_today_stats

from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from utils.search_cache import SEARCH_CACHE
from db.access import (
    grant_access,
    extend_access,
    has_access,
    count_active_subs,
    list_active_user_ids
)
from db.users import count_users
from db.audit import auditj
from db.broadcast import list_all_users, list_unsubscribed_users, set_user_blocked

# ----------------------------
# GLOBALS
# ----------------------------
router = Router()
logger = logging.getLogger(__name__)
broadcast_mode: dict[int, str] = {}  # user_id -> broadcast mode
ADMIN_IDS = {7040085454,8443292780}

# ----------------------------

# INLINE KEYBOARDS
# ----------------------------
def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📡 Broadcast", callback_data="admin_bc")],
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
            InlineKeyboardButton(text="📈 Full Stat", callback_data="admin_stats_full"),
        ],
        [
            InlineKeyboardButton(text="👥 Users", callback_data="admin_users"),
        ],
        [InlineKeyboardButton(text="🧹 Cache clear", callback_data="admin_clear_cache")]
    ])

def bc_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Hammasi", callback_data="bc_all")],
        [
            InlineKeyboardButton(text="💎 Obunachilar", callback_data="bc_subs"),
            InlineKeyboardButton(text="⚠️ Obunasizlar", callback_data="bc_nosubs"),
        ],
        [InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back")]
    ])

# ----------------------------
# ADMIN PANEL
# ----------------------------
@router.message(F.text == "/admin")
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    users = await count_users()
    active = await count_active_subs()
    no_expired = max(0, int(users) - int(active))

    await message.answer(
        "🛠 Admin panel\n\n"
        f"👥 Users: {users}\n"
        f"✅ Active: {active}\n"
        f"⏳ No sub: {no_expired}",
        reply_markup=admin_kb()
    )

# ----------------------------
# BROADCAST CALLBACKS
# ----------------------------
@router.callback_query(F.data == "admin_bc")
async def admin_bc(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    await callback.message.edit_text(
        "📡 Qaysi guruhga yuborasiz?",
        reply_markup=bc_kb()
    )


@router.callback_query(F.data.startswith("bc_"))
async def set_mode(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    broadcast_mode[callback.from_user.id] = callback.data
    await callback.message.edit_text(
        "📨 Endi yubormoqchi bo‘lgan postingizga reply qiling."
    )
    await callback.answer()  # loadingni yopadi


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    users = await count_users()
    active = await count_active_subs()
    no_expired = max(0, int(users) - int(active))

    await callback.message.edit_text(
        "🛠 Admin panel\n\n"
        f"👥 Users: {users}\n"
        f"✅ Active: {active}\n"
        f"⏳ No sub: {no_expired}",
        reply_markup=admin_kb()
    )


# ----------------------------
# BROADCAST REPLY HANDLER
# ----------------------------
@router.message(F.reply_to_message)
async def handle_broadcast(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    mode = broadcast_mode.pop(message.from_user.id, None)  # 🔥 FIX
    if not mode:
        return

    # foydalanuvchilarni olish
    if mode == "bc_all":
        user_ids = await list_all_users()
    elif mode == "bc_subs":
        user_ids = await list_active_user_ids()
    else:
        user_ids = await list_unsubscribed_users()

    if not user_ids:
        await message.answer("⚠️ Foydalanuvchilar topilmadi.")
        broadcast_mode.pop(message.from_user.id, None)
        return

    src = message.reply_to_message
    sent = 0
    failed = 0

    status = await message.answer(f"📣 Yuborilyapti... 0/{len(user_ids)}")

    for i, uid in enumerate(user_ids, start=1):
        try:
            await message.bot.copy_message(
                chat_id=uid,
                from_chat_id=src.chat.id,
                message_id=src.message_id,
            )
            sent += 1

        except (TelegramForbiddenError, TelegramBadRequest):
            failed += 1
            await set_user_blocked(uid)

        except Exception as e:
            failed += 1
            logger.exception("Broadcast error uid=%s: %s", uid, e)

        # throttle
        if i % 10 == 0:
            await asyncio.sleep(1)

        # progress update
        if i % 50 == 0 or i == len(user_ids):
            try:
                await status.edit_text(f"📣 Yuborilyapti... {i}/{len(user_ids)}")
            except Exception:
                pass

    await status.edit_text(
        f"✅ Broadcast tugadi\n\n"
        f"📨 Yuborildi: {sent}\n"
        f"❌ Yetmadi: {failed}\n"
        f"👥 Jami: {len(user_ids)}"
    )

    broadcast_mode.pop(message.from_user.id, None)


# ----------------------------
# USER GRANT / EXTEND
# ----------------------------

# ----------------------------
# CACHE COMMANDS
# ----------------------------
@router.message(F.text == "/clearcache")
async def clear_cache_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    SEARCH_CACHE.clear()
    await message.answer("✅ Search cache tozalandi.")


@router.message(F.text == "/cacheinfo")
async def cache_info_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(f"📦 SEARCH_CACHE keys: {len(SEARCH_CACHE)}")


# ----------------------------
# STATS / USERS CALLBACKS
# ----------------------------
@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    users = await count_users()
    active = await count_active_subs()

    await callback.message.edit_text(
        f"📊 Statistika\n\n"
        f"👥 Users: {users}\n"
        f"💎 Active: {active}\n"
        f"⚠️ No sub: {users - active}"
    )


@router.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    users = await count_users()
    await callback.answer(f"👥 {users} user", show_alert=True)


@router.callback_query(F.data == "admin_clear_cache")
async def clear_cache_cb(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    SEARCH_CACHE.clear()
    await callback.answer("Cache tozalandi ✅", show_alert=True)


@router.callback_query(F.data == "admin_stats_full")
async def full_stats(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return

    stats = await get_today_stats()

    await callback.message.edit_text(
        f"""📊 Bugungi statistika

👥 Yangi userlar: {stats['new_users']}
🚫 Bloklangan: {stats['blocked']}
⏳ Obunasi tugagan: {stats['expired']}

💎 Ruxsat berilgan: {stats['grants']} marta
📅 Jami kun: {stats['total_days']} kun
"""
    )