import time
import threading
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from utils import log_to_google_sheets, update_existing_signal
from dropbox_writer import upload_signal_to_dropbox_grouped,save_signal_batch_locally
import uuid
from signal_db import store_signalid, get_signalid, add_entry
import json
import os
USE_LOCAL_STORAGE = bool(os.getenv("USE_LOCAL_STORAGE"))
sent_signal_keys = set()
sent_signal_lock = threading.Lock()
app = Flask(__name__)
logger = logging.getLogger("signalworker.processor")

# In-memory lifecycle signal state tracking
signal_states = {}
lock = threading.Lock()


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
def send_signal_with_tracking(signal):
    signalid = signal["signalid"]
    with lock:
        signal_states[signalid] = {
            "sent_time": time.time(),
            "status": "pending",
            "signal": signal,
            "last_update": time.time(),
            "history": [("pending", time.time())]
        }
    # Upload to Dropbox (your existing call)
    print(USE_LOCAL_STORAGE)
    if USE_LOCAL_STORAGE:
        save_signal_batch_locally(signal)
    else:
        upload_signal_to_dropbox_grouped(signal)

    # You can also log to Google Sheets or elsewhere
    log_to_google_sheets(signal)
    logger.info(f"Signal {signalid} sent and tracking started.")

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
        logger.warning("⚠️ No signals found in sanitized payload.")
        return

    first_signal = signals[0] if signals else {}
    if first_signal.get("manipulation"):
        main_signalid = None
        if reply_to_msg_id:
            main_signalid = get_signalid(reply_to_msg_id)
        if not main_signalid:
            main_signalid = str(uuid.uuid4())
    else:
        main_signalid = get_signalid(telegram_message_id)
        if not main_signalid:
            main_signalid = store_signalid(telegram_message_id)

    # Deduplicate signals here by a unique key
    unique_signals_dict = {}
    for signal in signals:
        # Build unique key per signal: customize as needed
        key = (
            signal.get("telegram_message_id"),
            signal.get("manipulation"),
            signal.get("instrument"),
            signal.get("entry"),
            signal.get("signal")
        )
        unique_signals_dict[key] = signal  # overwrites duplicates, keeps last

    unique_signals = list(unique_signals_dict.values())

    for signal in unique_signals:
        signal["signalid"] = main_signalid

        if source:
            signal["source"] = source
        if link:
            signal["link"] = make_telegram_link(link)
        if timestamp:
            signal["time"] = timestamp
        if telegram_message_id:
            signal["telegram_message_id"] = telegram_message_id

        entry_type = "manipulation" if signal.get("manipulation") else "entry"
        add_entry(main_signalid, telegram_message_id, entry_type, json.dumps(signal))

        # Send with lifecycle tracking
        send_signal_with_tracking(signal)

# Periodic cleanup thread to invalidate stale signals
def cleanup_stale_signals(expiration_seconds=3600):
    while True:
        now = time.time()
        with lock:
            stale_signals = [sid for sid, data in signal_states.items() if data["status"] == "pending" and (now - data["sent_time"]) > expiration_seconds]
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