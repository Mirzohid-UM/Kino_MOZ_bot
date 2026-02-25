rom
dotenv
import load_dotenv

load_dotenv()
import asyncio
import logging
from aiogram import Bot, Dispatcher
from handlers import admin_broadcast
from config import TOKEN, CHANNEL_ID
from db import init_db
from utils.sub_notifier import run_sub_expiry_notifier

from aiogram import Dispatcher
from db.core import init_pool
from config import DATABASE_URL

from handlers.admin_subs import router as admin_subs_router

from handlers.admin import router as admin_router
from handlers.start import router as start_router
from handlers.access import router as access_router
from handlers.search import router as search_router
from handlers.channel import router as channel_router

# ---------------- LOGGING ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

init_db()


async def on_startup(dispatcher: Dispatcher):
    await init_pool(DATABASE_URL, min_size=1, max_size=10)


async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    # Router tartibi:
    # 1) admin komandalar
    dp.include_router(admin_router)
    dp.include_router(admin_subs_router)
    dp.include_router(admin_broadcast.router)

    # 2) /start
    dp.include_router(start_router)
    # 3) access callbacklar
    dp.include_router(access_router)
    # 4) qidiruv (oddiy textni ushlaydi)
    dp.include_router(search_router)

    # 5) kanal postlari
    dp.include_router(channel_router)

    # Global error handler
    @dp.errors()
    async def global_error_handler(event):
        exc = getattr(event, "exception", event)
        upd = getattr(event, "update", None)
        upd_id = getattr(upd, "update_id", None)
        logger.exception(f"Unhandled error (update_id={upd_id})", exc_info=exc)
        return True

    chat = await bot.get_chat(CHANNEL_ID)
    logger.info(f"Bot started. Kanal: {chat.title} ({chat.id})")
    # bot yaratilgandan keyin, pollingdan oldin:
    asyncio.create_task(
        run_sub_expiry_notifier(bot, admin_url="https://t.me/Mozcyberr", interval_sec=600)
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
