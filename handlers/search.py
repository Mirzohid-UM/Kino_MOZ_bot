# handlers/search.py
import time, uuid, logging, re
from utils.search_cache import SEARCH_CACHE
from logging import Logger
from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

from utils.copy import safe_copy_with_ttl
from config import CHANNEL_ID

from db.movies import delete_movie_by_message_id   # ✅ db/__init__ emas, toza moduldan
from db.access import has_access                   # ✅ async bo'ladi
from service.search import find_top_movies, extract_episode  # ✅ bu sync qoladi

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
    # ✅ has_access endi async
    if not await has_access(message.from_user.id):
        await message.answer("⛔ Sizda ruxsat yo‘q. Admin bilan bog‘laning.")
        return

    _cleanup_cache()

    query = (message.text or "").strip()
    if len(query) > 80 or "\n" in query:
        await message.answer("🔎 Faqat kino nomini qisqa qilib yozing (masalan: `Shazam`).")
        return

    # "Sevgi ortidan 7" -> base + episode
    m = re.match(r"^(.*?)(?:\s+(\d{1,3}))?$", query)
    base = (m.group(1) or "").strip() if m else query
    episode = m.group(2) if m else None

    # ✅ find_top_movies sync qoladi (await QO'YMAYSIZ)
    items = await find_top_movies(base)

    if items and episode:
        epn = int(episode)

        def ep_match(it: dict) -> int:
            _, e = extract_episode(it.get("title", ""))
            return 0 if e == epn else 1

        items.sort(key=ep_match)

    if not items:
        kb = InlineKeyboardBuilder()
        kb.button(text="👤 Adminga yozish", url="https://t.me/Mozcyberr")
        await message.answer(
            "❌ Kino hali botga qo‘shilmagan yoki nomida adashgansiz.\nAdminga murojaat qiling 👇",
            reply_markup=kb.as_markup()
        )
        return

    if len(items) == 1:
        it = items[0]
        ok = await safe_copy_with_ttl(
            bot=message.bot,
            chat_id=message.from_user.id,
            from_chat_id=int(it["channel_id"]),
            message_id=int(it["message_id"]),
            ttl_sec=6 * 60 * 60,
            protect=True,
            disable_notification=True,
        )
        if not ok:
            await delete_movie_by_message_id(int(it["message_id"]), int(it["channel_id"]))
            await message.answer("❌ Bu kino kanaldan o‘chirilgan.")
            return

    token = uuid.uuid4().hex[:10]
    SEARCH_CACHE[token] = {"user_id": message.from_user.id, "items": items, "ts": time.time()}

    total_pages = (len(items) - 1) // PAGE_SIZE + 1
    kb = build_keyboard(token, page=0, items=items)
    await message.answer(
        f"Topilgan eng yaqin kinolar: {len(items)} ta. (Sahifa 1/{total_pages})",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("nav:"))
async def nav_callback(call: types.CallbackQuery):
    _cleanup_cache()

    try:
        _, token, page_s = call.data.split(":")
        page = int(page_s)
    except Exception:
        await call.answer("Noto‘g‘ri tugma.", show_alert=True)
        return

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


@router.callback_query(F.data.startswith("movie:"))
async def movie_callback(call: types.CallbackQuery):
    _cleanup_cache()

    if not call.message:
        await call.answer("Bu tugma eskirgan. Qaytadan qidirib ko‘ring.", show_alert=True)
        return

    try:
        _, token, msg_s = call.data.split(":", 2)
        msg_id = int(msg_s)
    except Exception:
        await call.answer("Callback ma’lumoti buzilgan. Qayta qidirib ko‘ring.", show_alert=True)
        return

    data = SEARCH_CACHE.get(token)
    if not data or data.get("user_id") != call.from_user.id:
        await call.answer("Bu tugma eskirgan. Qayta qidirib ko‘ring.", show_alert=True)
        return

    ok = await safe_copy_with_ttl(
        bot=call.message.bot,
        chat_id=call.from_user.id,
        from_chat_id=CHANNEL_ID,
        message_id=msg_id,
        ttl_sec=6 * 60 * 60,
        protect=True,
        disable_notification=True,
    )

    if ok:
        await call.answer()
        return

    # source o'chgan bo'lsa: DBdan o'chiramiz (async)
    try:
        await delete_movie_by_message_id(msg_id, CHANNEL_ID)
    except Exception:
        logger.exception("delete_movie_by_message_id failed")

    # cache dan olib tashlash
    items = data.get("items") or []
    data["items"] = [
        it for it in items
        if not (
            int(it.get("message_id", -1)) == msg_id and
            int(it.get("channel_id", -1)) == CHANNEL_ID
        )
    ]

    # UI update
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
        if "message is not modified" not in str(e):
            raise
    except Exception:
        logger.exception("UI update failed")

    await call.answer("Bu kino kanaldan o‘chirilgan.", show_alert=True)