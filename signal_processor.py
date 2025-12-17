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

logging.basicConfig(level=logging.INFO)
USE_LOCAL_STORAGE = os.getenv("USE_LOCAL_STORAGE", "False").lower() in ("true", "1", "yes")
LOCAL_SIGNAL_FOLDER = os.getenv("LOCAL_SIGNAL_FOLDER")
LOCAL_HISTORICAL_FOLDER = os.getenv("LOCAL_HISTORICAL_FOLDER", "historical_signals_storage")
sent_signal_keys = set()
sent_signal_lock = threading.Lock()
app = Flask(__name__)
logger = logging.getLogger("signalworker.processor")

# In-memory lifecycle signal state tracking
signal_states = {}
lock = threading.Lock()
signal_batches = {}
manipulation_counters = {}  # memory map signalid -> manipulation count

CHANNEL_CONFIG = {
    "🌸NOVA - GOLD PLATINUM 🎀": {
        "entry_offset": 50,    # 50 Points (5 Pips)
        "risk_overwrite": 0.02 # 2% Risiko pro Trade
    },
    "VasilyTrader Vip Signals": {
        "entry_offset": 0,   # -20 Points
        "risk_overwrite": 0.10 # 10% Risiko pro Trade
    },
    "signals_Test": {
        "entry_offset": 0,  # -20 Points
        "risk_overwrite": 0.0  # 10% Risiko pro Trade
    }
}

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
        # Assuming save_signal_batch_locally is defined elsewhere or not critical for this fix
        # save_signal_batch_locally(signal)
        pass
    else:
        # Assuming upload_signal_to_dropbox_grouped is defined elsewhere or not critical for this fix
        # upload_signal_to_dropbox_grouped(signal, manipulation_count=manipulation_count)
        pass

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
        override_signalid: str = None,
        is_historical: bool = False
):
    storage_folder = LOCAL_HISTORICAL_FOLDER if is_historical else LOCAL_SIGNAL_FOLDER
    signals = sanitized.get("signals", [])
    if not signals:
        logger.warning("⚠️ No signals found.")
        return

    first_signal = signals[0] if signals else {}
    # Check if 'manipulation' field is present and not None
    is_manipulation = first_signal.get("manipulation") is not None
    main_signalid = None

    # 1. Determine main_signalid
    if is_manipulation and reply_to_msg_id:
        # Manipulation: Fetch ID of the original signal using the reply ID
        main_signalid = get_signalid(reply_to_msg_id)
        if not main_signalid:
            logger.warning(
                f"Manipulation received but original signal ID not found for reply_to_msg_id: {reply_to_msg_id}")
            return
    elif telegram_message_id:
        # New Signal: Get existing ID or create a new one
        main_signalid = get_signalid(telegram_message_id) or store_signalid(telegram_message_id)

    if not main_signalid:
        logger.warning("Could not determine main_signalid.")
        return

    # Get the current in-memory batch (the state of the existing signal entries)
    current_batch = signal_batches.setdefault(main_signalid, [])

    # --- Start Data Merging Logic for Manipulation ---

    if is_manipulation and current_batch:
        logger.info(f"Applying manipulation data for signal ID: {main_signalid}")
        manipulation_data = first_signal  # The sanitized object containing new 'sl' and/or 'tp'

        # NEUER EINTRAG FÜR MANIPULATION:
        # Manipulationen werden nun als eigenständiger Eintrag mit dem Zeitstempel der Manipulation hinzugefügt,
        # anstatt die bestehenden Einträge zu überschreiben.

        # Kontextfelder für den neuen Manipulationseintrag füllen
        new_manipulation_entry = {
            "signalid": main_signalid,
            "manipulation": manipulation_data.get("manipulation"),
            "instrument": manipulation_data.get("instrument"),
            "link": make_telegram_link(link) if link else None,
            "source": source,
            "time": timestamp,
            "telegram_message_id": telegram_message_id
            # Optional: Übernehmen von SL/TP-Updates, falls vorhanden,
            # obwohl das "manipulation"-Feld in der Regel die Aktion beschreibt.
        }

        # Hinzufügen des Manipulationseintrags zur Batch
        current_batch.append(new_manipulation_entry)

        # Die ursprüngliche Logik zur Aktualisierung der SL/TP-Werte in der Batch
        # ist für die meisten Manipulationsarten NICHT gewünscht, da sie historische
        # Daten überschreibt. Wir entfernen die Logik, die in-place die SL/TPs aller
        # vorherigen Einträge ändert, um eine saubere Historie zu gewährleisten.

        dedup_signals = current_batch

    else:
        # New Signal Case (No Manipulation)

        # Deduplicate incoming signals before filling context fields
        unique = {}
        for signal in signals:
            k = signal_key(signal)
            unique[k] = signal

        # Fill context fields
        for k, sig in unique.items():  # Wir iterieren über k, sig um sicherzugehen
            # 1. Standard-Kontext setzen
            sig["signalid"] = main_signalid
            if source: sig["source"] = source
            if link: sig["link"] = make_telegram_link(link)
            if timestamp: sig["time"] = timestamp
            if telegram_message_id: sig["telegram_message_id"] = telegram_message_id

            # 2. Kanal-spezifische Anpassungen (DIREKT im Objekt)
            print(source)
            if source in CHANNEL_CONFIG:
                config = CHANNEL_CONFIG[source]

                # A. Risk Overwrite
                if "risk_overwrite" in config:
                    sig["risk"] = config["risk_overwrite"]
                    logger.info(f"SET RISK: {sig['risk']} for {source}")

                # B. Entry Offset
                offset_points = config.get("entry_offset", 0)
                if offset_points != 0 and sig.get("entry") is not None:
                    direction = sig.get("signal", "").upper()
                    point_val = 0.01  # Standard für Gold

                    try:
                        old_entry = float(sig["entry"])
                        # Wichtig: offset_points * point_val
                        mod = offset_points * point_val

                        if "BUY" in direction:
                            sig["entry"] = round(old_entry + mod, 2)
                        elif "SELL" in direction:
                            sig["entry"] = round(old_entry - mod, 2)

                        logger.info(f"OFFSET APPLIED: {old_entry} -> {sig['entry']} ({direction})")
                    except Exception as e:
                        logger.error(f"Offset error: {e}")

            # 3. Erst JETZT in die Datenbank und den Batch-Speicher schreiben
            if "manipulation" not in sig:
                sig["manipulation"] = None

            entry_type = "manipulation" if sig.get("manipulation") else "entry"

            # WICHTIG: Hier muss das MODIFIZIERTE sig übergeben werden!
            add_entry(main_signalid, telegram_message_id, entry_type, json.dumps(sig))

            # 4. Update global in-memory batch mit den modifizierten Objekten
        current_batch.extend(unique.values())

        # Deduplicate the full batch based on the original signal_key logic
        dedup_signals = list({signal_key(s): s for s in current_batch}.values())
        signal_batches[main_signalid] = dedup_signals

    # 3. Store full batch (new or updated state)

    # NEUER SCHRITT: Chronologische Sortierung der Einträge
    if dedup_signals:
        try:
            # Das 'time'-Feld ist ein ISO-8601-String. Lexikographische Sortierung ist chronologisch korrekt.
            # Fallback auf einen sehr alten Timestamp, falls 'time' fehlt, um diesen Eintrag an den Anfang zu setzen.
            dedup_signals.sort(key=lambda s: s.get("time", "1970-01-01T00:00:00Z"), reverse=False)
            logger.info(f"Signal batch for {main_signalid} successfully sorted chronologically.")
        except Exception as e:
            logger.error(f"Failed to sort signals for {main_signalid}: {e}")
            # Fährt fort mit dem Speichern, auch wenn die Sortierung fehlschlägt.

    store_signal_batch(
        dedup_signals,
        main_signalid,
        USE_LOCAL_STORAGE,
        LOCAL_SIGNAL_FOLDER=storage_folder,
    )

    # 4. FIX: Move logging before return statement
    logger.info(f"Signal batch for {main_signalid} written with {len(dedup_signals)} entries.")
    return main_signalid


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