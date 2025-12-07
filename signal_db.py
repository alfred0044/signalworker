import sqlite3
import os
import uuid

DB_PATH = os.getenv("SIGNAL_DB_PATH", "signal_mapping.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Parent signals (1 row per Telegram message)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            telegram_message_id INTEGER PRIMARY KEY,
            signalid TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Child entries (1 row per trade entry or manipulation linked to a signal)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signalid TEXT NOT NULL,
            telegram_message_id INTEGER,
            type TEXT,          -- "entry" or "manipulation"
            payload TEXT,       -- JSON payload for debugging/logging
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (signalid) REFERENCES signals(signalid)
        )
    """)

    conn.commit()
    conn.close()


def get_signalid(telegram_message_id: int) -> str | None:
    """
    Retrieves the persistent signalid (UUID) associated with a given Telegram message ID.

    This is used for:
    1. New signals: To check if a signal ID was already generated.
    2. Manipulations: To find the original signal ID via the reply_to_msg_id.
    """
    if not isinstance(telegram_message_id, int):
        logger.error(f"Invalid message ID type provided: {type(telegram_message_id)}")
        return None

    # Replace with database lookup: e.g., db.fetch_signalid(telegram_message_id)
    signal_id = MESSAGE_ID_TO_SIGNAL_ID.get(telegram_message_id)

    if signal_id:
        logger.debug(f"Found signal ID {signal_id} for message ID {telegram_message_id}.")
    else:
        logger.debug(f"No signal ID found for message ID {telegram_message_id}.")

    return signal_id


def store_signalid(telegram_message_id: int) -> str:
    """
    Generates a new UUID signalid and stores the mapping to the Telegram message ID.

    This is called only when processing a NEW signal for the first time.
    """
    new_signal_id = str(uuid.uuid4())

    # Replace with database storage: e.g., db.save_mapping(telegram_message_id, new_signal_id)
    MESSAGE_ID_TO_SIGNAL_ID[telegram_message_id] = new_signal_id

    logger.info(f"Stored new signal ID {new_signal_id} for message ID {telegram_message_id}.")
    return new_signal_id
def store_signalid(telegram_message_id: int, signalid: str = None) -> str:
    """
    Save one signalid for the given Telegram parent message.
    If not exists, create it.
    """
    if not signalid:
        signalid = str(uuid.uuid4())

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO signals (telegram_message_id, signalid) VALUES (?, ?)",
                (telegram_message_id, signalid))
    conn.commit()
    conn.close()
    return signalid


def get_signalid(telegram_message_id: int) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT signalid FROM signals WHERE telegram_message_id = ?", (telegram_message_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def add_entry(signalid: str, telegram_message_id: int, entry_type: str, payload: str):
    """
    Add a child entry (trade split or manipulation) linked to a master signalid.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO entries (signalid, telegram_message_id, type, payload)
        VALUES (?, ?, ?, ?)
    """, (signalid, telegram_message_id, entry_type, payload))
    conn.commit()
    conn.close()
