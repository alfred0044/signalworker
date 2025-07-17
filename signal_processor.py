from datetime import datetime
import json
import time
import traceback
import uuid
import requests
from dropbox_writer import upload_signal_to_dropbox
from utils import split_signals, log_to_google_sheets
import os

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHAT_ID"))
API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


async def process_sanitized_signal(text: str, source: str = "Unknown", link: str = None, timestamp: str = None):
    try:
        signal_json = json.loads(text)  # ✅ Removed .upper()
    except json.JSONDecodeError:
        print("❌ Invalid JSON format.")
        return

    if not isinstance(signal_json, dict) or "signals" not in signal_json:
        print("❌ Invalid signal format. Expected top-level 'signals' key.")
        return
    signalid = int(uuid.uuid4())
    for item in signal_json["signals"]:
        item["source"] = source
        item["signalid"] = signalid

        dt = timestamp or datetime.utcnow()
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt.replace("Z", "").replace("+00:00", ""))
            except:
                dt = datetime.utcnow()

        item["time"] = dt.strftime("%Y-%m-%d %H:%M:%S")

        if link:
            item["link"] = link

    try:
        requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": TARGET_CHANNEL_ID,
            "text": json.dumps(signal_json, indent=2)
        })

        upload_signal_to_dropbox(signal_json)
        print("✅ Signal processed and logged.")
    except Exception as e:
        print("❌ Error sending or logging signal:", traceback.format_exc())