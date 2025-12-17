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
    "summary", "recap", "performance", "winrate", "win rate",
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
    original_text = text
    text_lower = text.lower().strip()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')



    # NEU: Manipulationen müssen frühzeitig erkannt werden, damit der BLACKLIST-Filter sie nicht ignoriert
    is_pips_manipulation = re.search(r"\+\d+\s*pips", text_lower)


    # --- 1. PRE-FILTER: MINIMALE PRÜFUNG AUF HANDELSAKTIVITÄT ---
    found_required_kw = any(kw.lower() in text_lower for kw in REQUIRED_TRADING_KEYWORDS)


    if not found_required_kw and not is_pips_manipulation:

        log_skipped_signal(f"{timestamp} - Ignoring: No core trading keyword found", original_text)

        return True



    # --- 2. BLACKLIST-PRÜFUNG (MUSS VOR DER WHITELISTING-PRÜFUNG ERFOLGEN) ---
    for word in BLACKLIST_KEYWORDS:
        # ROBUSTERE PRÜFUNG: Sucht entweder am Anfang (^) oder an einer Wortgrenze (\b),
        # gefolgt von beliebigen Leerzeichen, Satzzeichen, etc. ([\s\W]*).
        pattern = r'(?:^|\b)' + re.escape(word) + r'[\s\W]*'

        match = re.search(pattern, original_text, re.IGNORECASE)


        if match:

            log_skipped_signal(f"🛑 Ignoring: matched blacklist keyword '{word}'", original_text)

            return True



    # --- 3. PRÜFUNG AUF ZWINGENDE TRADING-PARAMETER (WHITELISTING) ---

    # SL Check
    has_sl_match_1 = re.search(r'\bsl\b[\s:\-]*\d+', text_lower)
    has_sl_match_2 = re.search(r'stop\s*loss', text_lower)
    has_sl_match_3 = re.search(r'🟣', text)
    has_sl = bool(has_sl_match_1 or has_sl_match_2 or has_sl_match_3)


    # TP Check
    has_tp_match_1 = re.search(r'tp\d*[\s:=+\-]*[\$\d\.]+', text_lower)
    has_tp_match_2 = re.search(r'🟡', text)
    has_tp_match_3 = re.search(r'\btp\d*[\s:=+\-]*\d+\s*p[ip]*s?\b', text_lower)
    has_tp_match_4 = re.search(r'take\s*profit', text_lower)
    has_tp = bool(has_tp_match_1 or has_tp_match_2 or has_tp_match_3 or has_tp_match_4)



    # Manipulation Check
    manipulation_cmds = ["close all", "close at entry", "move sl to", "cancel pending", "cancel", "close", "set be", "break even"]
    has_manipulation_cmd = any(cmd in text_lower for cmd in manipulation_cmds)
    manipulation_commands_present = has_manipulation_cmd or bool(is_pips_manipulation)



    # Wenn weder SL/TP noch ein expliziter Manipulationsbefehl vorhanden ist, ignorieren.
    if not (has_sl or has_tp or manipulation_commands_present):

        log_skipped_signal(f"{timestamp} - Ignoring: missing SL or TP or manipulation commands", original_text)

        return True



    # --- 4. UPDATE-MUSTER PRÜFUNG (Regex-Muster) ---
    for i, pattern in enumerate(UPDATE_PATTERNS):
        match = re.search(pattern, text_lower)


        if match and not is_pips_manipulation:

            log_skipped_signal("Ignored signal: update pattern detected", original_text)

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