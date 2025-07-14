
import asyncio
from telethon import TelegramClient, events
from dotenv import load_dotenv
import os

from filters import is_trade_signal
from sanitizer import sanitize_with_ai
from signal_processor import process_sanitized_signal

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_NAME = "signal_splitter"

SOURCE_CHANNEL_IDS = [int(cid) for cid in os.getenv("SOURCE_CHANNEL_IDS").split(',')]

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


@client.on(events.NewMessage(chats=SOURCE_CHANNEL_IDS))

async def handler(event):
    text = event.message.message
    if not is_trade_signal(text):
        return

    try:
        sanitized = await sanitize_with_ai(text)
        await process_sanitized_signal(sanitized)
    except Exception as e:
        print("❌ Error processing message:", e)


async def main():
    await client.start()
    print("✅ Bot is running.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
