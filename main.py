import asyncio
import base64
import os
import sys
import traceback
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from filters import should_ignore_message
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from filters import is_trade_signal
from sanitizer import sanitize_with_ai
from signal_processor import process_sanitized_signal

# -----------------------
# CONFIGURATION
# -----------------------

ENVIRONMENT = os.getenv("ENVIRONMENT", "test")
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
SOURCE_CHANNEL_IDS = [
    int(cid.strip()) for cid in os.getenv("SOURCE_CHANNEL_IDS", "").split(",") if cid.strip()
]

LOCAL_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "data"))

# Determine correct session directory
if ENVIRONMENT == "prod":
    if sys.platform.startswith("win"):
        SESSION_DIRECTORY = LOCAL_DATA_DIR
    else:
        SESSION_DIRECTORY = "/data"
else:
    SESSION_DIRECTORY = "."

SESSION_NAME = f"signal_splitter_{ENVIRONMENT}.session"
SESSION_B64 = f"{SESSION_NAME}.b64"
SESSION_PATH = os.path.join(SESSION_DIRECTORY, SESSION_NAME)
SESSION_B64_PATH = os.path.join(SESSION_DIRECTORY, SESSION_B64)

# Decode Base64 session file if necessary
if ENVIRONMENT == "prod":
    if not os.path.exists(SESSION_PATH):
        if os.path.exists(SESSION_B64_PATH):
            try:
                print(f"🔐 Decoding session file from {SESSION_B64_PATH}...")
                with open(SESSION_B64_PATH, "rb") as f_in, open(SESSION_PATH, "wb") as f_out:
                    f_out.write(base64.b64decode(f_in.read()))
                print("✅ Session file decoded.")
            except Exception as e:
                print("❌ Failed to decode session file:", str(e))
                print(traceback.format_exc())
        else:
            print(f"❌ .b64 session not found at {SESSION_B64_PATH}")
    else:
        print(f"✅ Session file found at {SESSION_PATH}")


# -----------------------
# CLIENT FACTORY & MAIN
# -----------------------

def get_client() -> TelegramClient:
    return TelegramClient(SESSION_PATH, TELEGRAM_API_ID, TELEGRAM_API_HASH)

async def main():
    try:
        client = get_client()
        await client.connect()

        if not await client.is_user_authorized():
            print("❌ Telegram client is not authorized.")
            return

        print("✅ Telegram client connected.")

        @client.on(events.NewMessage(chats=SOURCE_CHANNEL_IDS))
        async def handler(event):
            text = event.message.message
            if not is_trade_signal(text):
                return

            try:
                print("main_sanitized")
                source_name = getattr(event.chat, 'title', 'Unknown')
                message_link = None

                if hasattr(event.chat, 'username') and event.chat.username:
                    message_link = f"https://t.me/{event.chat.username}/{event.message.id}"

                message_time = event.message.date.isoformat() + 'Z'

                if should_ignore_message(text):
                    print("⚠️ Ignored non-signal message.")
                    return

                sanitized = await sanitize_with_ai(text)
                await process_sanitized_signal(
                    sanitized,
                    source=source_name,
                    link=message_link,
                    timestamp=message_time
                )

            except Exception as e:
                print("❌ Error in message handler:", e)
                print(traceback.format_exc())

        await client.start()
        print("📥 Listening for messages...")
        await client.run_until_disconnected()

    except Exception as e:
        print("❌ Failed to initialize or run Telegram client:")
        print(traceback.format_exc())
        # Optionally keep the service alive or retry
        while True:
            print("🔁 Retrying in 60 seconds...")
            await asyncio.sleep(60)
            # Retry logic here, or just stay alive

# Entrypoint
if __name__ == "__main__":
    asyncio.run(main())
