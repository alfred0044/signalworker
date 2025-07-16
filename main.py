import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
from filters import should_ignore_message
from telethon import TelegramClient, events
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from datetime import datetime
from filters import is_trade_signal
from sanitizer import sanitize_with_ai
from signal_processor import process_sanitized_signal
from client_factory import get_client
import traceback



# Load environment variables

# Load channel IDs from environment
SOURCE_CHANNEL_IDS = [int(cid) for cid in os.getenv("SOURCE_CHANNEL_IDS", "").split(',') if cid.strip()]

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
ENVIRONMENT = os.getenv("ENVIRONMENT", "test")  # e.g., 'test' or 'prod'

# Set session file name based on environment
SESSION_NAME = f"signal_splitter_{ENVIRONMENT}.session"
SESSION_B64 = f"{SESSION_NAME}.b64"

print(f"{SESSION_NAME}.b64")
# Decode .b64 to .session if not already decoded
if not os.path.exists(SESSION_NAME) and os.path.exists(SESSION_B64):
    print(f"🔐 Decoding session file for {ENVIRONMENT}...")
    with open(SESSION_B64, "rb") as f_in, open(SESSION_NAME, "wb") as f_out:
        f_out.write(base64.b64decode(f_in.read()))
    print("✅ Session file decoded.")
print(os.path.exists(SESSION_NAME))
print(os.path.exists(SESSION_B64))
def get_client() -> TelegramClient:
    return TelegramClient(SESSION_NAME, API_ID, API_HASH)
async def main():
    # Get a properly initialized client
    client = get_client()


    # Define the handler INSIDE main to ensure `client` is valid
    @client.on(events.NewMessage(chats=SOURCE_CHANNEL_IDS))
    async def handler(event):
        text = event.message.message
        if not is_trade_signal(text):
            return

        try:
            print("main_sanitized")
            source_name = event.chat.title if event.chat and hasattr(event.chat, 'title') else "Unknown"
            message_link = None

            if event.chat and hasattr(event.chat, 'username') and event.chat.username:
                message_link = f"https://t.me/{event.chat.username}/{event.message.id}"

            message_time = event.message.date.isoformat() + 'Z'

            if should_ignore_message(text):
                print("⚠️ Ignored non-signal message.")
                return None  # or []

            print("main_sanitized")
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

    # Start and keep running
    await client.start()

    print("✅ Telegram client started.")
    print("📥 Fetching dialogs (channels, groups, chats)...")
    dialogs = await client(GetDialogsRequest(
        offset_date=None,
        offset_id=0,
        offset_peer=InputPeerEmpty(),
        limit=200,
        hash=0
    ))

    print("📋 Your accessible channels and their IDs:")
    for chat in dialogs.chats:
        if getattr(chat, "title", None):
            print(f"• {chat.title} — ID: {chat.id}")

    print("✅ Client started and listening for new messages.")
    # Optional: fetch dialogs for testing


    # Optionally print dialog names
    # for dialog in dialogs.chats:
    #     print(f"{dialog.id}: {dialog.title}")

    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
