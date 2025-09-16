import re
from datetime import datetime
from utils import log_skipped_signal

def is_trade_signal(text: str) -> bool:
    """
    Determines whether the text is considered a trade signal.
    Accepts signals that contain trading keywords or manipulation commands.
    """
    keywords = [
        "XAUUSD", "GOLD", "TP", "SL", "BUY", "SELL", "ZONE", "ENTRY", "Long", "Short", "Short From","Long From" 
        "close all", "close at entry", "move sl to", "cancel pending", "Cancel", "close"
    ]
    text_upper = text.upper()
    # Include pips profit reply as manipulation
    pips_reply = re.search(r"\+\d+\s*pips", text)
    return any(kw.upper() in text_upper for kw in keywords) or pips_reply

def should_ignore_message(text: str) -> bool:
    original_text = text
    text = text.lower().strip()
    print(text)
    has_sl = re.search(r'\bsl\b[\s:]*\d+', text) or re.search(r'stop\s*loss', text, re.IGNORECASE)
    has_tp_price = re.search(r'tp\d*[\s:]*[\$\d]+', text, re.IGNORECASE)
    has_tp_pips  = re.search(r'\btp\d*[\s:=+\-]*\d+\s*p[ip]*s?\b', text,re.IGNORECASE)
    has_tp_label = re.search(r'take\s*profit', text,re.IGNORECASE)
    has_tp = has_tp_price or has_tp_pips or has_tp_label

    # Accept manipulation commands and pips-profit even if missing TP/SL
    manipulation_commands_present = (
        any(cmd in text for cmd in ["close all", "close at entry", "move sl to", "cancel pending", "cancel"]) or
        re.search(r"\+\d+\s*pips", text)
    )

    if not (has_sl and has_tp) and not manipulation_commands_present:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"🛑 {timestamp} - Ignoring: missing SL or TP.")
        log_skipped_signal(f"{timestamp} - Ignoring: missing SL or TP", original_text)
        return True

    # Blacklist phrases to ignore performance messages etc.
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
        if word in text:
            print(f"🛑 Ignoring: matched blacklist keyword '{word}'")
            log_skipped_signal(f"🛑 Ignoring: matched blacklist keyword '{word}'", original_text)
            return True

    # Heuristic patterns for ignoring performance summaries etc.
    update_patterns = [
        r'\b(tp|sl)\s*(hit|triggered)?[:\-\s]*[\+\-]?\d+\s*pips?\b',
        r'\+[\d\.]+\s*pips?\b',
        r'\bsl\s+was\s+hit\b',
        r'^(buy|sell)[\s\S]{0,20}:\s*\+?\d+\s*pips?',
        r'\b\d{1,3}%\s*win\s*rate\b',
        r'\b\d+\s*trade(s)?\s*(shared|executed|given)\b',

        r'\d+\)\s*(buy|sell)',  # List-style numbering of trades
    ]

    for pattern in update_patterns:
        # EXCEPTION: Accept "+XXpips" if used as reply/manipulation (cancel pending)
        if re.search(pattern, text) and not re.search(r"\+\d+\s*pips", text):
            print(f"🛑 Ignoring: matched pattern '{pattern}'")
            log_skipped_signal("Ignored signal: update pattern detected", original_text)
            return True

    print("✅ Message accepted as potential signal.")
    return False
