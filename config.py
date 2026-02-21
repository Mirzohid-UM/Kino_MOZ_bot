# config.py
import os
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv("TOKEN", "")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
DATABASE_URL = os.getenv("DATABASE_URL", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ADMIN_IDS = os.getenv("ADMIN_IDS","")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN is missing. Set it in .env or environment variables.")











