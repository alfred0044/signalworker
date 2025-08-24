import os
import pathlib
from dotenv import load_dotenv

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "test")
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")

SOURCE_CHANNEL_IDS = [
    int(cid.strip()) for cid in os.getenv("SOURCE_CHANNEL_IDS", "").split(",") if cid.strip()
]

if ENVIRONMENT == "prod":
    SESSION_DIRECTORY = "/data/storage"
    SESSION_NAME = f"signal_splitter_{ENVIRONMENT}.session"
    SESSION_PATH = f"{SESSION_DIRECTORY}/{SESSION_NAME}"
else:
    SESSION_DIRECTORY = pathlib.Path(__file__).parent / "data"
    SESSION_NAME = f"signal_splitter_{ENVIRONMENT}.session"
    SESSION_PATH = str(SESSION_DIRECTORY / SESSION_NAME)

os.makedirs(os.path.dirname(SESSION_PATH), exist_ok=True)
