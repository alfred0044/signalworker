# handlers.py

import logging
from telethon import events
from sanitizer import sanitize_signal
from signal_processor import process_sanitized_signal
# WICHTIG: Stellen Sie sicher, dass diese Imports vorhanden sind!
from filters import should_ignore_message  # Die korrigierte Funktion
from signal_db import get_signalid, store_signalid
from datetime import datetime

logger = logging.getLogger("signalworker.handlers")


def register_handlers(client, source_channels, is_historical=False):
    @client.on(events.NewMessage(chats=source_channels))
    async def handler(event):
        text = event.raw_text.strip()
        if not text:
            return

        # ... (Filter, Kontext-Extraktion)

        is_reply = event.message.is_reply
        reply_to_msg_id = event.message.reply_to_msg_id
        telegram_message_id = event.id

        source_title = getattr(event.chat, 'title', 'unknown_chat')
        link = f"https://t.me/c/{abs(event.chat_id)}/{event.id}"
        timestamp = str(event.message.date)

        # --- 2. ID MANAGEMENT (KRITISCHER FIX) ---
        main_signalid = None

        if is_reply and reply_to_msg_id:
            # Szenario A: Manipulation (Antwort auf ein anderes Signal)
            main_signalid = get_signalid(reply_to_msg_id)

            if not main_signalid:
                # KRITISCHER FIX: Wenn die ID des Originals NICHT gefunden wird,
                # erstellen wir sie JETZT nachträglich anhand der Original-Nachrichten-ID.
                main_signalid = store_signalid(reply_to_msg_id)

                # Wenn wir hier sind, bedeutet das, dass das Originalsignal nicht
                # als "neues Signal" gespeichert wurde oder die DB-Synchronisation fehlschlug.
                logger.warning(
                    f"Original signal ID not found for reply_to_msg_id: {reply_to_msg_id}. New ID {main_signalid} created based on original message ID.")

            # Die aktuelle Nachricht (Manipulation) muss auch zur Haupt-Signal-ID zugeordnet werden
            # (falls sie noch nicht existiert), aber die main_signalid ist die ID des Originals.
            if telegram_message_id and get_signalid(telegram_message_id) is None:
                store_signalid(telegram_message_id, main_signalid)


        elif telegram_message_id:
            # Szenario B: Neues Signal (Keine Antwort)
            main_signalid = get_signalid(telegram_message_id) or store_signalid(telegram_message_id)

        # Dies ist die finale Prüfung, falls get/store_signalid fehlschlägt.
        if not main_signalid:
            logger.error(f"Failed to determine signal ID for message ID {telegram_message_id}.")
            return

        # --- 3. Sanitizing (unverändert) ---
        sanitized = await sanitize_signal(
            signal_text=text,
            is_reply=is_reply,
            main_signalid=main_signalid,
            link=link,
            source=source_title
        )

        # Optional: Prüfung auf leeres sanitized JSON (falls sanitize_signal leer zurückgibt)
        if not sanitized or not isinstance(sanitized, dict) or not any(sanitized.values()):
            logger.warning(f"Sanitizer returned empty data for signal ID {main_signalid}. Message ignored.")
            return

        # --- 4. Processing (unverändert) ---
        await process_sanitized_signal(
            sanitized,
            source=source_title,
            link=link,
            timestamp=timestamp,
            telegram_message_id=telegram_message_id,
            reply_to_msg_id=reply_to_msg_id,
            override_signalid=main_signalid,
            is_historical=is_historical
        )