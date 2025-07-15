import re
def is_trade_signal(text: str) -> bool:
    keywords = ["XAUUSD", "GOLD", "TP", "SL", "BUY", "SELL", "ZONE", "ENTRY"]
    return any(kw in text.upper() for kw in keywords)


def should_ignore_message(text: str) -> bool:
    text = text.lower().strip()

    # ✅ Must contain SL and TP info
    has_sl = re.search(r'\b(sl|stop\s*loss|🔴)\b', text, re.IGNORECASE)
    has_tp = re.search(r'\b(tp|take\s*profit|🟢)\b', text, re.IGNORECASE)

    if not (has_sl and has_tp):
        print("🛑 Ignoring: missing SL or TP.")
        return True

    # ✅ Blacklist phrases
    blacklist_keywords = [
        "result", "results", "manual close", "manually closed",
        "tp hit", "sl hit", "closed at", "update", "running",
        "active signal", "already running", "already active",
        "signal in play", "closed in profit", "floating"
    ]
    for word in blacklist_keywords:
        if word in text:
            print(f"🛑 Ignoring: matched blacklist keyword '{word}'")
            return True

    # ✅ Heuristic update patterns
    update_patterns = [
        r'\b(tp|sl)\s*(hit|triggered)?[:\-\s]*[\+\-]?\d+\s*pips?\b',
        r'\+[\d\.]+\s*pips?\b',
        r'\bsl\s+was\s+hit\b',
        r'^(buy|sell)[\s\S]{0,20}:\s*\+?\d+\s*pips?'
    ]
    for pattern in update_patterns:
        if re.search(pattern, text):
            print(f"🛑 Ignoring: matched pattern '{pattern}'")
            return True

    print("✅ Message accepted as potential signal.")
    return False
