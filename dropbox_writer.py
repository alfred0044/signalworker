# dropbox_writer.py
import dropbox
import os
import json
from datetime import datetime

DROPBOX_ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN")

def upload_signal_to_dropbox(signal_data: dict, filename_prefix="signal"):
    dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    filename = f"/{filename_prefix}_{timestamp}.json"
    content = signal_data.__str__()

    dbx.files_upload(
        content.encode(),
        filename,
        mode=dropbox.files.WriteMode.overwrite
    )
    print(f"✅ Uploaded to Dropbox: {filename}")
