import re
from utils import log_skipped_signal
def is_trade_signal(text: str) -> bool:
    keywords = ["XAUUSD", "GOLD", "TP", "SL", "BUY", "SELL", "ZONE", "ENTRY"]
    return any(kw in text.upper() for kw in keywords)


import re

import re

def should_ignore_message(text: str) -> bool:
    original_text = text  # for logging
    text = text.lower().strip()

    # Detect Stop Loss via common phrases
    has_sl = re.search(r'\bsl\b[\s:]*\d+', text) or re.search(r'stop\s*loss', text)

    # Detect TP via numeric values OR pip values
    has_tp_price = re.search(r'tp\d*[\s:]*[\$\d]+', text)
    has_tp_pips  = re.search(r'\btp\d*[\s:=+\-]*\d+\s*p[ip]*s?\b', text)  # matches "tp1: +50pips", "tp2 = 100 pip"
    has_tp_label = re.search(r'take\s*profit', text)  # generic label

    has_tp = has_tp_price or has_tp_pips or has_tp_label

    if not (has_sl and has_tp):
        print("🛑 Ignoring: missing SL or TP.")
        log_skipped_signal("Ignoring: missing SL or TP", original_text)
        return True  # Signal should be ignored

    return False  # Signal is acceptable



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

