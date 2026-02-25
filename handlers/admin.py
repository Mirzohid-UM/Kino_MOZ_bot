from __future__ import annotations

import logging
import datetime

from aiogram import Router, F, types

from db.access import grant_access, extend_access, has_access, count_active_subs
from db.users import count_users
from db.audit import auditj

router = Router()
logger = logging.getLogger(__name__)

ADMIN_IDS = {7040085454}  # <-- sizning ID


@router.message(F.text.startswith("/grant"))
async def grant_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Siz admin emassiz.")
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Usage: /grant <user_id> [days]\nMasalan: /grant 7040085454 1")
        return

    try:
        user_id = int(parts[1])
        days = int(parts[2]) if len(parts) >= 3 else 1
        if days <= 0:
            await message.answer("❌ days 0 dan katta bo‘lishi kerak.")
            return
    except ValueError:
        await message.answer("❌ Noto‘g‘ri format. Masalan: /grant 7040085454 1")
        return

    # 1) Amal (async)
    expires_at = await grant_access(user_id, days=days)

    # 2) Audit (async)
    await auditj(
        actor_id=message.from_user.id,
        action="grant_access",
        target_id=user_id,
        meta={"days": days, "expires_at": int(expires_at)},
    )

    # 3) Tekshiruv (async)
    ok = await has_access(user_id)

    dt = datetime.datetime.fromtimestamp(int(expires_at))
    await message.answer(
        f"✅ Access berildi: user_id={user_id}, days={days}\n"
        f"🕒 Tugash: {dt:%Y-%m-%d %H:%M}\n"
        f"Tekshiruv: {ok}"
    )
    logger.info("Access granted by admin=%s to user=%s days=%s", message.from_user.id, user_id, days)


@router.message(F.text.startswith("/extend"))
@router.message(F.text.startswith("/renew"))  # eski nom ham ishlasin
async def renew_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Siz admin emassiz.")
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Usage: /extend <user_id> [days]\nMasalan: /extend 7040085454 30")
        return

    try:
        user_id = int(parts[1])
        days = int(parts[2]) if len(parts) >= 3 else 30
        if days <= 0:
            await message.answer("❌ days 0 dan katta bo‘lishi kerak.")
            return
    except ValueError:
        await message.answer("❌ Noto‘g‘ri format. Masalan: /extend 7040085454 30")
        return

    try:
        # 1) Amal: obunani uzaytirish (async)
        new_exp = await extend_access(user_id, days=days)

        # 2) Audit (async)
        await auditj(
            actor_id=message.from_user.id,
            action="extend_access",
            target_id=user_id,
            meta={"days": days, "new_expires_at": int(new_exp)},
        )

        # 3) Javob
        dt = datetime.datetime.fromtimestamp(int(new_exp))
        await message.answer(
            f"✅ Uzaytirildi: user_id={user_id}, +{days} kun\n"
            f"🕒 Yangi muddat: {dt:%Y-%m-%d %H:%M}"
        )

        logger.info("Access extended by admin=%s for user=%s days=%s", message.from_user.id, user_id, days)

    except Exception:
        logger.exception("Extend failed")
        await message.answer("❌ Uzaytirishda xatolik. Logni tekshiring.")


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
        f"✅ Active subs: {active}\n"
        f"⏳ No/expired: {no_expired}\n\n"
        "📌 Buyruqlar:\n"
        "- /grant <id> [days]\n"
        "- /extend <id> [days]\n"
        "- /subs"
    )