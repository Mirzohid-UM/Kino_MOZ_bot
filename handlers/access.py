# handlers/access.py
from __future__ import annotations

import logging
import time
from typing import Set

from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from db.access import grant_access  # grant_access(user_id:int, days:int)
from db.users import upsert_user  # upsert_user(user_id, username, full_name) - agar sendan async bo'lsa

router = Router()
logger = logging.getLogger(__name__)

# Admin ID lar
ADMIN_IDS: Set[int] = {7040085454.8443292780}

# Spamdan saqlash: user 30 soniyada 1 marta so'ray oladi
_REQ_COOLDOWN_SEC = 30
_LAST_REQ: dict[int, float] = {}


def _can_request(user_id: int) -> bool:
    now = time.time()
    last = _LAST_REQ.get(user_id, 0.0)
    if now - last < _REQ_COOLDOWN_SEC:
        return False
    _LAST_REQ[user_id] = now
    return True


def make_admin_approve_kb(user_id: int) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    # 1/7/10/20/30/90
    for days in (1, 7, 10, 20, 30, 90):
        kb.button(text=f"✅ Approve ({days} kun)", callback_data=f"access:approve:{user_id}:{days}")

    kb.button(text="❌ Reject", callback_data=f"access:reject:{user_id}")
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data == "access:request")
async def access_request(call: types.CallbackQuery):
    user = call.from_user
    user_id = int(user.id)

    if not _can_request(user_id):
        await call.answer("⏳ Biroz kuting, keyin qayta yuboring.", show_alert=True)
        return

    # profilni DBga yozib qo'yamiz (username/full_name keyin admin panelda kerak bo'ladi)
    try:
        await upsert_user(user_id, user.username or None, user.full_name or None)
    except Exception:
        logger.exception("upsert_user failed (non-fatal)")

    text = (
        "🔔 Yangi ruxsat so‘rovi\n\n"
        f"👤 Ism: {user.full_name}\n"
        + (f"🧾 Username: @{user.username}\n" if user.username else "")
        + f"🆔 User ID: {user_id}\n"
    )

    sent_any = False
    for admin_id in ADMIN_IDS:
        try:
            await call.bot.send_message(
                chat_id=admin_id,
                text=text,
                reply_markup=make_admin_approve_kb(user_id),
            )
            sent_any = True
        except Exception as e:
            logger.exception("Failed to notify admin %s: %s", admin_id, e)

    if sent_any:
        await call.answer("✅ So‘rov yuborildi. Admin tasdiqlashini kuting.", show_alert=True)
    else:
        await call.answer("❌ Adminlarga yuborib bo‘lmadi (bot adminlarga yoza olmayapti).", show_alert=True)


@router.callback_query(F.data.startswith("access:approve:"))
async def access_approve(call: types.CallbackQuery):
    # callback_data: access:approve:{user_id}:{days}
    parts = (call.data or "").split(":")
    if len(parts) != 4:
        await call.answer("❌ Noto‘g‘ri callback.", show_alert=True)
        return

    _, action, user_id_s, days_s = parts
    if action != "approve":
        await call.answer()
        return

    admin_id = int(call.from_user.id)
    if admin_id not in ADMIN_IDS:
        await call.answer("⛔ Siz admin emassiz.", show_alert=True)
        return

    try:
        user_id = int(user_id_s)
        days = int(days_s)
    except ValueError:
        await call.answer("❌ Parametr xato.", show_alert=True)
        return

    # DB ga yozamiz
    try:
        await grant_access(user_id, days=days)
    except Exception:
        logger.exception("grant_access failed")
        await call.answer("❌ DB xato. Keyinroq urinib ko‘ring.", show_alert=True)
        return

    # Userga xabar
    try:
        await call.bot.send_message(
            chat_id=user_id,
            text=f"✅ Sizga {days} kunlik obuna tayinlandi.\n\nBotdan foydalanishingiz mumkin 🎬",
        )
    except TelegramForbiddenError:
        # user botni block qilgan
        pass
    except TelegramBadRequest:
        pass
    except Exception:
        logger.exception("Failed to notify user about approval")

    # Adminga tasdiq
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await call.answer(f"✅ {days} kun berildi.", show_alert=True)


@router.callback_query(F.data.startswith("access:reject:"))
async def access_reject(call: types.CallbackQuery):
    # callback_data: access:reject:{user_id}
    parts = (call.data or "").split(":")
    if len(parts) != 3:
        await call.answer("❌ Noto‘g‘ri callback.", show_alert=True)
        return

    _, action, user_id_s = parts
    if action != "reject":
        await call.answer()
        return

    admin_id = int(call.from_user.id)
    if admin_id not in ADMIN_IDS:
        await call.answer("⛔ Siz admin emassiz.", show_alert=True)
        return

    try:
        user_id = int(user_id_s)
    except ValueError:
        await call.answer("❌ Parametr xato.", show_alert=True)
        return

    # Userga xabar
    try:
        await call.bot.send_message(
            chat_id=user_id,
            text="❌ So‘rovingiz rad etildi. Admin bilan bog‘laning.",
        )
    except Exception:
        pass

    # Admin tugmalarini olib tashlaymiz
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    await call.answer("✅ Rad etildi.", show_alert=True)

async def list_active_users_with_profiles(*, limit: int = 5000, now: Optional[int] = None) -> List[Dict[str, Any]]:
    if now is None:
        import time
        now = int(time.time())

    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ua.user_id, ua.expires_at, u.username, u.full_name
            FROM user_access ua
            LEFT JOIN users u ON u.user_id = ua.user_id
            WHERE ua.expires_at > $1
            ORDER BY ua.expires_at ASC
            LIMIT $2
            """,
            int(now), int(limit)
        )
    return [dict(r) for r in rows]
