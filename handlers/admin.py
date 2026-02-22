from aiogram import Router, F, types
from db import grant_access, has_access
import logging
import datetime
from db import last_audit,list_active_users,count_users, count_active_subs

from db import extend_access, audit  # ✅ importlarni qo'shing
import datetime

router = Router()
logger = logging.getLogger(__name__)

ADMIN_IDS = {7040085454}  # <-- sizning ID

from db import grant_access, has_access, audit  # ✅ audit import qiling

@router.message(F.text.startswith("/grant"))
async def grant_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Siz admin emassiz.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /grant <user_id> [days]\nMasalan: /grant 7040085454 1")
        return

    user_id = int(parts[1])
    days = int(parts[2]) if len(parts) >= 3 else 1

    # 1) Amal
    grant_access(user_id, days=days)

    # 2) Audit (AMALDAN KEYIN)
    audit(
        actor_id=message.from_user.id,
        action="grant_access",
        target_id=user_id,
        meta=f"days={days}"
    )

    # 3) Tekshiruv (ixtiyoriy)
    ok = has_access(user_id)

    await message.answer(f"✅ Access berildi: user_id={user_id}, days={days}\nTekshiruv: {ok}")
    logger.info(f"Access granted by admin={message.from_user.id} to user={user_id} days={days}")

@router.message(F.text.startswith("/renew"))
async def renew_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Siz admin emassiz.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /renew <user_id> [days]\nMasalan: /renew 7040085454 30")
        return

    user_id = int(parts[1])
    days = int(parts[2]) if len(parts) >= 3 else 30

    try:
        # 1) Amal: obunani uzaytirish
        new_exp = extend_access(user_id, days)

        # 2) Audit: amal bajarilgandan keyin
        audit(
            actor_id=message.from_user.id,
            action="renew_access",
            target_id=user_id,
            meta=f"days={days}"
        )

        # 3) Javob
        dt = datetime.datetime.fromtimestamp(new_exp)
        await message.answer(
            f"✅ Uzaytirildi: user_id={user_id}, +{days} kun\n"
            f"Yangi muddat: {dt:%Y-%m-%d %H:%M}"
        )

        logger.info(f"Access renewed by admin={message.from_user.id} for user={user_id} days={days}")

    except Exception as e:
        logger.exception(f"Renew failed: {e}")
        await message.answer("❌ Renew qilishda xatolik. Logni tekshiring.")

@router.message(F.text == "/admin")
async def admin_panel(message: types.Message):
    if message.from_user.id != 7040085454:  # o'zing
        return

    users = count_users()
    active = count_active_subs()
    no_expired = max(0, users - active)

    await message.answer(
        "🛠 Admin panel\n\n"
        f"👥 Users: {users}\n"
        f"✅ Active subs: {active}\n"
        f"⏳ No/expired: {no_expired}"
    )
