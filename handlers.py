import logging
from telethon import events
from sanitizer import sanitize_signal
from signal_processor import process_sanitized_signal
from filters import should_ignore_message,is_trade_signal

logger = logging.getLogger("signalworker.handlers")

# -------------------------------------------
# Register handlers with the given Telethon client
# -------------------------------------------
def register_handlers(client, source_channels):
    @client.on(events.NewMessage(chats=source_channels))
    async def handler(event):
        text = event.raw_text.strip()
        if not text:
            return

        if should_ignore_message(text):
            logger.info("Ignored message: does not pass should_ignore_message.")
            return

        if not is_trade_signal(text):
            logger.debug("Message is not a trade signal.")
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

