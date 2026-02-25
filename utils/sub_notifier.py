import asyncio
import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from db.access import get_expiring_between, was_notified, mark_notified  # ✅ to‘g‘ri moduldan

logger = logging.getLogger(__name__)

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


def _kb_extend(admin_url: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="🔁 Uzaytirish (admin)", url=admin_url)  # ✅ hardcode emas
    kb.button(text="ℹ️ Obuna haqida", callback_data="sub:info")
    kb.adjust(1)
    return kb.as_markup()


async def run_sub_expiry_notifier(bot, *, admin_url: str, interval_sec: int = 600):
    """
    Har interval_sec da tekshiradi:
    - 3 kun qolganda (d3)
    - 1 kun qolganda (d1)

    Eslatma: DB funksiyalar async bo‘lishi shart.
    """
    while True:
        try:
            now = int(time.time())

            # d3: 72 soat +/- 30 daqiqa
            d3_start = now + 3 * 86400 - 1800
            d3_end = now + 3 * 86400 + 1800

            # d1: 24 soat +/- 30 daqiqa
            d1_start = now + 1 * 86400 - 1800
            d1_end = now + 1 * 86400 + 1800

            for kind, start_ts, end_ts in (("d3", d3_start, d3_end), ("d1", d1_start, d1_end)):
                rows = await get_expiring_between(start_ts, end_ts, limit=2000) # ✅ await

                for r in rows:
                    user_id = int(r["user_id"])
                    expires_at = int(r["expires_at"])

                    # ✅ await
                    if await was_notified(user_id=user_id, kind=kind, expires_at=expires_at):
                        continue

                    uname = (r.get("username") or "").strip()
                    fname = (r.get("full_name") or "").strip()

                    who = fname or str(user_id)
                    if uname:
                        who = f"{who} (@{uname})"

                    when = _fmt_ts(expires_at)
                    left = _remains(expires_at)

                    title = "⏳ Obunangiz tugashiga 3 kun qoldi." if kind == "d3" else "🚨 Obunangiz tugashiga 1 kun qoldi."

                    text = (
                        f"{title}\n\n"
                        f"🕒 Tugash vaqti: {when} ({TZ_LABEL})\n"
                        f"⌛ Qoldi: {left}\n\n"
                        f"Obunani uzaytirmoqchimisiz?"
                    )

                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=text,
                            reply_markup=_kb_extend(admin_url),
                            protect_content=True,
                        )
                        await mark_notified(user_id=user_id, kind=kind, expires_at=expires_at)  # ✅ await
                    except (TelegramForbiddenError, TelegramBadRequest):
                        # user bloklagan / chat yo‘q / h.k.
                        logger.info("Notify skipped (blocked/badrequest) user_id=%s kind=%s", user_id, kind)
                    except Exception:
                        logger.exception("Failed to notify user_id=%s kind=%s", user_id, kind)

        except Exception:
            logger.exception("Notifier loop error")

        await asyncio.sleep(interval_sec)