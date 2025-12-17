import asyncio
import os
import sys
import json
from datetime import datetime, timezone
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import PeerChannel
from dotenv import load_dotenv
import aiofiles

# Importiere zentrale Logik aus den Modulen
from handlers import register_handlers

# Hinweis: 'sanitizer' und 'signal_processor' müssen hier nicht importiert werden,
# da sie bereits von 'handlers.py' importiert und verwendet werden.
LOCAL_HISTORICAL_FOLDER = "local_signals"

# Lade Umgebungsvariablen aus .env
load_dotenv()

# --- GLOBALE KONFIGURATION ---
try:
    API_ID = int(os.getenv("TELEGRAM_API_ID"))
    API_HASH = os.getenv("TELEGRAM_API_HASH")
except (TypeError, ValueError):
    print("❌ Fehler: TELEGRAM_API_ID oder API_HASH fehlt oder ist ungültig in der .env-Datei.")
    sys.exit(1)

SESSION_STRING = os.getenv("TELEGRAM_STRING_SESSION")
TELEGRAM_PASSWORD = os.getenv("TELEGRAM_PASSWORD")  # Für client.start()
SAVE_DIR = "saved_signals"


# --- HILFSFUNKTIONEN (für Audit und Konvertierung) ---

async def store_sanitized_json(data: dict, source: str, telegram_message_id: int):
    """
    Speichert bereinigte Signaldaten in einer JSON-Datei zu Audit-Zwecken.
    (Optional, nur für die Speicherung der historischen Daten im Filesystem)
    """
    os.makedirs(SAVE_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_source = "".join(c if c.isalnum() else "_" for c in source or "unknown")
    filename = f"{timestamp}_{safe_source}_{telegram_message_id}.json"
    path = os.path.join(SAVE_DIR, filename)

    try:
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            # Speichert die rohe, bereinigte JSON-Struktur, bevor der Prozessor sie verarbeitet
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"✅ Gespeichert: {filename}")
        return path
    except Exception as e:
        print(f"⚠️ Fehler beim Speichern der bereinigten JSON: {e}")
        return None


def to_peer_channel(channel_id: str | int) -> PeerChannel | int:
    """
    Konvertiert Telegram-IDs in Telethon PeerChannel-Objekte.
    """
    if isinstance(channel_id, str) and channel_id.startswith("-100"):
        channel_id = int(channel_id[4:])
    if isinstance(channel_id, int):
        return PeerChannel(channel_id=channel_id)
    return channel_id


def make_aware(dt: datetime | None) -> datetime | None:
    """
    Stellt sicher, dass das datetime-Objekt zeitzonenbewusst ist (UTC).
    """
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# --- TELETHON CLIENT LOGIK ---

def get_client() -> TelegramClient:
    """
    Erstellt und gibt den Telethon-Client zurück.
    """
    if not SESSION_STRING:
        raise RuntimeError("TELEGRAM_STRING_SESSION fehlt!")
    return TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


async def fetch_channel_history(client: TelegramClient, channel_id: str | int, limit=None, min_date=None,
                                max_date=None) -> list:
    """
    Ruft historische Nachrichten aus einem Kanal im gegebenen Datumsbereich ab.
    """
    min_date = make_aware(min_date)
    max_date = make_aware(max_date)

    messages = []
    peer = to_peer_channel(channel_id)

    async for message in client.iter_messages(peer, limit=limit, reverse=False):
        if not getattr(message, "raw_text", None):
            continue

        if min_date and message.date < min_date:
            break

        if max_date and message.date > max_date:
            continue

        messages.append(message)

    return messages


async def replay_historical_messages(client: TelegramClient, messages: list):
    """
    Spielt historische Nachrichten ab, indem NewMessage-Events simuliert werden.
    WICHTIG: Die Verarbeitung (Sanitizer/Processor) erfolgt durch den externen Handler.
    """
    if not client._event_builders:
        print("⚠️ Warnung: Es wurden keine Handler registriert.")
        return

    # Greift auf die registrierte Handler-Funktion in handlers.py zu
    handler = client._event_builders[0][1]

    for message in messages:
        # Extrahiere den Nachrichtentext robust
        msg_text = getattr(message, 'raw_text', None) or getattr(message, 'message', '') or ''
        if not msg_text:
            continue

        # Simuliere ein Event-Objekt mit allen Attributen, die der Handler in handlers.py benötigt
        class DummyEvent:
            def __init__(self, msg):
                self.raw_text = msg_text
                self.message = msg
                # Die folgenden Attribute sind für die Link-Erstellung und Chat-Titel-Erkennung wichtig
                self.chat = getattr(msg, 'chat', None)
                self.chat_id = getattr(msg, 'chat_id', None)
                self.id = getattr(msg, 'id', None)
                self.is_reply = getattr(msg, 'is_reply', False)

        dummy_event = DummyEvent(message)

        # Ruft den Handler in handlers.py auf, um das Signal zu verarbeiten
        await handler(dummy_event)


# --- ARGS PARSING (unverändert) ---

def parse_args():
    """
    Analysiert Befehlszeilenargumente.
    """
    if len(sys.argv) < 2:
        print("Usage: python main.py <channel_id> [source_channel_ids_comma_separated] [start_date] [end_date]")
        sys.exit(1)

    channel_id = sys.argv[1]

    source_channel_ids = []
    start_date = None
    end_date = None

    # ... (Rest der parse_args Funktion, wie in der letzten Korrektur)

    if len(sys.argv) >= 3:
        arg2 = sys.argv[2]

        if "," in arg2 or (arg2.isdigit() or (arg2.startswith('-') and arg2[1:].isdigit())):
            try:
                source_channel_ids = list(map(int, arg2.split(','))) if "," in arg2 else [int(arg2)]

                if len(sys.argv) >= 4:
                    start_date = datetime.strptime(sys.argv[3], "%Y-%m-%d")
                    if len(sys.argv) >= 5:
                        end_date = datetime.strptime(sys.argv[4], "%Y-%m-%d")

            except ValueError:
                print(f"Invalid channel IDs or date format detected in argument 2/3.")
                sys.exit(1)

        else:
            try:
                start_date = datetime.strptime(arg2, "%Y-%m-%d")
                if len(sys.argv) >= 4:
                    end_date = datetime.strptime(sys.argv[3], "%Y-%m-%d")
            except ValueError:
                print(f"Invalid date format: {arg2}")
                sys.exit(1)

    return channel_id, source_channel_ids, start_date, end_date


# --- MAIN LOGIK ---

async def main(channel_id: str | int, min_date: datetime | None = None, max_date: datetime | None = None):
    client = get_client()

    # Verbindungsversuch (Verwendet optional das 2FA-Passwort)
    await client.start(password=TELEGRAM_PASSWORD)

    # Handler aus handlers.py importieren und registrieren
    register_handlers(client, [to_peer_channel(channel_id)], is_historical=True)

    print(f"Lade historische Nachrichten von Kanal {channel_id}...")
    messages = await fetch_channel_history(client, channel_id, min_date=min_date, max_date=max_date)
    print(f"✅ {len(messages)} Nachrichten im Datumsbereich gefunden.")

    if messages:
        print("▶️ Beginne Wiedergabe historischer Nachrichten...")
        await replay_historical_messages(client, messages)
        print("✅ Wiedergabe abgeschlossen.")

    # run_until_disconnected() ist hier nicht nötig, da das Skript nach der Wiedergabe beendet werden soll.
    # Wenn Sie nach der Wiedergabe in den Live-Modus wechseln möchten, fügen Sie es hinzu.
    # await client.run_until_disconnected()


if __name__ == "__main__":
    channel, ids, start_date, end_date = parse_args()

    print("\n--- Historische Signale ---\n")
    print(f"Zielkanal: {channel}")
    print(f"Startdatum: {start_date.strftime('%Y-%m-%d') if start_date else 'Anfang'}")
    print(f"Enddatum: {end_date.strftime('%Y-%m-%d') if end_date else 'Jetzt'}")
    print("\n--------------------------\n")

    try:
        asyncio.run(main(channel, start_date, end_date))
    except RuntimeError as e:
        if "session" in str(e) and "missing" in str(e):
            print("\n🚨 KRITISCHER FEHLER: TELEGRAM_STRING_SESSION fehlt oder ist ungültig.")
            print("Bitte erstellen Sie eine neue, autorisierte Sitzung.")
        else:
            # traceback.print_exc() wäre hier hilfreich, um andere Fehler zu sehen
            raise