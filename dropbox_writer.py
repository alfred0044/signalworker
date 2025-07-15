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
