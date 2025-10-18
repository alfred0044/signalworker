import asyncio
import os
import sys
import traceback
from dotenv import load_dotenv
from fastapi import FastAPI, Request
import uvicorn

from telethon import TelegramClient
from telethon.sessions import StringSession
from handlers import register_handlers
from config import SOURCE_CHANNEL_IDS
from signal_db import init_db

init_db()
load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_STRING = os.getenv("TELEGRAM_STRING_SESSION")
PHONE = os.getenv("TELEGRAM_PHONE")  # store your phone number here

app = FastAPI()
pending_clients = {}   # store temporary TelegramClients awaiting login


async def create_stringsession_interactive():
    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        await client.start()
        print("🔑 StringSession:", client.session.save())


def get_client():
    if not SESSION_STRING:
        raise RuntimeError("TELEGRAM_STRING_SESSION fehlt in den Umgebungsvariablen!")
    return TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


# ---------- FastAPI — remote session endpoints ----------

@app.get("/login/start")
async def login_start():
    """Starts the login process by sending a Telegram login code."""
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    await client.send_code_request(PHONE)
    pending_clients[PHONE] = client
    return {"status": "code_sent", "message": f"Login code sent to {PHONE}"}


@app.get("/login/verify")
async def login_verify(code: str, password: str | None = None):
    """Verifies the code and returns a StringSession."""
    client = pending_clients.get(PHONE)
    if not client:
        return {"error": "no_pending_login"}

    try:
        await client.sign_in(phone=PHONE, code=code)
    except Exception:
        if password:
            await client.sign_in(phone=PHONE, password=password)
        else:
            raise
    string = client.session.save()
    await client.disconnect()
    return {"session_string": string}


# ---------- main bot runtime ----------

async def main():
    if len(sys.argv) > 1 and sys.argv[1] == "create_session":
        await create_stringsession_interactive()
        return

    # On Railway, start FastAPI only if session missing
    if not SESSION_STRING:
        print("Starting temporary login server...")
        config = uvicorn.Config(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
        server = uvicorn.Server(config)
        await server.serve()
        return

    while True:
        try:
            client = get_client()
            await client.connect()

            if not await client.is_user_authorized():
                print("❌ Telegram client not authorized. StringSession ist evtl. ungültig.")
                await asyncio.sleep(60)
                continue

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
