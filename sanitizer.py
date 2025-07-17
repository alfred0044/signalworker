
import os

from openai import OpenAI
import asyncio

from dotenv import load_dotenv
from filters import should_ignore_message
load_dotenv()
OpenAI.api_key = os.getenv("OPENAI_API_KEY")

prompt_template = """
You are a forex signal processor. Parse the following signal message and return individual signals with fixed entry points and target prices.

Instructions:
- If a zone is given (e.g., 3348–3350), evenly split 3 entries in the range.
- Match each entry to a TP so that one pair has the smallest delta, one the largest, and one in between.
- Keep SL and direction consistent.
- SL and TP must be present int the input. No inference allowed

Return the output in this format stricly and not additional text:
the rsult should statisfy .json requirements

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

Message:
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
