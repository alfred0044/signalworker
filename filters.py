import re
from datetime import datetime
from utils import log_skipped_signal


def is_trade_signal(text: str) -> bool:
    """
    Determines whether the text is considered a trade signal.
    Accepts signals that contain trading keywords or manipulation commands.
    """
    keywords = [
        "XAUUSD", "GOLD", "TP", "SL", "BUY", "SELL", "ZONE", "ENTRY", "Long", "Short", "Short From", "Long From"
                                                                                                     "close all",
        "close at entry", "move sl to", "cancel pending", "Cancel", "close"
    ]
    text_upper = text.upper()
    # Include pips profit reply as manipulation
    pips_reply = re.search(r"\+\d+\s*pips", text)
    return any(kw.upper() in text_upper for kw in keywords) or pips_reply


import re
from datetime import datetime


def should_ignore_message(text: str) -> bool:
    original_text = text
    text_lower = text.lower().strip()
    print(text_lower)

    # Expanded SL presence detection: match traditional, emoji and numbers after markers
    has_sl = (
        re.search(r'\bsl\b[\s:\-]*\d+', text_lower)
        or re.search(r'stop\s*loss', text_lower)
        or re.search(r'🟣', text)  # any occurrence of purple circle emoji signaling SL
    )

    # Expanded TP presence detection: match TP with prices, emoji, or phrase
    has_tp_price = (
        re.search(r'tp\d*[\s:=+\-]*[\$\d\.]+', text_lower)
        or re.search(r'🟡', text)    # yellow circle emoji signals TP
    )

    has_tp_pips = re.search(r'\btp\d*[\s:=+\-]*\d+\s*p[ip]*s?\b', text_lower)
    has_tp_label = re.search(r'take\s*profit', text_lower)
    has_tp = has_tp_price or has_tp_pips or has_tp_label

    manipulation_commands_present = (
        any(cmd in text_lower for cmd in ["close all", "close at entry", "move sl to", "cancel pending", "cancel", "close"])
        or re.search(r"\+\d+\s*pips", text_lower)
    )

    # Allow signals if any of these found (SL marker, TP marker, or manipulation commands)
    if not (has_sl or has_tp or manipulation_commands_present):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"🛑 {timestamp} - Ignoring: missing SL or TP or manipulation commands.")
        log_skipped_signal(f"{timestamp} - Ignoring: missing SL or TP or manipulation commands", original_text)
        return True

    # blacklist unchanged (case insensitive) with whole word or phrase boundaries
    blacklist_keywords = [
        "result", "results", "manual close", "manually closed",
        "tp hit", "sl hit", "closed at", "update", "running",
        "active signal", "already running", "already active",
        "signal in play", "closed in profit", "floating",
        "summary", "recap", "performance", "winrate", "win rate",
        "today's trades", "we’ve just closed out", "total of", "lot size",
        "scalping", "pips in a day", "dollar profit",
        "trade signals were shared", "incredible day", "signals reached", "signals missed"
    ]
    for word in blacklist_keywords:
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
            print(f"🛑 Ignoring: matched blacklist keyword '{word}'")
            log_skipped_signal(f"🛑 Ignoring: matched blacklist keyword '{word}'", original_text)
            return True

    # update signals patterns unchanged but case insensitive on text_lower
    update_patterns = [
        r'\b(tp|sl)\s*(hit|triggered)?[:\-\s]*[\+\-]?\d+\s*pips?\b',
        r'\+[\d\.]+\s*pips?\b',
        r'\bsl\s+was\s+hit\b',
        r'^(buy|sell)[\s\S]{0,20}:\s*\+?\d+\s*pips?',
        r'\b\d{1,3}%\s*win\s*rate\b',
        r'\b\d+\s*trade(s)?\s*(shared|executed|given)\b',
        r'\d+\)\s*(buy|sell)',
    ]

    for pattern in update_patterns:
        if re.search(pattern, text_lower) and not re.search(r"\+\d+\s*pips", text_lower):
            print(f"🛑 Ignoring: matched pattern '{pattern}'")
            log_skipped_signal("Ignored signal: update pattern detected", original_text)
            return True

    print("✅ Message accepted as potential signal.")
    return False