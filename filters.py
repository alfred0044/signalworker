import re
def is_trade_signal(text: str) -> bool:
    keywords = ["XAUUSD", "GOLD", "TP", "SL", "BUY", "SELL", "ZONE", "ENTRY"]
    return any(kw in text.upper() for kw in keywords)


import re

def should_ignore_message(text: str) -> bool:
    text = text.lower().strip()

    # Accepts "sl", "sl1234", "sl: 1234", "stop loss", etc
    has_sl = re.search(r'sl[\s:]*\d+', text) or re.search(r'stop\s*loss', text)
    # Accepts "tp1", "tp2: $3350", etc
    has_tp = re.search(r'tp\d*[\s:]*[\$\d]+', text) or re.search(r'take\s*profit', text)

    if not (has_sl and has_tp):
        print("🛑 Ignoring: missing SL or TP.")
        log_skipped_signal("Ignoring: missing SL or TP", text);
        return True


    # ✅ Blacklist phrases
    blacklist_keywords = [
        "result", "results", "manual close", "manually closed",
        "tp hit", "sl hit", "closed at", "update", "running",
        "active signal", "already running", "already active",
        "signal in play", "closed in profit", "floating",
        "summary", "recap", "performance", "winrate", "win rate",
        "today's trades", "we’ve just closed out", "total of", "lot size",
        "scalping", "pips in a day", "dollar profit",  # <-- keep this!
        # "$",   <-- REMOVE THIS LINE
        "trade signals were shared", "incredible day", "signals reached", "signals missed"
    ]
    for word in blacklist_keywords:
        if word in text:
            print(f"🛑 Ignoring: matched blacklist keyword '{word}'")
            log_skipped_signal(f"🛑 Ignoring: matched blacklist keyword '{word}'",message );
            return True

    # ✅ Heuristic patterns for performance summaries
    update_patterns = [
        r'\b(tp|sl)\s*(hit|triggered)?[:\-\s]*[\+\-]?\d+\s*pips?\b',
        r'\+[\d\.]+\s*pips?\b',
        r'\bsl\s+was\s+hit\b',
        r'^(buy|sell)[\s\S]{0,20}:\s*\+?\d+\s*pips?',
        r'\b\d{1,3}%\s*win\s*rate\b',
        r'\b\d+\s*trade(s)?\s*(shared|executed|given)\b',
        # r'\$\d+',  # <--- REMOVE OR COMMENT OUT THIS LINE
        r'\d+\s*pips\s*(in\s*(a|one)?\s*day)?',
        r'\d+\)\s*(buy|sell)'  # List-style numbering of trades
    ]

    for pattern in update_patterns:
        if re.search(pattern, text):
            print(f"🛑 Ignoring: matched pattern '{pattern}'")
            log_skipped_signal("No TP detected", text)
            return True

    print("✅ Message accepted as potential signal.")
    return False

