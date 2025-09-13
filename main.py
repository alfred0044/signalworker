import asyncio
import os
import sys
import re
import traceback
from dotenv import load_dotenv
from handlers import register_handlers
from config import SOURCE_CHANNEL_IDS

from telethon import TelegramClient
from telethon.sessions import StringSession
from signal_db import init_db
init_db()
load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_STRING = os.getenv("TELEGRAM_STRING_SESSION")

async def create_stringsession():
    # Interaktiver Modus: Session-String generieren (nur lokal, nicht Railway!)
    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        await client.start()
        print("🔑 StringSession:", client.session.save())

def get_client():
    if not SESSION_STRING:
        raise RuntimeError("TELEGRAM_STRING_SESSION fehlt in den Umgebungsvariablen!")
    return TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

async def main():
    # Optional: interaktive StringSession-Erstellung
    if len(sys.argv) > 1 and sys.argv[1] == "create_session":
        await create_stringsession()
        return

    while True:
        try:
            client = get_client()
            await client.connect()

            if not await client.is_user_authorized():
                print("❌ Telegram client not authorized. StringSession ist evtl. ungültig.")
                await asyncio.sleep(60)
                continue

            # Handler registrieren (deine Funktionen)
            register_handlers(client, SOURCE_CHANNEL_IDS)

            dialogs = await client.get_dialogs()
            for dialog in dialogs:
                if abs(dialog.id) in SOURCE_CHANNEL_IDS:
                    print(dialog.name, dialog.id, "✅")
                else:
                    print(dialog.name, dialog.id, "❌")

            print("✅ Client gestartet — wartet auf Nachrichten.")
            await client.run_until_disconnected()

        except Exception:
            print("❌ Fatal error during runtime:")
            print(traceback.format_exc())
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
