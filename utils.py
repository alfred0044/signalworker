from datetime import datetime


def split_signals(text: str) -> list:
    blocks = text.strip().split("* Instrument:")
    return [f"* Instrument:{block.strip()}" for block in blocks if block.strip()]

def log_to_google_sheets(signal_text: str):
    print("📄 Logging to sheet:\n", signal_text)


def log_skipped_signal(reason, signal, logfile="skipped_signals.log"):
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": "WARNING",
        "reason": reason,
        "signal": signal
    }
    with open(logfile, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")