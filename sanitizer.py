import os
import re
import json
import asyncio
import logging
import uuid
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

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


# ---------------- Manipulation Detection ---------------- #
import re


def detect_manipulation(text: str) -> dict:
    text_lower = text.lower()

    # Detect 'cancel_pending' related commands first to avoid 'close all' false positives
    if re.search(r"\b(cancel pending|cancel order|cancel trade|close a part|partial close)\b", text_lower):
        return {"cancel_pending": True}

    # Then detect 'close_all' phrases precisely
    if re.search(r"\bclose all\b", text_lower):
        return {"close_all": True}

    # 'close at entry' exact phrase
    if re.search(r"\bclose at entry\b", text_lower):
        return {"close_at_entry": True}

    # Move stop loss to specified price
    match = re.search(r"move sl to (\d+(\.\d+)?)", text_lower)
    if match:
        try:
            return {"move_sl": float(match.group(1))}
        except Exception:
            return {"move_sl": None}

    return {}
# ---------------- Prompt Template ---------------- #

test ="""
       Your role and rules:
   Extract valid BUY LIMIT and SELL LIMIT orders only. Discard or skip other order types.

   For any entry zone given (e.g. 3348–3350), split it evenly into exactly 3 unique entries strictly within the given range.

   Create only one signal per identified entry point.

   Normalize instrument names to remove slashes and spaces. For example, use "XAUUSD" not "XAU/USD".

   For SELL LIMIT: use the lowest entry in the range. For BUY LIMIT: use the highest entry.

   The stop loss (SL) and take profit (TP) must both be present, not "Open" or missing.

   Use the same SL for all entries derived from the same signal.

   TP and entry must obey:

   BUY LIMIT → SL < Entry < TP; assign the lowest TP to the highest entry, highest TP to the lowest entry, and midpoint TP to the middle entry.

   SELL LIMIT → TP < Entry < SL; assign the highest TP to the lowest entry, lowest TP to the highest entry, and midpoint TP to the middle entry.

   Determine pip size based on instrument digits (common: 5 or 3 digits → 0.0001 or 0.01 pips; 4 or 2 digits → 0.0001 or 0.01 pips).

   Output exactly 3 signals maximum for each valid signal.

   Do not create signals for any entries outside the given range or duplicate entries.

   Important:
   The output must be PLAIN JSON ONLY, with NO explanation, NO markdown, and NO comments.

   All values extracted and output must be based strictly on the input message. Under no circumstance should you add, invent, or guess additional signals, instruments, or values not found in the input.

   Enforce strict validation: if any required field is missing or invalid in the input, do not output a signal for it.

   If no valid signals can be parsed, output an empty signals array: {{ "signals": [] }}.

   Output format example (values are placeholders ONLY - DO NOT COPY):
   {{
   "signals": [
   {{
   "instrument": "XAUUSD",
   "signal": "BUY LIMIT",
   "entry": 3648,
   "sl": 3644,
   "tp": 3660,
   "time": "2025-09-10T13:40:28Z",
   "source": "Sanitized Signals"
   }},
   {{
   "instrument": "XAUUSD",
   "signal": "BUY LIMIT",
   "entry": 3649,
   "sl": 3644,
   "tp": 3665,
   "time": "2025-09-10T13:40:28Z",
   "source": "Sanitized Signals"
   }},
   {{
   "instrument": "XAUUSD",
   "signal": "BUY LIMIT",
   "entry": 3650,
   "sl": 3644,
   "tp": 3670,
   "time": "2025-09-10T13:40:28Z",
   "source": "Sanitized Signals"
   }}
   ]
   }}
   
   
   ### Input Message:
{text}
       """
# ---------------- AI sanitization ---------------- #
async def sanitize_with_ai(signal_text: str, timeout: int = 10) -> str:
    logger.info("🧼 Sanitizing signal: %s", signal_text[:60])
    prompt = test.format(text=signal_text)

    try:
        def blocking_call():
            return client.chat.completions.create(
                model=AI_MODEL,
                messages=[{"role": "system", "content": prompt}],
                temperature=0.1,
            )

        response = await asyncio.wait_for(asyncio.to_thread(blocking_call), timeout=timeout)
        return response.choices[0].message.content.strip()
    except asyncio.TimeoutError:
        logger.error("⏱️ AI sanitization timed out.")
        return '{"signals": []}'
    except Exception as e:
        logger.error("❌ AI sanitization failed: %s", e, exc_info=True)
        return '{"signals": []}'


# ---------------- Postprocess ---------------- #
def clean_llm_output(raw: str) -> str:
    if not raw:
        return raw
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"```$", "", cleaned.strip())
    return cleaned.strip()


def postprocess_ai_output(ai_json_str: str, original_text: str, is_reply: bool) -> dict:
    """
    Validate AI output JSON, attach manipulations (for replies),
    and create a dummy signal if it's a pure manipulation reply.
    """
    cleaned = clean_llm_output(ai_json_str)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("⚠️ AI output invalid JSON — returning empty signals.")
        data = {"signals": []}

    manipulations = detect_manipulation(original_text) if is_reply else {}

    # Apply manipulations onto AI-derived signals
    for signal in data.get("signals", []):
        if manipulations:
            for key, val in manipulations.items():
                signal["manipulation"] = key
                if key == "move_sl" and val:
                    signal["new_sl"] = val
                break
        if "source" not in signal:
            signal["source"] = "Sanitized Signals"
        if "time" not in signal:
            signal["time"] = datetime.utcnow().isoformat() + "Z"
        if "signalid" not in signal:
            signal["signalid"] = str(uuid.uuid4())

    # ✅ Special case: reply is ONLY a manipulation, AI returned no signals
    if is_reply and manipulations and not data.get("signals"):
        dummy = {
            "signalid": str(uuid.uuid4()),
            "source": "Sanitized Signals",
            "time": datetime.utcnow().isoformat() + "Z",
        }
        for key, val in manipulations.items():
            dummy["manipulation"] = key
            if key == "move_sl" and val:
                dummy["new_sl"] = val
            break
        data["signals"] = [dummy]

    return data

# ---------------- High-level ---------------- #
async def sanitize_signal(signal_text: str, is_reply: bool = False, timeout: int = 10) -> dict:
    ai_output = await sanitize_with_ai(signal_text, timeout=timeout)
    return postprocess_ai_output(ai_output, signal_text, is_reply)

# ---------------- Manual test ---------------- #
if __name__ == "__main__":
    test_message = """
    🟢 XAUUSD BUY LIMIT
    Entry: 1930 - 1932
    SL: 1920
    TP1: 1940
    TP2: 1950
    """

    result = asyncio.run(sanitize_signal(test_message, is_reply=False))
    print("Final sanitized JSON:", result)
