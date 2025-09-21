# dropbox_writer.py
import traceback

import dropbox
import os
import json
from datetime import datetime
import logging
logger = logging.getLogger("signalworker.filewriter")
# Environment variables
DROPBOX_REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN")
DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY")
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET")
LOCAL_SIGNAL_FOLDER =  "local_signals"
def upload_signal_to_dropbox(signal_data: dict, filename_prefix="signal"):
    try:
        # Work directly with signal_data
       # signal_data['TIME'] = datetime.utcnow().isoformat() + "Z"
       # signal_data['SOURCE'] = "test"

        # Convert dict to JSON string
        content = json.dumps(signal_data, indent=2)

        dbx = dropbox.Dropbox(
            oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
            app_key=DROPBOX_APP_KEY,
            app_secret=DROPBOX_APP_SECRET
        )

        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        filename = f"/{filename_prefix}_{timestamp}.json"

        dbx.files_upload(
            content.encode('utf-8'),
            filename,
            mode=dropbox.files.WriteMode.overwrite
        )

        print(f"✅ Uploaded to Dropbox: {filename}")

    except Exception as e:
        print(f"❌ Error: {e}",traceback.format_exc())


def upload_signal_to_dropbox_grouped(signal: dict, filename_prefix="signal"):
    """
    Group all signals & manipulations by shared signalid into a single JSON file.
    File name is based on the signalid.
    """
    signalid = signal["signalid"]

    # Dropbox client initialization
    dbx = dropbox.Dropbox(
        oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
        app_key=DROPBOX_APP_KEY,
        app_secret=DROPBOX_APP_SECRET
    )

    # Base filename without manipulation prefix
    base_filename = f"/{filename_prefix}_{signalid}.json"

    # Try to download existing data (if any)
    existing_data = {"signals": []}
    try:
        _, res = dbx.files_download(base_filename)
        existing_data = json.loads(res.content.decode("utf-8"))
    except dropbox.exceptions.ApiError:
        # File likely doesn't exist, start fresh
        existing_data = {"signals": []}

    # Append new signal/manipulation to the existing list
    existing_data["signals"].append(signal)

    # Helper to create a unique key per signal (for deduplication if needed)
    def signal_key(sig):
        return (
            sig.get("telegram_message_id"),
            sig.get("manipulation"),
            sig.get("instrument"),
            sig.get("entry"),
            sig.get("signal")
        )

    dedup_map = {signal_key(s): s for s in existing_data.get("signals", [])}
    dedup_signals = list(dedup_map.values())

    # Count manipulations for this signalid if signal has manipulation
    manipulation_value = signal.get("manipulation")
    if manipulation_value:
        manip_count = sum(
            1 for s in dedup_signals
            if s.get("signalid") == signalid and s.get("manipulation") is not None
        )
        # If the current signal's key not previously present, increment manip_count
        if signal_key(signal) not in dedup_map:
            manip_count += 1
        filename = f"/manipulation{manip_count}{filename_prefix}_{signalid}.json"
    else:
        # No manipulation: keep original filename
        filename = base_filename

    # Upload updated JSON with deduplicated signals
    dbx.files_upload(
        json.dumps({"signals": dedup_signals}, indent=2).encode("utf-8"),
        filename,
        mode=dropbox.files.WriteMode("overwrite"),
    )

    print(f"✅ Uploaded to Dropbox: {filename}")


def save_signal_batch_locally(signal: dict, filename_prefix="signal"):
    signalid = signal["signalid"]
    # Gather the filename without manipulation count yet
    filename_without_count = f"{filename_prefix}_{signalid}.json"
    filepath = os.path.join(LOCAL_SIGNAL_FOLDER, filename_without_count)

    # Load existing data as usual
    existing_data = {"signals": []}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception as e:
            logger.warning(f"Could not read existing file {filepath}, starting fresh. Error: {e}")

    # Helper to create a unique key per signal
    def signal_key(sig):
        return (
            sig.get("telegram_message_id"),
            sig.get("manipulation"),
            sig.get("instrument"),
            sig.get("entry"),
            sig.get("signal")
        )

    # Map and deduplicate
    existing_map = {signal_key(s): s for s in existing_data.get("signals", [])}
    existing_map[signal_key(signal)] = signal
    dedup_signals = list(existing_map.values())

    # Count manipulations (for this signalid)
    manipulation_value = signal.get("manipulation")
    # Keep original name if no manipulation
    if manipulation_value:
        # Count manipulations as before
        manip_count = sum(
            1 for s in dedup_signals
            if s.get("signalid") == signalid and s.get("manipulation") is not None
        )
        if (
                manipulation_value is not None
                and signal_key(signal) not in [signal_key(s) for s in existing_data.get("signals", [])]
        ):
            manip_count += 1
        filename = f"manipulation{manip_count}{filename_prefix}_{signalid}.json"
    else:
        filename = f"{filename_prefix}_{signalid}.json"

    filepath = os.path.join(LOCAL_SIGNAL_FOLDER, filename)

    # Save updated JSON back to file
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"signals": dedup_signals}, f, indent=2)
        logger.info(f"✅ Saved deduplicated batch locally: {filepath}")
    except Exception as e:
        logger.error(f"Failed saving batch locally at {filepath}: {e}")
