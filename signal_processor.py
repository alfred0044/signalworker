import logging
from datetime import datetime
import json
import traceback
import uuid
import re
from typing import Dict, Any, Optional

from dropbox_writer import upload_signal_to_dropbox
from utils import split_signals, log_to_google_sheets
from json_extractor import JsonExtractor

logger = logging.getLogger("signalworker.process")

# In-memory store of signals keyed by telegram message ID
active_signals_by_message_id: Dict[int, Dict] = {}

def create_signal_json(
    signal_data: Dict[str, Any],
    manipulation: Optional[str] = None,
    new_sl: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Creates a properly structured JSON signal dict including manipulation commands.

    Args:
        signal_data: Dict containing the core signal fields (instrument, entry, sl, tp, etc.)
        manipulation: Optional manipulation command string
        new_sl: New stop loss price if manipulation is "move_sl"

    Returns:
        dict: JSON-compatible dictionary for the full signal including optional manipulations.
    """
    signal_json = {
        "signalid": signal_data.get("signalid", str(uuid.uuid4())),
        "source": signal_data.get("source", "Unknown"),
        "time": signal_data.get("time", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")),
        "instrument": signal_data.get("instrument"),
        "signal": signal_data.get("signal"),
        "entry": signal_data.get("entry"),
        "tp": signal_data.get("tp"),
        "sl": signal_data.get("sl"),
        "telegram_message_id": signal_data.get("telegram_message_id"),
        "comment": signal_data.get("comment", ""),
        "manipulation": manipulation or signal_data.get("manipulation"),
        "new_sl": new_sl or signal_data.get("new_sl"),
    }
    # Clean None values out from JSON
    cleaned = {k: v for k, v in signal_json.items() if v is not None}
    return {"signals": [cleaned]}

async def process_sanitized_signal(
        text: str,
        source: str = "Unknown",
        link: Optional[str] = None,
        timestamp: Optional[str] = None,
        telegram_message_id: Optional[int] = None,
) -> bool:
    """
    Processes sanitized signal text into JSON, stores in-memory state and uploads to Dropbox.
    """
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

    signalid = str(uuid.uuid4())
    dt = timestamp or datetime.utcnow()
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "").replace("+00:00", ""))
        except Exception as e:
            logger.warning("Could not parse timestamp '%s': %s. Using current UTC.", timestamp, e)
            dt = datetime.utcnow()

    confirmed = True
    for item in signal_json["signals"]:
        # Add enriching fields
        item["source"] = source
        item["signalid"] = signalid
        item["time"] = dt.strftime("%Y-%m-%d %H:%M:%S")
        if link:
            item["link"] = link
        if telegram_message_id is not None:
            item["telegram_message_id"] = telegram_message_id
            # Store in-memory for quick lookup by Telegram message ID
            active_signals_by_message_id[telegram_message_id] = item

        # Manipulation detection: if text matches "+XXpips", automatically mark as "cancel_pending"
        manipulation = item.get("manipulation")
        if not manipulation and isinstance(text, str) and re.search(r"\+\d+\s*pips", text.lower()):
            manipulation = "cancel_pending"

        full_signal_json = create_signal_json(item, manipulation=manipulation, new_sl=item.get("new_sl"))

        try:
            upload_signal_to_dropbox(full_signal_json)
            logger.info("✅ Signal processed and uploaded with ID: %s", signalid)
        except Exception as e:
            logger.error("Error uploading signal to Dropbox: %s\n%s", e, traceback.format_exc())
            confirmed = False

    return confirmed

def find_signal_by_telegram_message_id(message_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve the signal associated with Telegram message ID.
    """
    return active_signals_by_message_id.get(message_id)

def update_signal_json_and_dropbox(signal: Dict[str, Any]):
    """
    Update signal in-memory and upload updated JSON with manipulation instructions.
    """
    try:
        message_id = signal.get("telegram_message_id")
        if message_id is None:
            logger.warning("Signal missing telegram_message_id: cannot update in-memory store.")
        else:
            active_signals_by_message_id[message_id] = signal

        manipulation = signal.get("manipulation")
        new_sl = signal.get("new_sl")

        full_signal_json = create_signal_json(signal, manipulation=manipulation, new_sl=new_sl)
        upload_signal_to_dropbox(full_signal_json)
        logger.info("Updated signal uploaded to Dropbox for message_id=%s with manipulation=%s", message_id, manipulation)
    except Exception as e:
        logger.error("Failed to update and upload signal: %s", e)

def format_for_confirmation(signal: Dict[str, Any]) -> str:
    fields = ("instrument", "signal", "entry", "tp", "sl", "signalid")
    return (
        f"📥 *New Signal Detected:*\n" +
        "".join([
            f"*{field.capitalize()}:* `{signal.get(field, 'N/A')}`\n"
            for field in fields
        ]) +
        "\n✅ Reply with `/approve {}` to confirm".format(signal.get("signalid", "N/A"))
    )