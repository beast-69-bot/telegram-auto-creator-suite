import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

# Telegram API Credentials (from https://my.telegram.org)
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

# Main Bot Token (from @BotFather)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Admin ID (Only authorized users or empty for open use)
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

# Storage paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PICS_DIR = os.path.join(DATA_DIR, "pics")
DB_PATH = os.path.join(DATA_DIR, "auto_creator.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(PICS_DIR, exist_ok=True)
