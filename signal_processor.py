import logging


from utils import log_to_google_sheets, update_existing_signal
from dropbox_writer import upload_signal_to_dropbox_grouped
import uuid

from signal_db import store_signalid, get_signalid, add_entry
import json

logger = logging.getLogger("signalworker.processor")


from signal_db import store_signalid, get_signalid

async def process_sanitized_signal(
    sanitized: dict,
    source: str = None,
    link: str = None,
    timestamp: str = None,
    telegram_message_id: int = None,
    reply_to_msg_id: int = None,
):
    signals = sanitized.get("signals", [])
    if not signals:
        logger.warning("⚠️ No signals found in sanitized payload.")
        return

    # Determine main signalid
    first_signal = signals[0] if signals else {}
    if first_signal.get("manipulation"):
        # Manipulation → reuse parent's UUID
        main_signalid = None
        if reply_to_msg_id:
            main_signalid = get_signalid(reply_to_msg_id)
        if not main_signalid:
            main_signalid = str(uuid.uuid4())
    else:
        # Normal trade signal
        main_signalid = get_signalid(telegram_message_id)
        if not main_signalid:
            main_signalid = store_signalid(telegram_message_id)

    for signal in signals:
        # Assign consistent signalid
        signal["signalid"] = main_signalid

        # Metadata
        if source:
            signal["source"] = source
        if link:
            signal["link"] = link
        if timestamp:
            signal["time"] = timestamp
        if telegram_message_id:
            signal["telegram_message_id"] = telegram_message_id

        # Record in DB (entry row)
        entry_type = "manipulation" if signal.get("manipulation") else "entry"
        add_entry(main_signalid, telegram_message_id, entry_type, json.dumps(signal))

        # Forward downstream
        upload_signal_to_dropbox_grouped(signal)
        log_to_google_sheets(signal)