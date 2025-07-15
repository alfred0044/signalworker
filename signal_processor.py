from datetime import datetime
import json
import time
import traceback

import requests
from dropbox_writer import upload_signal_to_dropbox
from utils import split_signals, log_to_google_sheets
import os

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHAT_ID"))
API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

async def process_sanitized_signal(text: str, source: str = "Unknown"):
    signal = text.upper()
    signal_data = json.loads(signal)

    for item in signal_data:
        item["SOURCE"] = source  # ← set from channel
        item["TIME"] = datetime.utcnow().isoformat() + 'Z'

    try:
        # Optional: send a pretty version to Telegram for debugging
        res = requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": TARGET_CHANNEL_ID,
            "text": json.dumps(signal_data, indent=2),
            "parse_mode": "Markdown"
        })
        res.raise_for_status()

        upload_signal_to_dropbox(signal_data)
        print("✅ Signal processed and logged.")
    except Exception as e:
        print("❌ Error sending or logging signal:", traceback.format_exc())

