# handlers/admin_subs.py
from __future__ import annotations

import time
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict, List

from aiogram import Router, F, types
from aiogram.filters import Command

from db.access import get_expiring_between, was_notified, mark_notified,list_active_users_with_profiles,get_access_info

router = Router()
logger = logging.getLogger(__name__)

ADMIN_IDS = {7040085454,8443292780}  # o'zingizniki

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


def _who_row(r: Dict[str, Any]) -> str:
    user_id = int(r["user_id"])
    uname = (r.get("username") or "").strip()
    fname = (r.get("full_name") or "").strip()

    label = fname if fname else str(user_id)
    if uname:
        label = f"{label} (@{uname})"
    if str(user_id) not in label:
        label = f"{label} | ID: {user_id}"
    return label


@router.message(Command("subs"))
async def subs_cmd(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    now = int(time.time())

    # ✅ endi async
    rows = await list_active_users_with_profiles(limit=5000)

    # bucketlar
    b_48h: List[Dict[str, Any]] = []
    b_3d: List[Dict[str, Any]] = []
    b_7d: List[Dict[str, Any]] = []
    b_after: List[Dict[str, Any]] = []

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

    # tartiblash (yaxshi ko‘rinadi)
    b_48h.sort(key=lambda x: int(x["expires_at"]))
    b_3d.sort(key=lambda x: int(x["expires_at"]))
    b_7d.sort(key=lambda x: int(x["expires_at"]))
    b_after.sort(key=lambda x: int(x["expires_at"]))

    lines: List[str] = []
    lines.append(f"👥 Aktiv obunachilar: {len(rows)} ta")
    lines.append(f"🕒 Hisobot vaqti: {_fmt_ts(now)} ({TZ_LABEL})")
    lines.append("")

    def add_bucket(title: str, bucket: List[Dict[str, Any]]):
        lines.append(f"{title} ({len(bucket)} ta):")
        if not bucket:
            lines.append("— yo‘q")
        else:
            for i, r in enumerate(bucket, 1):
                exp = int(r["expires_at"])
                lines.append(f"{i}) {_who_row(r)} — {_fmt_ts(exp)} (qoldi: {_remains(exp)})")
        lines.append("")

    add_bucket("🚨 48 soat ichida tugaydi", b_48h)
    add_bucket("⚠️ 3 kun ichida tugaydi", b_3d)
    add_bucket("⏳ 7 kun ichida tugaydi", b_7d)

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

    # Telegram limit: 4096 (xavfsiz 3900)
    if len(text) <= 3900:
        await message.answer(text)
        return

    chunk: List[str] = []
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
    user_id = call.from_user.id
    now = int(time.time())

    exp = await get_access_info(user_id)

    if not exp:
        await call.answer("❌ Sizda hozir obuna yo‘q.", show_alert=True)
        return

    exp = int(exp)

    if exp <= now:
        await call.answer(
            "❌ Obunangiz tugagan!\n\n"
            "🚫 Botdan foydalanish cheklangan\n\n"
            "🔥 Hoziroq tiklang va davom eting:\n"
            "👉 /start",
            show_alert=True
        )
        return

    msg = (
        "💎 Premium status: AKTIV\n\n"
        f"🕒 Tugash: {_fmt_ts(exp)}\n"
        f"⏳ Qoldi: {_remains(exp)}\n\n"
        "━━━━━━━━━━━━━━━\n"
        "🔥 Siz hozir VIP foydalanuvchisiz!\n\n"
        "❗ Muhim:\n"
        "Obuna tugashi bilan barcha imkoniyatlar yopiladi.\n\n"
        "🚀 Oldindan uzaytiring va hech narsa yo‘qotmang!\n"
        "👉 /start orqali davom eting"
    )
    await call.answer("💎 Obuna ma’lumoti", show_alert=True)

    await call.message.answer(msg, parse_mode="Markdown")
