
import os

from openai import OpenAI
import asyncio

from dotenv import load_dotenv
from filters import should_ignore_message
load_dotenv()
OpenAI.api_key = os.getenv("OPENAI_API_KEY")

prompt_template = """
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


# Use GROQ endpoint
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

import asyncio

async def sanitize_with_ai(signal_text):
    print("🧼 Starting AI sanitization...")
    try:
        # Wrap blocking call in a function
        def blocking_call():
            return client.chat.completions.create(
                model="llama3-70b-8192",
                messages=[
                    {"role": "system", "content": prompt_template},
                    {"role": "user", "content": signal_text}
                ],
                temperature=0.1
            )

        # Add timeout here (10 seconds, adjust as needed)
        response = await asyncio.wait_for(asyncio.to_thread(blocking_call), timeout=10)

        print("✅ AI sanitization complete.")
        print(response.choices[0].message.content.strip())
        return response.choices[0].message.content.strip()

    except asyncio.TimeoutError:
        print("⏱️ AI sanitization timed out.")
        return signal_text  # Fallback

    except Exception as e:
        print("❌ AI sanitization failed:", e)
        return signal_text  # Fallback
