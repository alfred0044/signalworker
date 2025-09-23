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




def store_signal_batch(signals, signalid, USE_LOCAL_STORAGE, LOCAL_SIGNAL_FOLDER=None):
    """
    Store a signal batch locally or on Dropbox under 'signal_<signalid>.json',
    governed by USE_LOCAL_STORAGE.
    """
    import json, os

    filename = f"signal_{signalid}.json"
    if USE_LOCAL_STORAGE:
        if not LOCAL_SIGNAL_FOLDER:
            raise ValueError("LOCAL_SIGNAL_FOLDER must be set if USE_LOCAL_STORAGE is True.")
        filepath = os.path.join(LOCAL_SIGNAL_FOLDER, filename)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump({"signals": signals}, f, indent=2)
            logger.info(f"✅ Saved locally: {filepath}")
        except Exception as e:
            logger.error(f"Local save failed: {e}")
    else:
        dbx = dropbox.Dropbox(
            oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
            app_key=DROPBOX_APP_KEY,
            app_secret=DROPBOX_APP_SECRET
        )
        if not dbx:
            raise ValueError("dbx Dropbox client must be provided if USE_LOCAL_STORAGE is False.")
        file_path = f"/{filename}"
        try:
            dbx.files_upload(
                json.dumps({"signals": signals}, indent=2).encode("utf-8"),
                file_path,
                mode=dropbox.files.WriteMode("overwrite"),
            )
            logger.info(f"✅ Uploaded to Dropbox: {file_path}")
        except Exception as e:
            logger.error(f"Dropbox upload failed: {e}")


