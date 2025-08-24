import os
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, SESSION_PATH

async def create_session_env():
    client = TelegramClient(SESSION_PATH, TELEGRAM_API_ID, TELEGRAM_API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        phone = os.environ.get("PHONE_NUMBER")
        login_code = os.environ.get("LOGIN_CODE")
        two_fa = os.environ.get("TWO_FA_PASSWORD")

        if not phone or not login_code:
            raise RuntimeError("PHONE_NUMBER and LOGIN_CODE env variables are required")

        await client.send_code_request(phone)
        try:
            await client.sign_in(phone, login_code)
        except SessionPasswordNeededError:
            if two_fa:
                await client.sign_in(password=two_fa)
            else:
                raise RuntimeError("2FA password required but not provided")

    await client.disconnect()

def get_client():
    return TelegramClient(SESSION_PATH, TELEGRAM_API_ID, TELEGRAM_API_HASH)
