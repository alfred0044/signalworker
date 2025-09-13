import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
import concurrent.futures
import os
from dotenv import load_dotenv
load_dotenv()
api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")

async def main():
    client = TelegramClient(StringSession(), api_id, api_hash)

    async def get_phone():
        return input("Bitte Telefonnummer eingeben (mit Ländervorwahl): ")

    async def get_code():
        return input("Bitte den Code eingeben, den du erhalten hast: ")

    async def get_password():
        return input("Bitte dein 2FA-Passwort eingeben: ")

    await client.start(
        phone=get_phone,
        code_callback=get_code,
        password=get_password
    )

    print("Login erfolgreich!")
    print("Deine Session als String:")
    print(client.session.save())

    print("Client läuft. STRG+C zum Beenden.")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())