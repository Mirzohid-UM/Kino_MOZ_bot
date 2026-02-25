import asyncio
import logging
from aiogram import Router, F, types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from db.access import list_active_user_ids

router = Router()
log = logging.getLogger(__name__)

ADMIN_ID = 7040085454


@router.message(F.text == "/post")
async def broadcast_post(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    if not message.reply_to_message:
        await message.answer("Post yuborish uchun biror xabarga reply qilib /post yozing.")
        return

    src = message.reply_to_message

    # ✅ async DB chaqiruv
    user_ids = await list_active_user_ids()

    if not user_ids:
        await message.answer("Aktiv obunachilar topilmadi.")
        return

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

        except Exception as e:
            failed += 1
            log.exception("broadcast error uid=%s err=%s", uid, e)

        # throttle
        if i % 20 == 0:
            await asyncio.sleep(1)

        if i % 50 == 0 or i == len(user_ids):
            try:
                await status.edit_text(f"📣 Yuborilyapti... {i}/{len(user_ids)}")
            except Exception:
                pass

    await status.edit_text(
        "✅ Broadcast yakunlandi.\n\n"
        f"📨 Yuborildi: {sent}\n"
        f"❌ Yetmadi: {failed}\n"
        f"👥 Jami: {len(user_ids)}"
    )