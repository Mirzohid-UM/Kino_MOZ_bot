import asyncio
import logging
from aiogram import Router, F, types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from db.access import list_active_user_ids
from db.broadcast import list_all_users, list_unsubscribed_users, set_user_blocked

router = Router()
log = logging.getLogger(__name__)

ADMIN_IDS = [7040085454,8443292780]


# =========================
# UNIVERSAL BROADCAST
# =========================

async def run_broadcast(message: types.Message, user_ids: list[int]):
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
            await set_user_blocked(uid)   # 🔥 blok qilgan

        except Exception as e:
            failed += 1
            log.exception("broadcast error uid=%s err=%s", uid, e)

        # anti flood
        if i % 20 == 0:
            await asyncio.sleep(1)

        # progress update
        if i % 50 == 0 or i == len(user_ids):
            try:
                await status.edit_text(f"📣 Yuborilyapti... {i}/{len(user_ids)}")
            except:
                pass

    await status.edit_text(
        f"""✅ Broadcast yakunlandi

📨 Yuborildi: {sent}
❌ Yetmadi: {failed}
👥 Jami: {len(user_ids)}
"""
    )


# =========================
# /post → HAMMAGA
# =========================
@router.message(F.text == "/post")
async def post_all(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    if not message.reply_to_message:
        await message.answer("Post yuborish uchun reply qiling.")
        return

    user_ids = await list_all_users()

    if not user_ids:
        await message.answer("Userlar topilmadi.")
        return

    await run_broadcast(message, user_ids)


# =========================
# /postobuna → OBUNACHILAR
# =========================
@router.message(F.text == "/postobuna")
async def post_subs(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    if not message.reply_to_message:
        await message.answer("Reply qiling.")
        return

    user_ids = await list_active_user_ids()

    if not user_ids:
        await message.answer("Obunachilar topilmadi.")
        return

    await run_broadcast(message, user_ids)


# =========================
# /postbezobuna → OBUNASIZLAR
# =========================
@router.message(F.text == "/postbezobuna")
async def post_no_subs(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    if not message.reply_to_message:
        await message.answer("Reply qiling.")
        return

    user_ids = await list_unsubscribed_users()

    if not user_ids:
        await message.answer("Mos user topilmadi.")
        return

    await run_broadcast(message, user_ids)