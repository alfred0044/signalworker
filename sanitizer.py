
import os

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
OpenAI.api_key = os.getenv("OPENAI_API_KEY")

prompt_template = """
You are a forex signal processor. Parse the following signal message and return individual signals with fixed entry points and target prices.

Instructions:
- If a zone is given (e.g., 3348–3350), evenly split 3 entries in the range.
- Match each entry to a TP so that one pair has the smallest delta, one the largest, and one in between.
- Keep SL and direction consistent.

Return the output in this format and not additional text:

* Instrument: XAUUSD
* Signal: BUY Limit
* Entry: 3348
* SL: 3344
* TP: 3353

* Instrument: XAUUSD
* Signal: BUY Limit
* Entry: 3349
* SL: 3344
* TP: 3356

* Instrument: XAUUSD
* Signal: BUY Limit
* Entry: 3350
* SL: 3344
* TP: 3363

Message:
{text}
"""


# Use GROQ endpoint
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

async def sanitize_with_ai(signal_text):
    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {
                    "role": "system",
                    "content": prompt_template
                },
                {
                    "role": "user",
                    "content": signal_text
                }
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("❌ AI sanitization failed:", e)
        return signal_text  # fallback