import json
from datetime import datetime


def split_signals(text: str) -> list:
    blocks = text.strip().split("* Instrument:")
    return [f"* Instrument:{block.strip()}" for block in blocks if block.strip()]

def log_to_google_sheets(signal_text: str):
    print("📄 Logging to sheet:\n", signal_text)


def log_skipped_signal(reason, signal, logfile="skipped_signals.log"):
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": "WARNING",
        "reason": reason,
        "signal": signal
    }
    with open(logfile, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
import logging
from dropbox_writer import upload_signal_to_dropbox

logger = logging.getLogger("signalworker.utils")

def update_existing_signal(signal: dict, action: str, value=None):
    """
    Create a manipulation JSON file with the same signal_id as the original trade.
    EA will consume this and update the correct trade.
    """
    manipulation_payload = {
        "signal_id": signal.get("signal_id"),  # <-- must exist already
        "instrument": signal.get("instrument"),
        "action": action,
    }

    if value is not None:
        manipulation_payload["value"] = value

    logger.info(f"📤 Uploading manipulation: {manipulation_payload}")

    try:
        upload_signal_to_dropbox([manipulation_payload])
    except Exception as e:
        logger.error(f"❌ Failed to upload manipulation to Dropbox: {e}", exc_info=True)
