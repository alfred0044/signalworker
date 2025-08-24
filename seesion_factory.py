from telethon import TelegramClient
import os
import base64
from dotenv import load_dotenv
load_dotenv()


api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")
session_name = "signal_splitter_prod"
client = TelegramClient(session_name, api_id, api_hash)


async def main():
    await client.start()
    print("✅ Session created and authorized!")

    # Encode to base64
    with open(f"{session_name}.session", "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    # Save to .b64 file
    with open(f"{session_name}.session.b64", "w") as out:
        out.write(b64)

    print(f"📦 Saved: {session_name}.session.b64 (upload this to Railway)")

client.loop.run_until_complete(main())
