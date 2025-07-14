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
if not os.path.exists(SESSION_NAME) and os.path.exists(SESSION_B64):
    print(f"🔐 Decoding session file for {ENVIRONMENT}...")
    with open(SESSION_B64, "rb") as f_in, open(SESSION_NAME, "wb") as f_out:
        f_out.write(base64.b64decode(f_in.read()))
    print("✅ Session file decoded.")

def get_client() -> TelegramClient:
    return TelegramClient(SESSION_NAME, API_ID, API_HASH)