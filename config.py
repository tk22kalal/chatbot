#(©)CodeXBotz - Modified for Anonymous Chat Bot

import os
import logging
from logging.handlers import RotatingFileHandler

# Bot token @Botfather
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")

# Your API ID from my.telegram.org
APP_ID = int(os.environ.get("APP_ID", "0"))

# Your API Hash from my.telegram.org
API_HASH = os.environ.get("API_HASH", "")

# Your db channel Id (for logging chats)
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "0"))

# OWNER ID
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# Port (for Heroku)
PORT = os.environ.get("PORT", "8080")

# Database 
DB_URI = os.environ.get("DATABASE_URL", "")
DB_NAME = os.environ.get("DATABASE_NAME", "anonchats")

# Force sub channel id (optional)
FORCE_SUB_CHANNEL = int(os.environ.get("FORCE_SUB_CHANNEL", "0"))

TG_BOT_WORKERS = int(os.environ.get("TG_BOT_WORKERS", "4"))

# Admin list
try:
    ADMINS = []
    for x in (os.environ.get("ADMINS", "").split()):
        ADMINS.append(int(x))
except ValueError:
    raise Exception("Your Admins list does not contain valid integers.")

ADMINS.append(OWNER_ID)

# Bot Messages
START_MSG = """
👋 Welcome to Anonymous Chat Bot!

To get started, please select your gender:
"""

PARTNER_FOUND_MSG = """
Partner found 😺

/next — find a new partner
/stop — stop this chat

`https://t.me/ChatbotXY_bot`
"""

PARTNER_LEFT_MSG = """
Your partner has stopped the chat 😞
Type /search to find a new partner
"""

SEARCHING_MSG = "Looking for a partner... please wait ⏳"

STOPPED_CHAT_MSG = "Chat stopped. Type /search to find a new partner."

# Logging Configuration
LOG_FILE_NAME = "anonchats.txt"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt='%d-%b-%y %H:%M:%S',
    handlers=[
        RotatingFileHandler(
            LOG_FILE_NAME,
            maxBytes=50000000,
            backupCount=10
        ),
        logging.StreamHandler()
    ]
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
