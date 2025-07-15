import re
def is_trade_signal(text: str) -> bool:
    keywords = ["XAUUSD", "GOLD", "TP", "SL", "BUY", "SELL", "ZONE", "ENTRY"]
    return any(kw in text.upper() for kw in keywords)


def should_ignore_message(text: str) -> bool:
    text = text.lower()

    # Heuristics: common update phrases or numeric summaries
    update_patterns = [
        r'\b(tp|sl)[\s:]*(hit|triggered)?[\s:-]+\+?\d+\s*pips?',   # "TP1 hit +40"
        r'\+[\d\.]+\s*pips?',                                  # "+40 pips"
        r'sl\s+(hit|was hit)',                                 # "SL was hit"
        r'update[d]?',                                         # "update"
        r'(running|active)\s+signal',                          # "already running signal"
        r'^buy\b.*?:\s*\+\d+',                                 # "BUY 3330-3328: +40"
        r'^sell\b.*?:\s*\+\d+',                                # "SELL 2300-2295: +30"
        r'\bresult\b|\bclosed\b|\bclose\b'                     # "Closed manually"
    ]

    for pattern in update_patterns:
        if re.search(pattern, text):
            return True

    return False