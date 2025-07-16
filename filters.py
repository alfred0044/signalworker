import re
def is_trade_signal(text: str) -> bool:
    keywords = ["XAUUSD", "GOLD", "TP", "SL", "BUY", "SELL", "ZONE", "ENTRY"]
    return any(kw in text.upper() for kw in keywords)


import re

def should_ignore_message(text: str) -> bool:
    text = text.lower().strip()

    # ✅ Must contain SL and TP info
    has_sl = re.search(r'\b(sl|stop\s*loss|🔴)\b', text, re.IGNORECASE)
    has_tp = re.search(r'\b(tp\d*|take\s*profit|🟢)\b', text, re.IGNORECASE)

    if not (has_sl and has_tp):
        print("🛑 Ignoring: missing SL or TP.")
        return True

    # ✅ Blacklist phrases
    blacklist_keywords = [
        "result", "results", "manual close", "manually closed",
        "tp hit", "sl hit", "closed at", "update", "running",
        "active signal", "already running", "already active",
        "signal in play", "closed in profit", "floating",
        "summary", "recap", "performance", "winrate", "win rate",
        "today's trades", "we’ve just closed out", "total of", "lot size",
        "scalping", "pips in a day", "dollar profit", "$", "trade signals were shared",
        "incredible day", "signals reached", "signals missed"
    ]
    for word in blacklist_keywords:
        if word in text:
            print(f"🛑 Ignoring: matched blacklist keyword '{word}'")
            return True

    # ✅ Heuristic patterns for performance summaries
    update_patterns = [
        r'\b(tp|sl)\s*(hit|triggered)?[:\-\s]*[\+\-]?\d+\s*pips?\b',
        r'\+[\d\.]+\s*pips?\b',
        r'\bsl\s+was\s+hit\b',
        r'^(buy|sell)[\s\S]{0,20}:\s*\+?\d+\s*pips?',
        r'\b\d{1,3}%\s*win\s*rate\b',
        r'\b\d+\s*trade(s)?\s*(shared|executed|given)\b',
        r'\$\d+',  # Mentions of $ amounts
        r'\d+\s*pips\s*(in\s*(a|one)?\s*day)?',
        r'\d+\)\s*(buy|sell)'  # List-style numbering of trades
    ]
    for pattern in update_patterns:
        if re.search(pattern, text):
            print(f"🛑 Ignoring: matched pattern '{pattern}'")
            return True

    print("✅ Message accepted as potential signal.")
    return False

