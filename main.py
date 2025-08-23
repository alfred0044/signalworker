import asyncio
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
ENVIRONMENT = "prod"  # override as needed

TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")

# Convert comma-separated string to list of ints
SOURCE_CHANNEL_IDS = [
    int(cid.strip()) for cid in os.getenv("SOURCE_CHANNEL_IDS", "").split(",") if cid.strip()
]

LOCAL_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "data"))

# Determine session directory based on environment and platform
if ENVIRONMENT == "prod":
    if sys.platform.startswith("win"):
        SESSION_DIRECTORY = LOCAL_DATA_DIR
        print(f"📦 Running 'prod' on Windows — session dir: {SESSION_DIRECTORY}")
    else:
        SESSION_DIRECTORY = "/data/storage"
        print(f"📦 Running 'prod' on Linux — session dir: {SESSION_DIRECTORY}")
else:
    SESSION_DIRECTORY = "."
    print(f"🧪 Running in environment '{ENVIRONMENT}' — using local session dir.")

SESSION_NAME = f"signal_splitter_{ENVIRONMENT}.session"
SESSION_PATH = os.path.join(SESSION_DIRECTORY, SESSION_NAME)

# -----------------------
# SESSION CREATION (only if create_session parameter passed)
# -----------------------

if len(sys.argv) > 1 and sys.argv[1] == "create_session":
    from telethon.sync import TelegramClient

    client = TelegramClient(SESSION_PATH, TELEGRAM_API_ID, TELEGRAM_API_HASH)

    async def create_session():
        await client.start()
        print("✅ Session created and authorized!")
        print(f"📦 Saved session file: {SESSION_PATH}")
        await client.disconnect()

    client.loop.run_until_complete(create_session())
    sys.exit()

# -----------------------
# VERIFY SESSION FILE PRESENCE
# -----------------------

if not os.path.exists(SESSION_PATH):
    print(f"❌ Session file not found at {SESSION_PATH}. Please create session using 'create_session' option.")
else:
    print(f"✅ Session file found at {SESSION_PATH}")

# -----------------------
# TELETHON CLIENT FACTORY
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
            await client.get_dialogs()

            if not await client.is_user_authorized():
                print("❌ Telegram client not authorized. Session file may be missing or invalid.")
                print("🔁 Retrying in 60 seconds...")
                await asyncio.sleep(600)
                continue

            print("✅ Telegram client is authorized ✔️")

            dialogs = await client.get_dialogs()
            for dialog in dialogs:
                if abs(dialog.id) in SOURCE_CHANNEL_IDS:
                    print(dialog.name, dialog.id, "✅")
                else:
                    print(dialog.name, dialog.id, "❌")

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

        except Exception:
            print("❌ Fatal error during startup or running:")
            print(traceback.format_exc())
            print("🔄 Retrying in 60 seconds...")
            await asyncio.sleep(60)

# -----------------------
# ENTRY POINT
# -----------------------

if __name__ == "__main__":
    asyncio.run(main())
