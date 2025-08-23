import asyncio
import os
import pathlib
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
# Determine session directory based on environment
if ENVIRONMENT == "prod":
    # Railway Linux environment folder - use explicit POSIX style string
    SESSION_DIRECTORY = "/data/storage"
    SESSION_NAME = f"signal_splitter_{ENVIRONMENT}.session"
    SESSION_PATH = f"{SESSION_DIRECTORY}/{SESSION_NAME}"
else:
    # Local development folder - use pathlib for OS-agnostic paths
    import pathlib
    SESSION_DIRECTORY = pathlib.Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "data")))
    SESSION_NAME = f"signal_splitter_{ENVIRONMENT}.session"
    SESSION_PATH = str(SESSION_DIRECTORY / SESSION_NAME)

os.makedirs(os.path.dirname(SESSION_PATH), exist_ok=True)
print(f"SESSION_DIRECTORY: '{SESSION_DIRECTORY}'")
print(f"SESSION_NAME: '{SESSION_NAME}'")
print(f"SESSION_PATH: '{SESSION_PATH}'")

# Use SESSION_PATH_POSIX string when passing to Telethon client to ensure correct Linux path


# -----------------------
# SESSION CREATION (only if create_session parameter passed)
# -----------------------

if len(sys.argv) > 1 and sys.argv[1] == "create_session":
    from telethon.sync import TelegramClient

    client = TelegramClient(SESSION_PATH, TELEGRAM_API_ID, TELEGRAM_API_HASH)

    async def create_session():
        await client.start()
        print("✅ Session created and authorized!")
        print(f"📦 Saved session file at: {SESSION_PATH}")
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

async def wait_for_session():
    while not os.path.exists(SESSION_PATH):
        print(f"❌ Session file not found at {SESSION_PATH}. Retrying in 60 seconds...")
        await asyncio.sleep(60)
    print(f"✅ Session file found at {SESSION_PATH}.")


async def main():
    await wait_for_session()

    while True:
        try:
            print("🚀 Initializing Telegram client...")
            client = get_client()
            await client.connect()

            # Authorization check
            if not await client.is_user_authorized():
                print("❌ Telegram client not authorized. Session file may be invalid.")
                print("🔁 Retrying in 60 seconds...")
                await asyncio.sleep(60)
                continue

            print("✅ Telegram client is authorized ✔️")

            # Rest of your dialog fetching and message handling logic here
            dialogs = await client.get_dialogs()
            for dialog in dialogs:
                if abs(dialog.id) in SOURCE_CHANNEL_IDS:
                    print(dialog.name, dialog.id, "✅")
                else:
                    print(dialog.name, dialog.id, "❌")

            @client.on(events.NewMessage(chats=SOURCE_CHANNEL_IDS))
            async def handler(event):
                # Your message processing logic here
                pass

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


if __name__ == "__main__":
    asyncio.run(main())