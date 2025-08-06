from datetime import datetime
import json
import time
import traceback
import uuid
from typing import Dict, Any
import requests
from dropbox_writer import upload_signal_to_dropbox
from utils import split_signals, log_to_google_sheets
import os


TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHAT_ID"))
API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
confirmation_message =" "

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
        confirmation_message = format_for_confirmation(item)
    try:

    #    response =  requests.post(f"{API_URL}/sendMessage", json={
    #        "chat_id": TARGET_CHANNEL_ID,
    #        "text":confirmation_message
    #    }    )
        print (response.content)
        if response.status_code == 200:
            print("Message sent successfully!")
        else:
            print(f"Failed to send message. Status code: {response.status_code}")

        upload_signal_to_dropbox(signal_json)
        print("✅ Signal processed and logged.")
    except Exception as e:
        print("❌ Error sending or logging signal:", traceback.format_exc())

def format_for_confirmation(signal: Dict[str, Any]) -> str:
    return (
        f"📥 *New Signal Detected:*\n"
        f"*Instrument:* `{signal['instrument']}`\n"
        f"*Type:* `{signal['signal']}`\n"
        f"*Entry:* `{signal['entry']}`\n"
        f"*TP:* `{signal['tp']}`\n"
        f"*SL:* `{signal['sl']}`\n"
        f"*Signal ID:* `{signal['signalid']}`\n\n"
        f"✅ Reply with `/approve {signal['signalid']}` to confirm"
    )