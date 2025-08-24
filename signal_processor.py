import logging
from datetime import datetime
import json
import traceback
import uuid
from typing import Dict, Any, Optional
import os
from dropbox_writer import upload_signal_to_dropbox
from utils import split_signals, log_to_google_sheets
from json_extractor import JsonExtractor

TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHAT_ID"))
API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

logger = logging.getLogger("signalworker.process")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
    logger.addHandler(handler)


async def process_sanitized_signal(
        text: str, source: str = "Unknown", link: Optional[str] = None, timestamp: Optional[str] = None
) -> bool:
    try:
        logger.info("Received text for processing: %s", text[:100])
        signal_json = JsonExtractor.extract_valid_json(text)
        logger.debug("Extracted JSON: %s", signal_json)
    except json.JSONDecodeError:
        logger.error("Invalid JSON format in sanitized signal.")
        return False

    if not isinstance(signal_json, dict) or "signals" not in signal_json:
        logger.error("Invalid signal format. Expected top-level 'signals' key. Data: %s", signal_json)
        return False

    signalid = int(uuid.uuid4())
    dt = timestamp or datetime.utcnow()
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "").replace("+00:00", ""))
        except Exception as e:
            logger.warning("Could not parse timestamp '%s': %s. Using current UTC.", timestamp, e)
            dt = datetime.utcnow()

    confirmed = True
    for item in signal_json["signals"]:
        item["source"] = source
        item["signalid"] = signalid
        item["time"] = dt.strftime("%Y-%m-%d %H:%M:%S")
        if link:
            item["link"] = link

        confirmation_message = format_for_confirmation(item)

        # Optionally send Telegram confirmation (uncomment to enable)
        # try:
        #     response = requests.post(f"{API_URL}/sendMessage", json={
        #         "chat_id": TARGET_CHANNEL_ID,
        #         "text": confirmation_message
        #     })
        #     if response.status_code != 200:
        #         logger.error("Failed to send Telegram message: %s | %s", response.status_code, response.content)
        #         confirmed = False
        #     else:
        #         logger.info("Confirmation message sent: %s", confirmation_message)
        # except Exception as e:
        #     logger.error("Exception while sending Telegram message: %s\n%s", e, traceback.format_exc())
        #     confirmed = False

    try:
        upload_signal_to_dropbox(signal_json)
        logger.info("✅ Signal processed and logged to Dropbox. ID: %s", signalid)
    except Exception as e:
        logger.error("Error sending or logging signal: %s\n%s", e, traceback.format_exc())
        return False

    return confirmed


def format_for_confirmation(signal: Dict[str, Any]) -> str:
    fields = ("instrument", "signal", "entry", "tp", "sl", "signalid")
    # Defensive: fallback to 'N/A' if fields are missing
    return (
            f"📥 *New Signal Detected:*\n" +
            "".join([
                f"*{field.capitalize()}:* `{signal.get(field, 'N/A')}`\n"
                for field in fields
            ]) +
            "\n✅ Reply with `/approve {}` to confirm".format(signal.get("signalid", "N/A"))
    )
