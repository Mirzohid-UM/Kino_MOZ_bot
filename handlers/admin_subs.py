import time
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, F, types
from aiogram.filters import Command

from db import list_active_users_with_profiles
from db.core import get_conn  # sub:info uchun

router = Router()
logger = logging.getLogger(__name__)

ADMIN_IDS = {7040085454}  # o'zingizniki

TZ = ZoneInfo("Asia/Tashkent")
TZ_LABEL = "Toshkent"


def _fmt_ts(ts: int) -> str:
    return datetime.fromtimestamp(int(ts), TZ).strftime("%Y-%m-%d %H:%M")


def _remains(expires_at: int) -> str:
    sec = max(0, int(expires_at - time.time()))
    d = sec // 86400
    h = (sec % 86400) // 3600
    m = (sec % 3600) // 60
    if d > 0:
        return f"{d}d {h}h"
    return f"{h}h {m}m"


def _who_row(r) -> str:
    user_id = int(r["user_id"])
    uname = (r["username"] or "").strip()
    fname = (r["full_name"] or "").strip()

    label = fname if fname else str(user_id)
    if uname:
        label = f"{label} (@{uname})"
    # IDni ham ko‘rsatib qo‘yamiz (admin uchun qulay)
    if str(user_id) not in label:
        label = f"{label} | ID: {user_id}"
    return label


@router.message(Command("subs"))
async def subs_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    now = int(time.time())
    rows = list_active_users_with_profiles(limit=5000)

    # bucketlar
    b_48h = []
    b_3d = []
    b_7d = []
    b_after = []

    for r in rows:
        exp = int(r["expires_at"])
        left = exp - now

        if left <= 48 * 3600:
            b_48h.append(r)
        elif left <= 3 * 86400:
            b_3d.append(r)
        elif left <= 7 * 86400:
            b_7d.append(r)
        else:
            b_after.append(r)

    lines = []
    lines.append(f"👥 Aktiv obunachilar: {len(rows)} ta")
    lines.append(f"🕒 Hisobot vaqti: {_fmt_ts(now)} ({TZ_LABEL})")
    lines.append("")

    # 48h
    lines.append(f"🚨 48 soat ichida tugaydi ({len(b_48h)} ta):")
    if not b_48h:
        lines.append("— yo‘q")
    else:
        for i, r in enumerate(b_48h, 1):
            exp = int(r["expires_at"])
            lines.append(f"{i}) {_who_row(r)} — {_fmt_ts(exp)} (qoldi: {_remains(exp)})")
    lines.append("")

    # 3d
    lines.append(f"⚠️ 3 kun ichida tugaydi ({len(b_3d)} ta):")
    if not b_3d:
        lines.append("— yo‘q")
    else:
        for i, r in enumerate(b_3d, 1):
            exp = int(r["expires_at"])
            lines.append(f"{i}) {_who_row(r)} — {_fmt_ts(exp)} (qoldi: {_remains(exp)})")
    lines.append("")

    # 7d
    lines.append(f"⏳ 7 kun ichida tugaydi ({len(b_7d)} ta):")
    if not b_7d:
        lines.append("— yo‘q")
    else:
        for i, r in enumerate(b_7d, 1):
            exp = int(r["expires_at"])
            lines.append(f"{i}) {_who_row(r)} — {_fmt_ts(exp)} (qoldi: {_remains(exp)})")
    lines.append("")

    # after 7d (faqat summary)
    lines.append(f"✅ 7 kundan keyin ({len(b_after)} ta):")
    if not b_after:
        lines.append("— yo‘q")
    else:
        nearest = b_after[0]
        farthest = b_after[-1]
        lines.append(f"Eng yaqin: {_who_row(nearest)} — {_fmt_ts(int(nearest['expires_at']))}")
        lines.append(f"Eng uzoq: {_who_row(farthest)} — {_fmt_ts(int(farthest['expires_at']))}")

    lines.append("")
    lines.append("📌 Buyruqlar:")
    lines.append("- /grant <id> <days>")
    lines.append("- /extend <id> <days>")

    text = "\n".join(lines)

    # Telegram limit: 4096. Agar juda uzun bo‘lsa, ikkiga bo‘lib yuboramiz.
    if len(text) <= 3900:
        await message.answer(text)
        return

    # split
    chunk = []
    cur = 0
    for line in lines:
        if cur + len(line) + 1 > 3900:
            await message.answer("\n".join(chunk))
            chunk = []
            cur = 0
        chunk.append(line)
        cur += len(line) + 1
    if chunk:
        await message.answer("\n".join(chunk))


@router.callback_query(F.data == "sub:info")
async def sub_info(call: types.CallbackQuery):
    # foydalanuvchining o'z obunasi haqida
    user_id = call.from_user.id
    conn = get_conn()
    now = int(time.time())

    row = conn.execute(
        "SELECT expires_at FROM user_access WHERE user_id=%s",
        (int(user_id),),
    ).fetchone()

    if not row:
        await call.answer("Sizda hozir obuna yo‘q.", show_alert=True)
        return

    exp = int(row["expires_at"])
    if exp <= now:
        await call.answer("Obunangiz tugagan. Adminga yozing.", show_alert=True)
        return

    msg = (
        "ℹ️ Obuna ma’lumoti\n\n"
        f"🕒 Tugash vaqti: {_fmt_ts(exp)} ({TZ_LABEL})\n"
        f"⌛ Qoldi: {_remains(exp)}\n\n"
        "Uzaytirish uchun adminga yozing."
    )
    await call.answer(msg, show_alert=True)