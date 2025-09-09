import logging
import os
import re
import traceback
from dotenv import load_dotenv

from telethon import events
from config import SOURCE_CHANNEL_IDS
from filters import should_ignore_message, is_trade_signal
from sanitizer import sanitize_with_ai
from signal_processor import (
    process_sanitized_signal,
    find_signal_by_telegram_message_id,
    update_signal_json_and_dropbox,
)

logger = logging.getLogger("signalworker")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
logger.addHandler(handler)
OUTPUT_CHANNEL_ID = int(os.getenv("OUTPUT_CHANNEL_ID"))
profit_pattern = r"^\+\d+\s*pips?\b"
def register_handlers(client):

    @client.on(events.NewMessage(chats=SOURCE_CHANNEL_IDS))
    async def handler(event):
        OUTPUT_CHANNEL = await client.get_entity(OUTPUT_CHANNEL_ID)
        try:
            text = getattr(event.message, "message", "")
            if not text:
                logger.warning("Received message with empty content.")
                return

            if should_ignore_message(text):
                logger.info("Ignored message: does not pass should_ignore_message.")
                return

            # Handle manipulation commands directly if message is a reply
            if event.message.is_reply:
                replied_msg = await event.get_reply_message()
                original_msg_id = replied_msg.id if replied_msg else None
                if not original_msg_id:
                    logger.warning("Reply message but could not fetch original message.")
                    return

                signal = find_signal_by_telegram_message_id(original_msg_id)
                if signal:
                    lower_text = text.lower().strip()

                    # Early bypass: direct handling for known manipulations
                    if lower_text in {"close at entry"}:
                        signal["manipulation"] = lower_text.replace(" ", "_")  # e.g. "close_all"
                        update_signal_json_and_dropbox(signal)
                        await client.send_message(OUTPUT_CHANNEL, f"Signal updated: {lower_text}.")

                        return  # EARLY RETURN here to bypass AI sanitization

                    if lower_text in {"close all", "close","cancel","cancel all"}:
                        signal["manipulation"] = "close_all"  # e.g. "close_all"
                        update_signal_json_and_dropbox(signal)
                        await client.send_message(OUTPUT_CHANNEL, f"Signal updated: {lower_text}.")

                        return  # EARLY RETURN here to bypass AI sanitization

                    if lower_text.startswith("move sl to "):
                        try:
                            new_sl_str = lower_text.split("move sl to ")[1].strip()
                            new_sl = float(new_sl_str)
                            signal["manipulation"] = "move_sl"
                            signal["new_sl"] = new_sl
                            update_signal_json_and_dropbox(signal)
                            await client.send_message(OUTPUT_CHANNEL, f"Signal updated: move SL to {new_sl}.")
                            return  # EARLY RETURN here to bypass AI sanitization
                        except Exception:
                            await event.respond("Could not parse 'move sl to' value.")
                            return  # EARLY RETURN

                    # Profit message triggers cancel_pending manipulation
                    if re.match(profit_pattern, lower_text):
                        signal["manipulation"] = "cancel_pending"
                        update_signal_json_and_dropbox(signal)
                        await client.send_message(OUTPUT_CHANNEL,"Signal updated: all pending trades canceled due to profit message.")
                        return  # EARLY RETURN

                    # Unknown manipulation
                    await client.send_message(OUTPUT_CHANNEL, "Unrecognized update command.")
                    return  # EARLY RETURN

            # Not a manipulation reply --> treat as new signal
            if not is_trade_signal(text):
                logger.debug("Message is not a trade signal.")
                return

            # Metadata extraction for new signal
            source_name = getattr(event.chat, "title", "Unknown")
            chat_username = getattr(event.chat, "username", None)
            message_link = f"https://t.me/{chat_username}/{event.message.id}" if chat_username else None
            message_time = event.message.date.isoformat() + "Z" if getattr(event.message, "date", None) else ""

            logger.info(f"Sanitizing signal from {source_name}: {text[:30]}")
            sanitized = await sanitize_with_ai(text)
            logger.info(f"Processing sanitized signal: {sanitized[:30]}")

            await process_sanitized_signal(
                sanitized,
                source=source_name,
                link=message_link,
                timestamp=message_time,
                telegram_message_id=event.message.id,
            )

        except Exception as e:
            logger.error(
                f"Error processing message: {e}\nOriginal message: {text[:1000]}\nTraceback: {traceback.format_exc()}"
            )
