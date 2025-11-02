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
from fastapi.responses import HTMLResponse
from fastapi import FastAPI, Request, Form
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

@app.get("/", response_class=HTMLResponse)
async def root():
    phone = PHONE or ""
    return f"""
    <h2>Telegram Session Login</h2>
    <form action="/login/start" method="post">
        Telefonnummer: <input type="text" name="phone" value="{phone}" required><br>
        <input type="submit" value="Login-Code senden">
    </form>
    <p>Nach Erhalt des Codes bitte auf <a href="/code">Code-Eingabe</a> gehen.</p>
    """

@app.post("/login/start")
async def login_start_form(phone: str = Form(...)):
    global PHONE
    PHONE = phone
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    await client.send_code_request(phone)
    pending_clients[phone] = client
    return HTMLResponse(f"""
    <p>Login-Code an {phone} gesendet.</p>
    <a href="/code">Weiter zur Code-Eingabe</a>
    """)

@app.get("/code", response_class=HTMLResponse)
async def code_form():
    return """
    <h3>Gib hier den Telegram-Code ein:</h3>
    <form action="/login/verify" method="post">
        Code: <input name="code" required><br>
        2FA-Passwort (falls aktiv): <input name="password" type="password"><br>
        <input type="submit" value="Session erstellen">
    </form>
    """

@app.post("/login/verify", response_class=HTMLResponse)
async def login_verify_form(code: str = Form(...), password: str = Form(None)):
    client = pending_clients.get(PHONE)
    if not client:
        return HTMLResponse("<p>Keine Anmeldung aktiv. Bitte neu starten.</p>", status_code=400)
    try:
        await client.sign_in(phone=PHONE, code=code)
    except Exception:
        if password:
            await client.sign_in(password=password)
        else:
            return HTMLResponse("<p>2FA benötigt, aber kein Passwort angegeben.</p>", status_code=400)
    session_string = client.session.save()
    await client.disconnect()
    # Optionally clear pending client
    del pending_clients[PHONE]
    return f"""
    <h3>Session erfolgreich erstellt!</h3>
    <textarea rows="4" cols="60" readonly>{session_string}</textarea><br>
    <button onclick="navigator.clipboard.writeText(document.querySelector('textarea').value)">
      Kopieren
    </button>
    <p>Bitte kopiere diesen String in deine Umgebungsvariablen (TELEGRAM_STRING_SESSION) auf Railway.</p>
    """
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
