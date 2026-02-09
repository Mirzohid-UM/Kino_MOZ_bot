# /home/mozcyber/PythonProject/handlers/search.py

import time, uuid, logging
from logging import Logger
import inspect
from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from utils.copy import safe_copy_with_ttl

from db import delete_movie_by_message_id, has_access
from service.search import find_top_movies

router = Router()
logger: Logger = logging.getLogger(__name__)

PAGE_SIZE = 5
CACHE_TTL = 10 * 60
SEARCH_CACHE: dict[str, dict] = {}

def _cleanup_cache():
    now = time.time()
    for k in [k for k, v in SEARCH_CACHE.items() if now - v["ts"] > CACHE_TTL]:
        SEARCH_CACHE.pop(k, None)

def _btn_text(s: str) -> str:
    # inline tugma textini xavfsiz qilish
    s = (s or "").replace("\n", " ").strip()
    if len(s) > 60:
        s = s[:57] + "..."
    return s or "🎬 Kino"

def build_keyboard(token: str, page: int, items: list[dict]) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    for it in items[start:end]:
        builder.button(
            text=it["title"],
            callback_data=f"movie:{token}:{it['channel_id']}:{it['message_id']}"
        )

    nav = InlineKeyboardBuilder()
    if page > 0:
        nav.button(text="⬅️ Prev", callback_data=f"nav:{token}:{page-1}")
    if end < len(items):
        nav.button(text="Next ➡️", callback_data=f"nav:{token}:{page+1}")
    if nav.buttons:
        builder.attach(nav)

    builder.adjust(1, 2)
    return builder.as_markup()


@router.message(F.text & ~F.text.startswith("/"))
async def search_movie(message: types.Message):
    if not has_access(message.from_user.id):
        await message.answer("⛔ Sizda ruxsat yo‘q. Admin bilan bog‘laning.")
        return

    _cleanup_cache()
    query = message.text
    items = find_top_movies(query)

    if not items:
        await message.answer("❌ Kino topilmadi")
        return

    if len(items) == 1:
        it = items[0]
        ok = await safe_copy_with_ttl(
            bot=message.bot,
            chat_id=message.chat.id,
            from_chat_id=it["channel_id"],
            message_id=it["message_id"],
            ttl_sec=86400
        )
        if not ok:
            await message.answer("❌ Bu kino kanaldan o‘chirilgan.")
        return

    token = uuid.uuid4().hex[:10]
    SEARCH_CACHE[token] = {"user_id": message.from_user.id, "items": items, "ts": time.time()}

    total_pages = (len(items) - 1) // PAGE_SIZE + 1
    kb = build_keyboard(token, page=0, items=items)
    await message.answer(f"Topilgan eng yaqin kinolar: {len(items)} ta. (Sahifa 1/{total_pages})", reply_markup=kb)

@router.callback_query(F.data.startswith("nav:"))
async def nav_callback(call: types.CallbackQuery):
    _cleanup_cache()
    _, token, page_s = call.data.split(":")
    page = int(page_s)

    data = SEARCH_CACHE.get(token)
    if not data:
        await call.answer("Ro‘yxat eskirib qoldi. Qaytadan qidiring.", show_alert=True)
        return
    if data["user_id"] != call.from_user.id:
        await call.answer("Bu ro‘yxat sizniki emas.", show_alert=True)
        return

    items = data["items"]
    total_pages = (len(items) - 1) // PAGE_SIZE + 1
    if page < 0 or page >= total_pages:
        await call.answer("Noto‘g‘ri sahifa.", show_alert=True)
        return

    kb = build_keyboard(token, page=page, items=items)
    text = f"Topilgan eng yaqin kinolar: {len(items)} ta. (Sahifa {page+1}/{total_pages})"

    try:
        await call.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await call.answer()



async def _maybe_await(fn, *args, **kwargs):
    """
    delete_movie_by_message_id sync bo'lsa ham, async bo'lsa ham ishlatish uchun.
    """
    try:
        res = fn(*args, **kwargs)
        if inspect.isawaitable(res):
            return await res
        return res
    except Exception:
        # DB xatolari botni yiqitmasin, lekin logda ko'rinsin
        import logging
        logging.getLogger(__name__).exception("DB operation failed")
        return None

@router.callback_query(F.data.startswith("movie:"))
async def movie_callback(call: types.CallbackQuery):
    _cleanup_cache()

    # Inline callbacklarda call.message bo'lmasligi mumkin
    if not call.message:
        await call.answer("Bu tugma eskirgan. Qaytadan qidirib ko‘ring.", show_alert=True)
        return

    # movie:{token}:{channel_id}:{message_id}
    try:
        _, token, ch_s, msg_s = call.data.split(":", 3)
        channel_id = int(ch_s)
        msg_id = int(msg_s)
    except Exception:
        await call.answer("Callback ma’lumoti buzilgan. Qayta qidirib ko‘ring.", show_alert=True)
        return

    # Token egasini tekshirish (muhim!)
    data = SEARCH_CACHE.get(token)
    if not data or data.get("user_id") != call.from_user.id:
        await call.answer("Bu tugma eskirgan. Qayta qidirib ko‘ring.", show_alert=True)
        return

    ok = await safe_copy_with_ttl(
        bot=call.message.bot,
        chat_id=call.from_user.id,   # har doim userga yuboramiz
        from_chat_id=channel_id,
        message_id=msg_id,
        ttl_sec=86400
    )

    if ok:
        await call.answer()
        return

    # ---- ok=False => source kino o'chgan ----
    # 1) DBdan o'chiramiz
    await _maybe_await(delete_movie_by_message_id, msg_id, channel_id)

    # 2) Cache ro'yxatdan ham o'chiramiz (tugma yo'qolsin)
    items = data.get("items") or []
    data["items"] = [
        it for it in items
        if not (int(it.get("message_id", -1)) == msg_id and int(it.get("channel_id", -1)) == channel_id)
    ]

    # 3) UI yangilash
    try:
        if not data["items"]:
            await call.message.edit_text("Bu ro‘yxatdagi kinolar endi mavjud emas.")
            await call.answer("Bu kino kanaldan o‘chirilgan.", show_alert=True)
            return

        total_pages = (len(data["items"]) - 1) // PAGE_SIZE + 1
        kb = build_keyboard(token, page=0, items=data["items"])
        await call.message.edit_text(
            f"Topilgan eng yaqin kinolar: {len(data['items'])} ta. (Sahifa 1/{total_pages})",
            reply_markup=kb
        )
    except TelegramBadRequest as e:
        # Ba'zan "message is not modified" chiqadi — ignore
        if "message is not modified" not in str(e):
            raise
    except Exception:
        # UI update xato bo'lsa ham userga alert beramiz
        import logging
        logging.getLogger(__name__).exception("UI update failed")

    await call.answer("Bu kino kanaldan o‘chirilgan.", show_alert=True)