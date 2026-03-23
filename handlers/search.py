# handlers/search.py
import time, uuid, logging, re
from logging import Logger

from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

from utils.search_cache import SEARCH_CACHE
from utils.copy import safe_copy_with_ttl
from db.movies import delete_movie_by_message_id
from db.access import has_access
from service.search import find_top_movies, extract_episode

router = Router()
logger: Logger = logging.getLogger(__name__)

PAGE_SIZE = 5
CACHE_TTL = 10 * 60
TTL = 6 * 60 * 60  # 6 soat
TTL_HOURS = TTL // 3600

def _cleanup_cache():
    now = time.time()
    for k in list(SEARCH_CACHE.keys()):
        if now - SEARCH_CACHE[k]["ts"] > CACHE_TTL:
            SEARCH_CACHE.pop(k, None)


def _btn_text(s: str) -> str:
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
            text=_btn_text(it.get("title", "")),
            callback_data=f"movie:{token}:{it['message_id']}"
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
    if not await has_access(message.from_user.id):
        await message.answer("⛔ Sizda ruxsat yo‘q. Admin bilan bog‘laning.")
        return

    # cache cleanup (light)
    if int(time.time()) % 10 == 0:
        _cleanup_cache()

    query = (message.text or "").strip()
    if len(query) > 80 or "\n" in query:
        await message.answer("🔎 Kino nomini qisqa yozing (masalan: Shazam)")
        return

    # episode parse
    m = re.match(r"^(.*?)(?:\s+(\d{1,3}))?$", query)
    base = (m.group(1) or "").strip() if m else query
    episode = m.group(2) if m else None

    # ✅ async function
    items = await find_top_movies(base)

    if items and episode:
        epn = int(episode)

        def ep_match(it: dict):
            _, e = extract_episode(it.get("title", ""))
            return 0 if e == epn else 1

        items.sort(key=ep_match)

    if not items:
        kb = InlineKeyboardBuilder()
        kb.button(text="🎬 Kanalga o‘tish", url="https://t.me/Trailer_kino_MOZ")
        kb.button(text="👤 Adminga yozish", url="https://t.me/Mozcyberr")
        kb.adjust(1)

        await message.answer(
            "❌ Afsuski, bu kino topilmadi.\n\n"
            "🎬 Lekin siz uchun qulay yechim bor!\n\n"
            "📺 Maxsus kanalimizda:\n"
            "• Barcha kinolar nomi\n"
            "• Eng yangi trailerlar\n"
            "• Oson va tez qidiruv\n\n"
            "🚀 Kerakli kinoni topish uchun pastdagi tugmani bosing:",
            reply_markup=kb.as_markup()
        )

        return
    # agar bitta bo‘lsa darrov yuboramiz
    if len(items) == 1:
        it = items[0]
        ok = await safe_copy_with_ttl(
            bot=message.bot,
            chat_id=message.from_user.id,
            from_chat_id=int(it["channel_id"]),
            message_id=int(it["message_id"]),
            ttl_sec=TTL,
            protect=True,
            disable_notification=True,
        )

        if not ok:
            await message.answer(f"⏳ Bu kino {TTL} soatdan keyin o‘chiriladi")
        else:
            await delete_movie_by_message_id(
                message_id=int(it["message_id"]),
                channel_id=int(it["channel_id"]),
            )
            await message.answer("❌ Bu kino o‘chirilgan.")
        return

    token = uuid.uuid4().hex[:10]
    SEARCH_CACHE[token] = {
        "user_id": message.from_user.id,
        "items": items,
        "ts": time.time()
    }

    total_pages = (len(items) - 1) // PAGE_SIZE + 1

    await message.answer(
        f"🎬 Topildi: {len(items)} ta (1/{total_pages})\n"
        f"⏳ Har bir kino {TTL_HOURS} soatdan keyin o‘chiriladi",
        reply_markup=build_keyboard(token, 0, items)
    )

@router.callback_query(F.data.startswith("nav:"))
async def nav_callback(call: types.CallbackQuery):
    _cleanup_cache()

    try:
        _, token, page_s = call.data.split(":")
        page = int(page_s)
    except:
        await call.answer("Xatolik", show_alert=True)
        return

    data = SEARCH_CACHE.get(token)
    if not data or data["user_id"] != call.from_user.id:
        await call.answer("Eskirgan", show_alert=True)
        return

    items = data["items"]
    total_pages = (len(items) - 1) // PAGE_SIZE + 1

    if page < 0 or page >= total_pages:
        await call.answer("Noto‘g‘ri sahifa", show_alert=True)
        return

    try:
        await call.message.edit_text(
            f"🎬 Topildi: {len(items)} ta ({page+1}/{total_pages})",
            reply_markup=build_keyboard(token, page, items)
        )
    except TelegramBadRequest:
        pass

    await call.answer()


@router.callback_query(F.data.startswith("movie:"))
async def movie_callback(call: types.CallbackQuery):
    _cleanup_cache()

    try:
        _, token, msg_s = call.data.split(":")
        msg_id = int(msg_s)
    except:
        await call.answer("Xatolik", show_alert=True)
        return

    data = SEARCH_CACHE.get(token)
    if not data or data["user_id"] != call.from_user.id:
        await call.answer("Eskirgan", show_alert=True)
        return

    item = next(
        (it for it in data["items"] if int(it["message_id"]) == msg_id),
        None
    )

    if not item:
        await call.answer("Topilmadi", show_alert=True)
        return

    ok = await safe_copy_with_ttl(
        bot=call.message.bot,
        chat_id=call.from_user.id,
        from_chat_id=int(item["channel_id"]),
        message_id=msg_id,
        ttl_sec=6 * 60 * 60,
        protect=True,
        disable_notification=True,
    )

    if ok:
        await call.answer()
        return

    # o‘chgan bo‘lsa DBdan ham o‘chiramiz
    try:
        await delete_movie_by_message_id(
            message_id=msg_id,
            channel_id=int(item["channel_id"])
        )
    except:
        logger.exception("delete failed")

    # cache update
    data["items"] = [
        it for it in data["items"]
        if int(it["message_id"]) != msg_id
    ]

    if not data["items"]:
        await call.message.edit_text("❌ Kinolar qolmadi")
        await call.answer("O‘chirilgan", show_alert=True)
        return

    total_pages = (len(data["items"]) - 1) // PAGE_SIZE + 1

    await call.message.edit_text(
        f"🎬 Qoldi: {len(data['items'])} ta (1/{total_pages})",
        reply_markup=build_keyboard(token, 0, data["items"])
    )

    await call.answer("❌ Kino o‘chirilgan", show_alert=True)