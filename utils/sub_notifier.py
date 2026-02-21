import asyncio
import logging
import time
from datetime import datetime
from aiogram.utils.keyboard import InlineKeyboardBuilder


from db import get_expiring_between, was_notified, mark_notified  # access_repo dan export bo'lishi kerak

logger = logging.getLogger(__name__)

TZ_LABEL = "Toshkent"

def _fmt_ts(ts: int) -> str:
    # Sizning server time unix bo'lsa ham, matnda oddiy ko'rsatamiz.
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")

def _remains(expires_at: int) -> str:
    sec = max(0, int(expires_at - time.time()))
    d = sec // 86400
    h = (sec % 86400) // 3600
    return f"{d}d {h}h"

def _kb_extend(admin_url: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="🔁 Uzaytirish (admin)", url="https://t.me/Mozcyberr")
    kb.button(text="ℹ️ Obuna haqida", callback_data="sub:info")
    kb.adjust(1)
    return kb.as_markup()

async def run_sub_expiry_notifier(bot, *, admin_url: str, interval_sec: int = 600):
    """
    Har interval_sec da tekshiradi:
    - 3 kun qolganda (d3)
    - 1 kun qolganda (d1)
    """
    while True:
        try:
            now = int(time.time())

            # d3: 72 soat +/- 30 daqiqa oynada ushlaymiz (spike bo'lmasin)
            d3_start = now + 3 * 86400 - 1800
            d3_end   = now + 3 * 86400 + 1800

            # d1: 24 soat +/- 30 daqiqa
            d1_start = now + 1 * 86400 - 1800
            d1_end   = now + 1 * 86400 + 1800

            for kind, start_ts, end_ts in (("d3", d3_start, d3_end), ("d1", d1_start, d1_end)):
                rows = get_expiring_between(start_ts, end_ts, limit=2000)

                for r in rows:
                    user_id = int(r["user_id"])
                    expires_at = int(r["expires_at"])

                    if was_notified(user_id, kind, expires_at):
                        continue

                    uname = r["username"]
                    fname = r["full_name"]
                    who = (fname or "").strip()
                    if uname:
                        who = (who + f" (@{uname})").strip()
                    if not who:
                        who = str(user_id)

                    when = _fmt_ts(expires_at)
                    left = _remains(expires_at)

                    if kind == "d3":
                        text = (
                            f"⏳ Obunangiz tugashiga 3 kun qoldi.\n\n"
                            f"🕒 Tugash vaqti: {when} ({TZ_LABEL})\n"
                            f"⌛ Qoldi: {left}\n\n"
                            f"Obunani uzaytirmoqchimisiz?"
                        )
                    else:
                        text = (
                            f"🚨 Obunangiz tugashiga 1 kun qoldi.\n\n"
                            f"🕒 Tugash vaqti: {when} ({TZ_LABEL})\n"
                            f"⌛ Qoldi: {left}\n\n"
                            f"Obunani uzaytirmoqchimisiz?"
                        )

                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=text,
                            reply_markup=_kb_extend(admin_url),
                            protect_content=True,  # ixtiyoriy
                        )
                        mark_notified(user_id, kind, expires_at)
                    except Exception:
                        # user botni block qilgan bo'lishi mumkin
                        logger.exception("Failed to notify user_id=%s kind=%s", user_id, kind)

        except Exception:
            logger.exception("Notifier loop error")

        await asyncio.sleep(interval_sec)