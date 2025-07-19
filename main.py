import asyncio
import base64
import os
import sys
import traceback
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty

# Custom imports
from filters import should_ignore_message, is_trade_signal
from sanitizer import sanitize_with_ai
from signal_processor import process_sanitized_signal

# Load environment variables
load_dotenv()

# -----------------------
# CONFIGURATION
# -----------------------

ENVIRONMENT = os.getenv("ENVIRONMENT", "test")  # default to 'test' if not set

TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")

# Convert comma-separated string to list of ints
SOURCE_CHANNEL_IDS = [
    int(cid.strip()) for cid in os.getenv("SOURCE_CHANNEL_IDS", "").split(",") if cid.strip()
]

LOCAL_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "data"))

# Determine correct session directory
if ENVIRONMENT == "prod":
    if sys.platform.startswith("win"):
        SESSION_DIRECTORY = LOCAL_DATA_DIR
        print(f"📦 Running 'prod' on Windows — session dir: {SESSION_DIRECTORY}")
    else:
        SESSION_DIRECTORY = "/data"
        print(f"📦 Running 'prod' on Linux — session dir: {SESSION_DIRECTORY}")
else:
    SESSION_DIRECTORY = "."
    print(f"🧪 Running in environment '{ENVIRONMENT}' — using local session dir.")

SESSION_NAME = f"signal_splitter_{ENVIRONMENT}.session"
SESSION_B64 = f"{SESSION_NAME}.b64"
SESSION_PATH = os.path.join(SESSION_DIRECTORY, SESSION_NAME)
SESSION_B64_PATH = os.path.join(SESSION_DIRECTORY, SESSION_B64)

# -----------------------
# SESSION FILE HANDLING
# -----------------------

if ENVIRONMENT == "prod":
    if not os.path.exists(SESSION_PATH):
        if os.path.exists(SESSION_B64_PATH):
            try:
                print(f"🔐 Decoding session from: {SESSION_B64_PATH}...")
                with open(SESSION_B64_PATH, "rb") as f_in, open(SESSION_PATH, "wb") as f_out:
                    f_out.write(base64.b64decode(f_in.read()))
                print("✅ Session file decoded successfully.")
            except Exception as e:
                print("❌ Failed to decode session file:", e)
                print(traceback.format_exc())
        else:
            print(f"❌ .b64 session not found at {SESSION_B64_PATH}")
    else:
        print(f"✅ Session file found at {SESSION_PATH}")
else:
    print(f"ℹ️ Skipping session decoding in non-prod env.")

# -----------------------
# CREATE TELETHON CLIENT
# -----------------------

def get_client() -> TelegramClient:
    return TelegramClient(SESSION_PATH, TELEGRAM_API_ID, TELEGRAM_API_HASH)

# -----------------------
# MAIN SERVICE LOGIC
# -----------------------

async def main():
    while True:
        try:
            print("🚀 Initializing Telegram client...")
            client = get_client()
            await client.connect()

            if not await client.is_user_authorized():
                print("❌ Telegram client not authorized. Session file may be missing or invalid.")
                print("🔁 Retrying in 60 seconds...")
                await asyncio.sleep(60)
                continue

            print("✅ Telegram client is authorized ✔️")
            print("📋 Watching channels:", SOURCE_CHANNEL_IDS)

            @client.on(events.NewMessage(chats=SOURCE_CHANNEL_IDS))
            async def handler(event):
                text = event.message.message
                if not is_trade_signal(text):
                    return

                try:
                    source_name = getattr(event.chat, 'title', 'Unknown')
                    message_link = None

                    if hasattr(event.chat, 'username') and event.chat.username:
                        message_link = f"https://t.me/{event.chat.username}/{event.message.id}"

                    message_time = event.message.date.isoformat() + 'Z'

                    if should_ignore_message(text):
                        print("⚠️ Ignored non-signal message.")
                        return

                    print("🧪 Sanitizing signal...")
                    sanitized = await sanitize_with_ai(text)

                    await process_sanitized_signal(
                        sanitized,
                        source=source_name,
                        link=message_link,
                        timestamp=message_time
                    )

                except Exception as e:
                    print("❌ Error processing message:", e)
                    print(traceback.format_exc())

            await client.start()
            print("✅ Client started — waiting for messages.")
            await client(GetDialogsRequest(
                offset_date=None,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=200,
                hash=0
            ))

            await client.run_until_disconnected()

        except Exception as e:
            print("❌ Fatal error during startup or running:")
            print(traceback.format_exc())
            print("🔄 Retrying in 60 seconds...")
            await asyncio.sleep(60)

# -----------------------
# ENTRY POINT
# -----------------------

if __name__ == "__main__":
    asyncio.run(main())
