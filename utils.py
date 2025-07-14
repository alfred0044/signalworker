
def split_signals(text: str) -> list:
    blocks = text.strip().split("* Instrument:")
    return [f"* Instrument:{block.strip()}" for block in blocks if block.strip()]

def log_to_google_sheets(signal_text: str):
    print("📄 Logging to sheet:\n", signal_text)
