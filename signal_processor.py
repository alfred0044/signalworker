import time
import threading
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from utils import log_to_google_sheets, update_existing_signal
from dropbox_writer import store_signal_batch
import uuid
from signal_db import store_signalid, get_signalid, add_entry
import json
import os

USE_LOCAL_STORAGE = os.getenv("USE_LOCAL_STORAGE", "False").lower() in ("true", "1", "yes")
LOCAL_SIGNAL_FOLDER = os.getenv("LOCAL_SIGNAL_FOLDER")
sent_signal_keys = set()
sent_signal_lock = threading.Lock()
app = Flask(__name__)
logger = logging.getLogger("signalworker.processor")

# In-memory lifecycle signal state tracking
signal_states = {}
lock = threading.Lock()
signal_batches = {}
manipulation_counters = {}  # memory map signalid -> manipulation count


@app.route("/ea-status-update", methods=["POST"])
def ea_status_update():
    data = request.json
    signalid = data.get("signalid")
    new_status = data.get("status")
    if not signalid or not new_status:
        return jsonify({"error": "signalid and status required"}), 400

    # Use your existing signal lifecycle update function here
    update_signal_state(signalid, new_status, data)
    logging.info(f"Signal {signalid} status updated from EA: {new_status}")
    return jsonify({"status": "ok"}), 200


def signal_unique_key(signal: dict) -> tuple:
    # Define uniqueness; example includes manipulation, telegram_message_id, instrument, entry price, etc.
    return (
        signal.get("signalid"),
        signal.get("telegram_message_id"),
        signal.get("manipulation"),
        signal.get("instrument"),
        signal.get("entry"),
        signal.get("signal")
    )

def signal_key(sig):
    return (
        sig.get("telegram_message_id"),
        sig.get("manipulation"),
        sig.get("instrument"),
        sig.get("entry"),
        sig.get("signal")
    )

def send_signal_with_tracking(signal):
    signalid = signal["signalid"]

    # Track signal lifecycle state
    with lock:
        signal_states[signalid] = {
            "sent_time": time.time(),
            "status": "pending",
            "signal": signal,
            "last_update": time.time(),
            "history": [("pending", time.time())]
        }

    manipulation_count = 0
    if signal.get("manipulation"):
        with lock:
            manipulation_counters.setdefault(signalid, 0)
            manipulation_counters[signalid] += 1
            manipulation_count = manipulation_counters[signalid]

    # Upload or save locally
    if USE_LOCAL_STORAGE:
        save_signal_batch_locally(signal)
    else:
        upload_signal_to_dropbox_grouped(signal, manipulation_count=manipulation_count)

    # Additional logging or secondary output
    logger.info(f"Signal {signalid} uploaded with manipulation count {manipulation_count}")


def update_signal_state(signalid, new_status, extra_info=None):
    with lock:
        if signalid in signal_states:
            signal_states[signalid]["status"] = new_status
            signal_states[signalid]["last_update"] = time.time()
            if extra_info:
                signal_states[signalid].update(extra_info)
            signal_states[signalid]["history"].append((new_status, time.time()))
            logger.info(f"Signal {signalid} status updated to {new_status}")
        else:
            logger.warning(f"Signal {signalid} update received but not found in tracking.")


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
        logger.warning("⚠️ No signals found.")
        return

    first_signal = signals[0] if signals else {}
    if first_signal.get("manipulation"):
        main_signalid = get_signalid(reply_to_msg_id) if reply_to_msg_id else str(uuid.uuid4())
    else:
        main_signalid = get_signalid(telegram_message_id) or store_signalid(telegram_message_id)

    # Deduplicate current batch per key
    unique = {}
    for signal in signals:
        k = (
            signal.get("telegram_message_id"),
            signal.get("manipulation"),
            signal.get("instrument"),
            signal.get("entry"),
            signal.get("signal")
        )
        unique[k] = signal

    # Fill context fields and add to entry db
    for sig in unique.values():
        sig["signalid"] = main_signalid
        if source: sig["source"] = source
        if link: sig["link"] = make_telegram_link(link)
        if timestamp: sig["time"] = timestamp
        if telegram_message_id: sig["telegram_message_id"] = telegram_message_id
        entry_type = "manipulation" if sig.get("manipulation") else "entry"
        add_entry(main_signalid, telegram_message_id, entry_type, json.dumps(sig))

    # Update global in-memory batch
    batch = signal_batches.setdefault(main_signalid, [])
    batch.extend(unique.values())
    dedup_signals = list({signal_key(s): s for s in batch}.values())
    signal_batches[main_signalid] = dedup_signals

    # Store full batch under a constant filename (local or Dropbox)
    store_signal_batch(
        dedup_signals,
        main_signalid,
        USE_LOCAL_STORAGE,
        LOCAL_SIGNAL_FOLDER,
    )

    logger.info(f"Signal batch for {main_signalid} written with {len(dedup_signals)} entries.")

# Periodic cleanup thread to invalidate stale signals
def cleanup_stale_signals(expiration_seconds=3600):
    while True:
        now = time.time()
        with lock:
            stale_signals = [sid for sid, data in signal_states.items() if
                             data["status"] == "pending" and (now - data["sent_time"]) > expiration_seconds]
            for sid in stale_signals:
                signal_states[sid]["status"] = "invalidated"
                signal_states[sid]["history"].append(("invalidated", now))
                logger.info(f"Signal {sid} marked as invalidated due to timeout.")
        time.sleep(60)


# You can run the cleanup thread alongside your app
import threading

cleanup_thread = threading.Thread(target=cleanup_stale_signals, daemon=True)
cleanup_thread.start()


def run_flask():
    app.run(host="0.0.0.0", port=5000, threaded=True)


def start_flask():
    thread = threading.Thread(target=run_flask)
    thread.daemon = True
    thread.start()


def make_telegram_link(raw_link):
    # Example input: https://t.me/c/1001548011615/35856
    # Goal: remove '100' prefix in channel id part

    parts = raw_link.split('/')
    # parts example: ['https:', '', 't.me', 'c', '1001548011615', '35856']

    if len(parts) >= 6:
        chat_id = parts[4]
        if chat_id.startswith("100") and len(chat_id) > 3:
            parts[4] = chat_id[3:]  # strip first 3 chars
        return "/".join(parts)
    return raw_link


if __name__ == "__main__":
    # Start Flask server in background
    start_flask()
