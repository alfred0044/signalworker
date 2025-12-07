import asyncio
from sanitizer import sanitize_signal
from signal_processor import process_sanitized_signal
from datetime import datetime, timezone
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import PeerChannel
from dotenv import load_dotenv
import os
import sys
import aiofiles
import json
load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_STRING = os.getenv("TELEGRAM_STRING_SESSION")


SAVE_DIR = "saved_signals"

async def store_sanitized_json(data: dict, source: str, telegram_message_id: int):
    """
    Save sanitized JSON data to a file for audit or debugging.
    Creates 'saved_signals' directory if it doesn't exist.
    """
    os.makedirs(SAVE_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_source = "".join(c if c.isalnum() else "_" for c in source or "unknown")
    filename = f"{timestamp}_{safe_source}_{telegram_message_id}.json"
    path = os.path.join(SAVE_DIR, filename)
    print ("saved")
    try:
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
        return path
    except Exception as e:
        print(f"⚠️ Failed to save sanitized JSON: {e}")
        return None
def register_handlers(client, source_channels):
    @client.on(events.NewMessage(1==1))
    async def handler(event):
        text = event.raw_text.strip()
        print(text)
        if not text:
            return

        sanitized = await sanitize_signal(
            signal_text=text,
            is_reply=event.message.is_reply
        )

        await process_sanitized_signal(
            sanitized,
            source=event.chat.title,
            link=f"https://t.me/c/{abs(event.chat_id)}/{event.id}",
            timestamp=str(event.message.date),
            telegram_message_id=event.id,
            reply_to_msg_id=event.message.reply_to_msg_id  # NEW
        )

def to_peer_channel(channel_id):
    if isinstance(channel_id, str) and channel_id.startswith("-100"):
        channel_id = int(channel_id[4:])  # Remove the '-100' prefix
    if isinstance(channel_id, int):
        return PeerChannel(channel_id=channel_id)
    return channel_id


def parse_args():
    if len(sys.argv) < 2:
        print("Usage: python main.py <channel_id> [source_channel_ids_comma_separated] [start_date] [end_date]")
        sys.exit(1)

    channel_id = sys.argv[1]

    source_channel_ids = []
    start_date = None
    end_date = None

    # Attempt to parse source_channel_ids if provided
    if len(sys.argv) >= 3:
        arg = sys.argv[2]
        if "," in arg:  # heuristic: if comma exists, parse IDs
            try:
                source_channel_ids = list(map(int, arg.split(',')))
            except ValueError:
                print(f"Invalid source_channel_ids: {arg}")
                sys.exit(1)
        else:
            # If no comma, might be start_date instead, so treat arg 2 as date
            try:
                start_date = datetime.strptime(arg, "%Y-%m-%d")
                # Try parsing end_date if it exists
                if len(sys.argv) >= 4:
                    end_date = datetime.strptime(sys.argv[3], "%Y-%m-%d")
            except ValueError:
                print(f"Invalid date format: {arg}")
                sys.exit(1)

    # If 3rd argument was source_channel_ids, parse dates from later args
    if source_channel_ids and len(sys.argv) >= 4:
        try:
            start_date = datetime.strptime(sys.argv[3], "%Y-%m-%d")
            if len(sys.argv) >= 5:
                end_date = datetime.strptime(sys.argv[4], "%Y-%m-%d")
        except ValueError:
            print(f"Invalid date format in arguments.")
            sys.exit(1)

    return channel_id, source_channel_ids, start_date, end_date


def get_client():
    if not SESSION_STRING:
        raise RuntimeError("TELEGRAM_STRING_SESSION missing!")
    return TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


def make_aware(dt):
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def fetch_channel_history(client, channel_id, limit=None, min_date=None, max_date=None):
    min_date = make_aware(min_date)
    max_date = make_aware(max_date)

    messages = []
    peer = to_peer_channel(channel_id)
    async for message in client.iter_messages(peer, limit=limit, reverse=False):
        # Skip messages out of the max_date range
        if max_date and message.date > max_date:
            continue
        # Break if message is before min_date since messages descend by date
        if min_date and message.date < min_date:
            break
        messages.append(message)
    return messages




import asyncio
from sanitizer import sanitize_signal
from signal_processor import process_sanitized_signal
from datetime import datetime, timezone
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import PeerChannel
from dotenv import load_dotenv
import os
import sys

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_STRING = os.getenv("TELEGRAM_STRING_SESSION")

def register_handlers(client, source_channels):
    @client.on(events.NewMessage(chats=source_channels))
    async def handler(event):
        text = event.raw_text.strip()
        if not text:
            return

        sanitized = await sanitize_signal(
            signal_text=text,
            is_reply=event.message.is_reply
        )
        await store_sanitized_json(
            sanitized,
            source=event.chat.title,
            telegram_message_id=event.id,
        )

        trade_signals, manipulations = split_signals_and_manipulations(sanitized)

        if trade_signals:
            await process_sanitized_signal(
                {"signals": trade_signals},
                source=event.chat.title,
                link=f"https://t.me/c/{abs(event.chat_id)}/{event.id}",
                timestamp=str(event.message.date),
                telegram_message_id=event.id,
                reply_to_msg_id=event.message.reply_to_msg_id,
            )



        if manipulations:
            await process_sanitized_signal(
                {"signals": manipulations},
                source=event.chat.title,
                link=f"https://t.me/c/{abs(event.chat_id)}/{event.id}",
                timestamp=str(event.message.date),
                telegram_message_id=event.id,
                reply_to_msg_id=event.message.reply_to_msg_id,
            )
def split_signals_and_manipulations(sanitized):
    trade_signals = []
    manipulations = []
    for sig in sanitized.get("signals", []):
        if sig.get("manipulation"):
            manipulations.append(sig)
        else:
            trade_signals.append(sig)
    return trade_signals, manipulations

def to_peer_channel(channel_id):
    if isinstance(channel_id, str) and channel_id.startswith("-100"):
        channel_id = int(channel_id[4:])  # Remove the '-100' prefix
    if isinstance(channel_id, int):
        return PeerChannel(channel_id=channel_id)
    return channel_id

def parse_args():
    if len(sys.argv) < 2:
        print("Usage: python main.py <channel_id> [source_channel_ids_comma_separated] [start_date] [end_date]")
        sys.exit(1)

    channel_id = sys.argv[1]

    source_channel_ids = []
    start_date = None
    end_date = None

    # Attempt to parse source_channel_ids if provided
    if len(sys.argv) >= 3:
        arg = sys.argv[2]
        if "," in arg:  # heuristic: if comma exists, parse IDs
            try:
                source_channel_ids = list(map(int, arg.split(',')))
            except ValueError:
                print(f"Invalid source_channel_ids: {arg}")
                sys.exit(1)
        else:
            # If no comma, might be start_date instead, so treat arg 2 as date
            try:
                start_date = datetime.strptime(arg, "%Y-%m-%d")
                # Try parsing end_date if it exists
                if len(sys.argv) >= 4:
                    end_date = datetime.strptime(sys.argv[3], "%Y-%m-%d")
            except ValueError:
                print(f"Invalid date format: {arg}")
                sys.exit(1)

    # If 3rd argument was source_channel_ids, parse dates from later args
    if source_channel_ids and len(sys.argv) >= 4:
        try:
            start_date = datetime.strptime(sys.argv[3], "%Y-%m-%d")
            if len(sys.argv) >= 5:
                end_date = datetime.strptime(sys.argv[4], "%Y-%m-%d")
        except ValueError:
            print(f"Invalid date format in arguments.")
            sys.exit(1)

    return channel_id, source_channel_ids, start_date, end_date


def get_client():
    if not SESSION_STRING:
        raise RuntimeError("TELEGRAM_STRING_SESSION missing!")
    return TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


def make_aware(dt):
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def fetch_channel_history(client, channel_id, limit=None, min_date=None, max_date=None):
    min_date = make_aware(min_date)
    max_date = make_aware(max_date)

    messages = []
    peer = to_peer_channel(channel_id)
    async for message in client.iter_messages(peer, limit=limit, reverse=False):
        if not getattr(message, "raw_text", None):
            continue  # skip non-text
        # Skip messages out of the max_date range
        if max_date and message.date > max_date:
            continue
        # Break if message is before min_date since messages descend by date
        if min_date and message.date < min_date:
            break
        messages.append(message)
    return messages




async def replay_historical_messages(client, messages):
    """
    Replay historical messages by simulating NewMessage events,
    so the live handler processes them one-by-one individually.
    """
    # Access the registered handler function (assumes only one handler)
    handler = client._event_builders[0][1]

    for message in messages:
        raw_text = getattr(message, 'raw_text', None)
        msg_text = raw_text or getattr(message, 'message', '') or ''
        if not msg_text:
            continue

        # Simulate an event with required attributes
        class DummyEvent:
            def __init__(self, msg):
                self.raw_text = msg_text
                self.message = msg
                self.chat = getattr(msg, 'chat', None)
                self.chat_id = getattr(msg, 'chat_id', None)
                self.id = getattr(msg, 'id', None)
                self.is_reply = getattr(msg, 'is_reply', False)

        dummy_event = DummyEvent(message)

        # Call the handler with the dummy event
        await handler(dummy_event)


async def main(channel_id, min_date=None, max_date=None):
    client = get_client()

    await client.start()

    register_handlers(client, [to_peer_channel(channel_id)])
    messages = await fetch_channel_history(client, channel_id, min_date=min_date, max_date=max_date)
    print(f"Fetched {len(messages)} messages from {channel_id}")

    await replay_historical_messages(client, messages)

    print("Replayed historical messages processed.")
    await client.run_until_disconnected()


if __name__ == "__main__":
    channel, ids, start_date, end_date = parse_args()
    print(f"Channel: {channel}")
    print(f"Source channel IDs: {ids}")
    print(f"Start date: {start_date}")
    print(f"End date: {end_date}")

    if len(sys.argv) < 3:
        print("Usage: python main.py <channel_id> <source_channel_ids_comma_separated> [start_date] [end_date]")
        print("Date format: YYYY-MM-DD")
        sys.exit(1)

    asyncio.run(main(channel, start_date, end_date))



