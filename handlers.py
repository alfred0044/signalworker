import logging
import traceback
from telethon import events
from config import SOURCE_CHANNEL_IDS
from filters import should_ignore_message, is_trade_signal
from sanitizer import sanitize_with_ai
from signal_processor import process_sanitized_signal

logger = logging.getLogger("signalworker")
logger.setLevel(logging.INFO)  # Set desired level
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
logger.addHandler(handler)

def register_handlers(client):
    @client.on(events.NewMessage(chats=SOURCE_CHANNEL_IDS))
    async def handler(event):
        text = getattr(event.message, "message", "")
        if not text:
            logger.warning("Received message with empty content.")
            return

        if should_ignore_message(text):
            logger.info("Ignored message: does not pass should_ignore_message.")
            return

        if not is_trade_signal(text):
            logger.debug("Message is not a trade signal.")
            return

        # Extract metadata
        try:
            source_name = getattr(event.chat, "title", "Unknown")
            chat_username = getattr(event.chat, "username", None)
            message_link = (
                f"https://t.me/{chat_username}/{event.message.id}"
                if chat_username else None
            )
            message_time = (
                event.message.date.isoformat() + "Z"
                if getattr(event.message, "date", None) else ""
            )

            logger.info("Sanitizing signal from %s: %s", source_name, text[:30])

            sanitized = await sanitize_with_ai(text)

            logger.info("Processing sanitized signal: %s", sanitized[:30])
            await process_sanitized_signal(
                sanitized,
                source=source_name,
                link=message_link,
                timestamp=message_time
            )

        except Exception as e:
            logger.error("Error processing message: %s\nOriginal message: %s\nTraceback: %s",
                         e, text[:1000], traceback.format_exc())
