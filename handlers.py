import logging
from telethon import events
from sanitizer import sanitize_signal
from signal_processor import process_sanitized_signal
from filters import should_ignore_message,is_trade_signal
from signal_db  import get_signalid,store_signalid
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
        is_reply = event.message.is_reply
        reply_to_msg_id = event.message.reply_to_msg_id
        telegram_message_id = event.id
        if should_ignore_message(text):
            logger.info("Ignored message: does not pass should_ignore_message.")
            return

        if not is_trade_signal(text):
            logger.debug("Message is not a trade signal.")
            return

        main_signalid = None
        if is_reply and reply_to_msg_id:
            # Manipulation: Look up the original ID
            main_signalid = get_signalid(reply_to_msg_id)
            if not main_signalid:
                logger.warning(
                    f"Manipulation received but original signal ID not found for reply_to_msg_id: {reply_to_msg_id}")
                return
        elif telegram_message_id:
            # New Signal: Get existing ID or create new one
            main_signalid = get_signalid(telegram_message_id) or store_signalid(telegram_message_id)

        if not main_signalid:
            logger.error("Failed to determine signal ID for processing.")
            return

        sanitized = await sanitize_signal(
            signal_text=text,
            is_reply=event.message.is_reply,
            main_signalid=main_signalid
        )

        await process_sanitized_signal(
            sanitized,
            source=event.chat.title,
            link=f"https://t.me/c/{abs(event.chat_id)}/{event.id}",
            timestamp=str(event.message.date),
            telegram_message_id=event.id,
            reply_to_msg_id=event.message.reply_to_msg_id  # NEW
        )
        signal_id_processed = await process_sanitized_signal(
            sanitized,
            source=event.chat.title,
            link=f"https://t.me/c/{abs(event.chat_id)}/{event.id}",
            timestamp=str(event.message.date),
            telegram_message_id=telegram_message_id,
            reply_to_msg_id=reply_to_msg_id,
            # Pass the ID explicitly to the processor
            override_signalid=main_signalid
        )
        if signal_id_processed:
            logger.info(f"✅ Signal batch {signal_id_processed} processed successfully.")
            # If the processor handles writing, no need to call store_signal_batch here.

