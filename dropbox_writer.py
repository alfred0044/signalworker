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


def upload_signal_to_dropbox_grouped(signal: dict, manipulation_count: int = 0, filename_prefix="signal"):
    """
    Uploads the individual signal to Dropbox.
    Appends manipulation count in filename if applicable for uniqueness.
    """
    signalid = signal["signalid"]

    dbx = dropbox.Dropbox(
        oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
        app_key=DROPBOX_APP_KEY,
        app_secret=DROPBOX_APP_SECRET
    )

    if manipulation_count > 0:
        filename = f"/manipulation{manipulation_count}{filename_prefix}_{signalid}.json"
    else:
        filename = f"/{filename_prefix}_{signalid}.json"

    try:
        dbx.files_upload(
            json.dumps({"signals": [signal]}, indent=2).encode("utf-8"),
            filename,
            mode=dropbox.files.WriteMode("overwrite"),
        )
        print(f"✅ Uploaded to Dropbox: {filename}")
    except Exception as e:
        print(f"❌ Failed to upload to Dropbox: {e}")


def save_signal_batch_locally(signal: dict, filename_prefix="signal"):
    signalid = signal["signalid"]
    filename_without_count = f"{filename_prefix}_{signalid}.json"
    filepath = os.path.join(LOCAL_SIGNAL_FOLDER, filename_without_count)
    print("tre");
    existing_data = {"signals": []}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except Exception as e:
            logger.warning(f"Could not read existing file {filepath}, starting fresh. Error: {e}")

    def signal_key(sig):
        return (
            sig.get("telegram_message_id"),
            sig.get("manipulation"),
            sig.get("instrument"),
            sig.get("entry"),
            sig.get("signal")
        )

    # Collect all signals with this signalid (deduplicate by full key)
    signals_all = existing_data.get("signals", [])
    signals_all.append(signal)  # add new one
    # Deduplicate (latest wins)
    sigmap = {signal_key(s): s for s in signals_all}
    dedup_signals = list(sigmap.values())

    # Now, get all manipulations for this signalid, sort by time if needed
    manip_signals = [s for s in dedup_signals if s.get("signalid") == signalid and s.get("manipulation") is not None]
    manipulation_count = len(manip_signals)

    # Compose new filename for manipulation
    manipulation_value = signal.get("manipulation")
    if manipulation_value:
        filename = f"manipulation{manipulation_count}{filename_prefix}_{signalid}.json"
    else:
        filename = f"{filename_prefix}_{signalid}.json"
    filepath = os.path.join(LOCAL_SIGNAL_FOLDER, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({"signals": dedup_signals}, f, indent=2)
        logger.info(f"✅ Saved deduplicated batch locally: {filepath}")
    except Exception as e:
        logger.error(f"Failed saving batch locally at {filepath}: {e}")


