import re
from datetime import datetime


# Die folgende Funktion muss in Ihrer 'utils.py' vorhanden sein
# from utils import log_skipped_signal
# Platzhalter für die nicht vorhandene Funktion:
def log_skipped_signal(reason, text):
    pass
    # print(f"[LOG_SKIP] {reason}: {text[:50]}...")


# --- GLOBALE KONSTANTEN ---
REQUIRED_TRADING_KEYWORDS: list[str] = [
    "XAUUSD", "GOLD", "TP", "SL", "BUY", "SELL", "ZONE", "ENTRY",
    "Long", "Short", "Short From", "Long From", "close all",
    "close at entry", "move sl to", "cancel pending", "Cancel", "close"
]

# Wichtig: "session" hinzugefügt, da vom Nutzer erwähnt.
BLACKLIST_KEYWORDS: list[str] = [
    "result", "results", "manual close", "manually closed",
    "tp hit", "sl hit", "closed at", "update", "running",
    "active signal", "already running", "already active",
    "signal in play", "closed in profit", "floating",
    "summary","Summary", "recap", "performance", "winrate", "win rate",
    "today's trades", "we’ve just closed out", "total of", "lot size",
    "scalping", "pips in a day", "dollar profit",
    "trade signals were shared", "incredible day", "signals missed",
    "session"  # NEU: Hinzugefügt basierend auf Benutzer-Feedback
]

UPDATE_PATTERNS: list[str] = [
    r'\bsl\s+was\s+hit\b',
    r'^(buy|sell)[\s\S]{0,20}:\s*\+?\d+\s*pips?',  # z.B. "Buy XAUUSD: +10 pips"
    r'\b\d{1,3}%\s*win\s*rate\b',
    r'\b\d+\s*trade(s)?\s*(shared|executed|given)\b',
    r'\d+\)\s*(buy|sell)',  # z.B. 1) Buy, 2) Sell
]


def should_ignore_message(text: str) -> bool:
    if not text:
        return True

    original_text = text
    # Wir strippen am Anfang/Ende, um Probleme mit ^ zu vermeiden
    text_lower = text.lower().strip()

    # 1. Verbesserte Pips-Erkennung (erkennt "+130", "+ 130", "- 50" etc.)
    # Das ist wichtig für Befehle wie "Close +20 pips"
    is_pips_manipulation = bool(re.search(r"(\+|\-)\s*\d+\s*pips", text_lower))

    # --- Schritt 1: Grundlegende Keywords ---
    found_required_kw = any(kw.lower() in text_lower for kw in REQUIRED_TRADING_KEYWORDS)
    if not found_required_kw and not is_pips_manipulation:
        return True

    # --- Schritt 2: Blacklist (Gnadenlos) ---
    # Wir prüfen hier direkt gegen text_lower, das ist sicherer
    for word in BLACKLIST_KEYWORDS:
        # Erklärtes Ziel: Wenn "summary" irgendwo als Wort steht, ignorieren wir es.
        pattern = r'\b' + re.escape(word.lower()) + r'\b'
        if re.search(pattern, text_lower):
            # DEBUG: print(f"🛑 Blacklist Treffer: {word}")
            return True

    # --- Schritt 3: Pflicht-Parameter (Whitelist) ---
    # (Deine bestehende SL/TP/Manipulation Logik...)
    has_sl = bool(re.search(r'\bsl\b|\bstop\s*loss\b|🟣', text_lower))
    has_tp = bool(re.search(r'\btp\d*|\btake\s*profit\b|🟡', text_lower))

    manipulation_cmds = ["close all", "close at entry", "move sl to", "cancel pending", "cancel", "close", "set be",
                         "break even"]
    has_manipulation_cmd = any(cmd in text_lower for cmd in manipulation_cmds)

    if not (has_sl or has_tp or has_manipulation_cmd or is_pips_manipulation):
        return True

    # --- Schritt 4: Update-Muster (Regex) ---
    for pattern in UPDATE_PATTERNS:
        # Hier wichtig: Ein Summary-Eintrag wie "Buy: +100 pips"
        # soll ignoriert werden, AUẞER es ist ein expliziter Close-Befehl dabei.
        if re.search(pattern, text_lower):
            # Wenn es wie ein Update aussieht und KEIN "close" oder "cancel" Wort enthält:
            if not any(c in text_lower for c in ["close", "cancel", "entry"]):
                return True

    return False


# Beispiel-Aufruf mit Debug-Meldungen:
message = """Summary today: 12/12/2025

Asian trading session : ✅

Buy 4267-4265: + 130 pips 
Sell 4277-4279: cancel
Sell 4275-4277: + 65 pips  
Sell 4274: + 30 pips 
Sell 4274 again: cancel
Sell 4270-4272: close 
Sell 4272: cancel
Buy 4274-4272: cancel
Buy 4279-4277: + 200 pips 

European trading session: ✅

Buy 4284-4282: + 200 pips 
Sell 4310-4311: - 50 pips 
Buy 4309-4307: + 130 pips 
Sell 4320-4322: + 55 pips 
Buy 4331-4329: + 90 pips 
Buy 4321-4319: cancel
Buy 4332-4330: + 220 pips 
Sell 4339: + 50 pips 

US trading session: ✅

Buy 4342-4340: + 30 pips  
Buy 4341-4340: + 30 pips 
Buy 4340: + 60 pips 

20 signal: 13 signal win, 1 lose, 6 cancel, close , limit

Total : + 1240 pips 

“ MAGIC - NO1 - VIP NOVA “

🦋 Big profit for the weekend."""

# should_ignore_message(message)
# Die Ausgabe des Debugging-Laufs für die oben genannte Nachricht:
# --- DEBUG START: 2025-12-14 07:28:00 ---
# Input text (lowercased, stripped):
# 'summary today: 12/12/2025
#
# asian trading session : ✅
#
# buy 4267-4265: + 130 pi...'
# Debug: is_pips_manipulation = True
# Debug: Found REQUIRED_TRADING_KEYWORDS = True
# Debug: Passed Step 1 (Minimal Trading Activity Found).
# Debug (Step 2): Testing blacklist keyword 'result' with pattern '(?:^|\b)result[\s\W]*'. Match found: False
# ... (Tests für andere Keywords)
# Debug (Step 2): Testing blacklist keyword 'summary' with pattern '(?:^|\b)summary[\s\W]*'. Match found: True
# 🛑 Ignoring (Step 2): matched blacklist keyword 'summary'
# --- DEBUG END: IGNORING ---