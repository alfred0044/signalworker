import asyncio
import os
import sys
import traceback
from dotenv import load_dotenv
load_dotenv()
from session import create_session_env, get_client
from handlers import register_handlers
from config import SESSION_PATH, SOURCE_CHANNEL_IDS

async def wait_for_session():
    while not os.path.exists(SESSION_PATH):
        print(f"❌ Session file not found at {SESSION_PATH}. Retrying in 60 seconds...")
        await asyncio.sleep(60)
    print(f"✅ Session file found at {SESSION_PATH}.")

async def main():
    # Optional session creation from CLI argument
    if len(sys.argv) > 1 and sys.argv[1] == "create_session":
        await create_session_env()
        return

    await wait_for_session()

    while True:
        try:
            client = get_client()
            await client.connect()

            if not await client.is_user_authorized():
                print("❌ Telegram client not authorized. Session file may be invalid.")
                await asyncio.sleep(60)
                continue

            register_handlers(client)

            dialogs = await client.get_dialogs()
            for dialog in dialogs:
                if abs(dialog.id) in SOURCE_CHANNEL_IDS:
                    print(dialog.name, dialog.id, "✅")
                else:
                    print(dialog.name, dialog.id, "❌")

            await client.start()
            print("✅ Client started — waiting for messages.")
            await client.run_until_disconnected()

        except Exception:
            print("❌ Fatal error during runtime:")
            print(traceback.format_exc())
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
