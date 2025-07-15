# dropbox_writer.py
import dropbox
import os
import json
from datetime import datetime

#DROPBOX_ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN")
DROPBOX_REFRESH_TOKEN = os.getenv("DROPBOX_REFRESH_TOKEN")
DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY")
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET")

def upload_signal_to_dropbox(signal_data: dict, filename_prefix="signal"):
    dbx = dropbox.Dropbox(
        #oauth2_access_token=DROPBOX_ACCESS_TOKEN,
        oauth2_refresh_token=DROPBOX_REFRESH_TOKEN,
        app_key=DROPBOX_APP_KEY,
        app_secret=DROPBOX_APP_SECRET
    )
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    filename = f"/{filename_prefix}_{timestamp}.txt"
    content = signal_data.__str__()

    dbx.files_upload(
        content.encode(),
        filename,
        mode=dropbox.files.WriteMode.overwrite
    )
    print(f"✅ Uploaded to Dropbox: {filename}")
