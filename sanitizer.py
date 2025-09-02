import os
import logging
import asyncio
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
OpenAI.api_key = os.getenv("OPENAI_API_KEY")  # Only needed for the OpenAI endpoint

PROMPT_TEMPLATE = """
You are a forex signal processor. Parse the following signal message and return structured individual trade signals in JSON format.

Your role:
Extract valid BUY LIMIT and SELL LIMIT orders, including correct entry, stop loss (SL), and take profit (TP). Ensure SL and TP rules are strictly followed with regard to price direction and pip logic.

Instructions:

### Entry Processing:
- If an entry zone is given (e.g. 3348–3350), split it evenly into 3 entries between those bounds.
- Only create signals with type "BUY LIMIT" or "SELL LIMIT" — discard or skip market/stop orders.
- Ensure instrument name does **not** include slashes or spaces, e.g. use `"XAUUSD"`, not `"XAU/USD"`.

### SL and TP Requirements:
- Discard signals where either SL or TP is missing or labeled as "Open".
- Don't infer missing values; process only when SL and at least one TP are explicitly present.
- Use the same SL across all derived entries (if SL is shared across the range).

### Buy/Sell Logic Matching:

#### For **BUY LIMIT** orders:
- All **TPs must be greater than** both the entry and the SL (i.e. entry < TP, SL < entry < TP).
- Assign **the lowest TP** to the **highest entry**, and the **highest TP** to the **lowest entry** (maximize reward-to-risk).
- If TPs are expressed in PIPS (e.g. TP1 = 50 PIPS), calculate absolute TP levels by *adding* PIP values to entry.

#### For **SELL LIMIT** orders:
- All **TPs must be less than** both the entry and the SL (i.e. TP < entry, TP < SL < entry).
- Assign **the highest TP** to the **lowest entry**, and the **lowest TP** to the **highest entry**.
- If TPs are expressed in PIPS (e.g. TP1 = 50 PIPS), calculate absolute TP levels by *subtracting* PIP values from the entry.

### Instrument-Specific Pip Calculation:
- Use common definitions for pip sizes based on instrument:
  - If the instrument has 5 or 3 digits (like 1.12345 or 123.456), **1 pip = 0.0001** or **0.01**
  - If it has 4 or 2 digits (like 1.1234 or 123.45), **1 pip = 0.0001** or **0.01**

### Output Requirements:
- Return a valid `.json` object — no explanations, prefixes, or extra descriptions.
- Output all matched signals as array items under `"signals"` key.
- Each signal must include:
  - `instrument`
  - `signal` (only `"BUY LIMIT"` or `"SELL LIMIT"`)
  - `entry`
  - `sl`
  - `tp` (single TP target per signal)
  - `time` (use ISO format like: `"2025-07-22T13:30:00Z"`)
  - `source` (can default to "Sanitized Signals")

### Example Output Format:
{
  "signals": [
    {
      "instrument": "XAUUSD",
      "signal": "SELL LIMIT",
      "entry": 2363.33,
      "sl": 2370.56,
      "tp": 2361.38,
      "time": "2025-07-14T15:00:00Z",
      "source": "GoldChannel"
    },
    {
      "instrument": "XAUUSD",
      "signal": "SELL LIMIT",
      "entry": 2365.36,
      "sl": 2370.56,
      "tp": 2360.38,
      "time": "2025-07-14T15:00:00Z",
      "source": "GoldChannel"
    }
  ]
}

### Input Message:
{text}
"""
  # Use a docstring or an external template file for readability

# Use true async client if available. Fall back to thread method if not.
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

logger = logging.getLogger("signalworker.sanitizer")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
    logger.addHandler(handler)

async def sanitize_with_ai(signal_text: str, timeout: int = 10) -> str:
    """
    Sends signal_text to the language model endpoint using the defined prompt template.
    Returns the cleaned JSON string or the original text on timeout/failure.
    """
    logger.info("🧼 Starting AI sanitization for signal: %s", signal_text[:60])
    prompt = PROMPT_TEMPLATE.replace("{text}", signal_text)
    try:
        def blocking_call():
            return client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": signal_text}
                ],
                temperature=0.1
            )
        response = await asyncio.wait_for(asyncio.to_thread(blocking_call), timeout=timeout)
        cleaned = response.choices[0].message.content.strip()
        logger.info("✅ AI sanitization complete. Response: %s...", cleaned[:60])

        # Optional: Check if it's valid JSON, else log warning
        import json
        try:
            json.loads(cleaned)
        except Exception:
            logger.warning("LLM output is not valid JSON. Returning raw output.")
        return cleaned

    except asyncio.TimeoutError:
        logger.error("⏱️ AI sanitization timed out after %ss.", timeout)
        return signal_text

    except Exception as e:
        logger.error("❌ AI sanitization failed: %s", e, exc_info=True)
        return signal_text
