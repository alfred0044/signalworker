import os
import base64
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
ENVIRONMENT = os.getenv("ENVIRONMENT", "test")  # e.g., 'test' or 'prod'

# Set session file name based on environment
SESSION_NAME = f"signal_splitter_{ENVIRONMENT}.session"
SESSION_B64 = f"{SESSION_NAME}.b64"

# Decode .b64 to .session if not already decoded

def get_client() -> TelegramClient:
    return TelegramClient(SESSION_PATH, API_ID, API_HASH)