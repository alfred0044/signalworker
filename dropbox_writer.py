# dropbox_writer.py
import traceback

import dropbox
import os
import json
from datetime import datetime

# Environment variables
DROPBOX_REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN")
DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY")
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET")

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
    filename = f"/{filename_prefix}_{signalid}.json"

    dbx = dropbox.Dropbox(
        oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
        app_key=DROPBOX_APP_KEY,
        app_secret=DROPBOX_APP_SECRET
    )

    # Try to download existing data (if any)
    existing_data = {"signals": []}
    try:
        _, res = dbx.files_download(filename)
        existing_data = json.loads(res.content.decode("utf-8"))
    except dropbox.exceptions.ApiError:
        # File likely doesn't exist, start fresh
        existing_data = {"signals": []}

    # Append new signal/manipulation to the existing list
    existing_data["signals"].append(signal)

    # Upload updated JSON
    dbx.files_upload(
        json.dumps(existing_data, indent=2).encode("utf-8"),
        filename,
        mode=dropbox.files.WriteMode("overwrite"),  # overwrite the old file
    )

    print(f"✅ Uploaded to Dropbox: {filename}")