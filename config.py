import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "0").split(",")))

    MAX_FILE_SIZE = 1024 * 1024 * 1024  # 1GB

    DAILY_LIMIT = 100

    DATABASE_URL = "sqlite:///bot.db"
    TEMP_DIR = "temp"
    DOWNLOAD_TIMEOUT = 300

    SUPPORTED_PLATFORMS = [
        "youtube.com", "youtu.be", "instagram.com", "tiktok.com",
        "twitter.com", "x.com", "facebook.com", "fb.watch",
        "reddit.com", "vimeo.com", "dailymotion.com", "twitch.tv"
    ]
