
import time
import requests
from dropbox_writer import upload_signal_to_dropbox
from utils import split_signals, log_to_google_sheets
import os

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHAT_ID"))
API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

async def process_sanitized_signal(text: str):
    signals = split_signals(text)

    for signal in signals:
        print(signal)
        try:
            res = requests.post(f"{API_URL}/sendMessage", json={
                "chat_id": TARGET_CHANNEL_ID,
                "text": signal
            })
            res.raise_for_status()
            upload_signal_to_dropbox(signal)
            log_to_google_sheets(signal)
            print("✅ Signal processed and logged.")
        except Exception as e:
            print("❌ Error sending or logging signal:", e)
