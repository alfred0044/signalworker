import asyncio
import json
from datetime import datetime
import re
import uuid
import logging
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

# Logger setup
logger = logging.getLogger("signalworker.sanitizer")
logger.setLevel(logging.DEBUG)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
    logger.addHandler(handler)

AI_MODEL = os.getenv("AI_MODEL", "llama-3.3-70b-versatile")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.groq.com/openai/v1")
AI_KEY = os.getenv("AI_KEY", os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY"))

if not AI_KEY:
    raise RuntimeError("❌ Missing AI_KEY (set GROQ_API_KEY or OPENAI_API_KEY in .env)")

client = OpenAI(api_key=AI_KEY, base_url=AI_BASE_URL)

# --- TP calculation helper ---
def calc_tp_from_pips(entry, pips, signal_type):
    pips_str = str(pips)
    match = re.search(r'(\d+)', pips_str)
    if not match:
        return None
    pip_value = float(match.group(1))
    movement = pip_value * 0.10
    if signal_type.upper() == "BUY LIMIT":
        return round(entry + movement, 2)
    elif signal_type.upper() == "SELL LIMIT":
        return round(entry - movement, 2)
    return None

# --- TP assignment helper ---
def assign_tp_values(entries, raw_tps, signal_type):
    if len(raw_tps) == 4:
        start, end = entries[0], entries[-1]
        step = (start - end) / 3
        entries = [round(start - i * step, 2) for i in range(4)]
    elif len(raw_tps) == 3 and len(entries) == 1:
        entries = [entries[0]] * 3
    tps = []
    for i, tp_raw in enumerate(raw_tps):
        if tp_raw is None:
            tps.append(None)
            continue
        tp_str = str(tp_raw)
        tp_lower = tp_str.lower()
        entry = entries[i] if i < len(entries) else entries[-1]
        if "open" in tp_lower:
            tps.append(None)
        elif "pips" in tp_lower:
            tps.append(calc_tp_from_pips(entry, tp_str, signal_type))
        else:
            try:
                tps.append(float(tp_str))
            except ValueError:
                tps.append(None)
                tps.append(None)
                tps.append(None)
    return entries, tps

# --- Create signals ---
def create_signals(instrument, signal_type, entries, sl, raw_tps, time_=None, source="Sanitized Signals",
                   link=None, telegram_message_id=None):
    time_ = time_ or datetime.utcnow().isoformat() + "Z"
    entries, tps = assign_tp_values(entries, raw_tps, signal_type)
    signals = []
    for i, entry in enumerate(entries):
        signal = {
            "instrument": instrument,
            "signal": signal_type,
            "entry": entry,
            "sl": sl,
            "tp": tps[i] if i < len(tps) else None,
            "time": time_,
            "source": source,
            "signalid": str(uuid.uuid4()),
        }
        if link:
            signal["link"] = link
        if telegram_message_id:
            signal["telegram_message_id"] = telegram_message_id
        signals.append(signal)
    return signals

def clean_llm_output(raw: str) -> str:
    if not raw:
        return raw
    cleaned = raw.strip()
    # Remove leading triple backticks and optional 'json' or similar, allowing newline after
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    print(cleaned)
    # Remove trailing triple backticks, possibly preceded by newline and whitespace
    cleaned = re.sub(r"\s*```", "", cleaned)
    return cleaned.strip()
# Prompt template for AI extraction with escaped braces
ai_prompt = """
Extract instrument name, signal type (BUY LIMIT, SELL LIMIT), entry points, stop loss (SL), and take profit levels (TP).

TP levels can be absolute prices (e.g. 1974, 1980) or values in pips (e.g. 30 pips, 50 pips).

1.  INSTRUMENT STANDARDIZATION: The value for "instrument" MUST be converted to the standardized format listed below, regardless of the input text (e.g., if the text says "Gold", output "XAUUSD").
    - Gold: XAUUSD
    - Silver: XAGUSD
    - Bitcoin: BTCUSD (or BTC/USD)
    - US30 / Dow Jones: US30
    - Nasdaq: US100
    - If a symbol is not recognized, output the symbol as-is (e.g., EURUSD).

2.  SIGNAL STANDARDIZATION: The value for "signal" MUST be standardized as one of the following official trading order types:
    - If the input is "Buy" or "Long", output: BUY LIMIT
    - If the input is "Sell" or "Short", output: SELL LIMIT
    - If the input already contains "LIMIT" or "STOP", output the full phrase (e.g., SELL LIMIT or BUY STOP).

Output JSON format example:

{{
  "instrument": "XAUUSD",
  "signal": "BUY LIMIT",
  "entries": [4006, 4005, 4004],
  "sl": 4001,
  "tps": ["30 pips", "50 pips", "80 pips", "Open"]
}}

If TP contains "Open", output four entries with the last entry having tp: null.
Only output valid JSON with these fields, no explanations or extra text.


{text}
"""

# Async call to AI
async def sanitize_with_ai(signal_text: str, timeout: int = 10) -> str:
    prompt = ai_prompt.format(text=signal_text)
    try:
        def blocking_call():
            return client.chat.completions.create(
                model=AI_MODEL,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.1,
            )
        response = await asyncio.wait_for(asyncio.to_thread(blocking_call), timeout=timeout)
        # Extract message content from response before returning
        return response.choices[0].message.content
    except asyncio.TimeoutError:
        logger.error("⏱️ AI sanitization timed out.")
        return ""
    except Exception as e:
        logger.error("❌ AI sanitization failed: %s", e, exc_info=True)
        return ""
# Postprocess AI output (basic example)
def postprocess_ai_output(ai_json_str: str, original_text: str, is_reply: bool) -> dict:
    try:
        data = json.loads(ai_json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ AI output invalid JSON: {e}")
        return {"signals": []}
    # You can add more validation/normalization here
    return data

# Main async sanitizer function
async def sanitize_signal(signal_text: str, is_reply: bool = False, timeout: int = 10,main_signalid: str = None) -> dict:
    print(is_reply,"is_reply",main_signalid,"main_signalid")
    if is_reply and main_signalid:  # Ensure we have the ID for manipulation
        # NOTE: If instrument is not in the manipulation message, you might need a lookup
        # here or rely on the processor to fetch the instrument from the batch.
        # For simplicity, we assume XAUUSD or fetch a default.
        manipulation_result = extract_manual_manipulation(
            signal_text,
            instrument="XAUUSD",  # Placeholder/default, or look up from original signal
            signalid=main_signalid
        )
        print(manipulation_result)
        print("SS")
        if manipulation_result:
            return {"signals": [manipulation_result]}
    # --- END NEW LOGIC ---

    ai_output = await sanitize_with_ai(signal_text, timeout=timeout)
    cleaned_output = clean_llm_output(ai_output)
    try:
        data = json.loads(cleaned_output)
    except json.JSONDecodeError as e:
        logger.warning(f"⚠️ AI output JSON decode error: {e}")
        return {"signals": []}

    if data.get("manipulation") is not None:
        # 💡 FIX: If 'manipulation' is present, return the raw data object directly.
        # This raw object contains the updated 'sl' or 'tp' and the 'manipulation' flag
        # required by signal_processor.py to trigger the merge logic.
        return {"signals": [data]}

    # Your existing postprocessing & signal creation logic below...
    if "signals" in data:
        return data

    instrument = data.get("instrument")
    signal_type = data.get("signal")
    entries = data.get("entries", [])
    sl = data.get("sl")
    tps = data.get("tps", [])

    if not instrument or not signal_type or not entries or sl is None or not tps:
        return {"signals": []}

    # 💡 IMPORTANT: Ensure the NEW signals have "manipulation": null for consistency
    signals = create_signals(instrument, signal_type, entries, sl, tps)
    for s in signals:
        s["manipulation"] = None  # Set default to null/None

    return {"signals": signals}

# Example main run
if __name__ == "__main__":
    test_message = """
    🟢 XAUUSD BUY LIMIT
    Entry: 1930 - 1932
    SL: 1920
    TP: 30 pips – 50 pips – 80 pips - Open
    """
    result = asyncio.run(sanitize_signal(test_message))
    print("Sanitized signals output:")
    print(json.dumps(result, indent=2))


def extract_manual_manipulation(text: str, instrument: str, signalid: str) -> dict | None:
    text_lower = text.lower().strip()

    # 1. Look for explicit commands
    if any(cmd in text_lower for cmd in
           ["close all", "cancel pending", "cancel", "close", "partial close", "close at entry"]):
        return {
            "instrument": instrument,
            "signalid": signalid,
            "manipulation": "close_all",
            "sl": None,
            "tp": None,
        }
    # 2. Look for SL movement
    sl_match = re.search(r'(move\s+sl\s+to|new\s+sl)[\s:\-]*([\d\.]+)', text_lower)
    if sl_match:
        new_sl = float(sl_match.group(2))
        return {
            "manipulation": "SL_CHANGE",
            "sl": new_sl,
            "tp": None,
        }

    # 3. Look for TP movement (Less common in replies, but good to include)
    tp_match = re.search(r'(move\s+tp\s+to|new\s+tp)[\s:\-]*([\d\.]+)', text_lower)
    if tp_match:
        new_tp = float(tp_match.group(2))
        return {
            "instrument": instrument,
            "signalid": signalid,
            "manipulation": "SL_CHANGE",
            "sl": new_sl,
            "tp": None,
        }

    # 4. Look for PIPS profit reports (e.g., +150 pips, might signal partial close)
    if any(cmd in text_lower for cmd in
           ["pips", "active", "hit entry"]):
        return {
            "instrument": instrument,
            "signalid": signalid,
            "manipulation": "cancel_pending",
        }

    # If it's a reply but contains no detectable manipulation command, return None
    # and let it fall through to the AI parser if necessary (e.g. for non-standard updates).
    return None