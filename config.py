# TikTok Telegram Bot Configuration

import os
from pathlib import Path

# Bot Configuration
BOT_TOKEN = "8218958423:AAEQaY7q1eN7Xb1umG5G98cE7fFfqPummtI"
BOT_USERNAME = "@tiktokrs_bot"
DEBUG_MODE = False

# Paths
BASE_DIR = Path(__file__).parent
DOWNLOAD_DIR = BASE_DIR / "downloads"

# Create download directory if it doesn't exist
DOWNLOAD_DIR.mkdir(exist_ok=True)

# TikTok URL patterns
TIKTOK_PATTERNS = [
    r'https?://(?:www\.)?tiktok\.com/@[\w.-]+/video/\d+',
    r'https?://(?:vm|vt)\.tiktok\.com/\w+',
    r'https?://(?:www\.)?tiktok\.com/t/\w+',
]
