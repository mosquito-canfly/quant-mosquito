"""Quick sanity check that Featherless AI (OpenAI-compatible API) works."""

import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

# Windows terminals default to cp1252, which chokes on stray unicode in
# model output; force utf-8 so printing the response never crashes.
sys.stdout.reconfigure(encoding="utf-8")

# Load FEATHERLESS_* vars from the .env file in this folder
load_dotenv()

# Featherless speaks the OpenAI API, so the official openai SDK works as-is
# once you point base_url at Featherless instead of OpenAI.
client = OpenAI(
    api_key=os.getenv("FEATHERLESS_API_KEY"),
    base_url=os.getenv("FEATHERLESS_BASE_URL"),
)

prompt = (
    "You are a stock market analyst. Based on this made-up scenario: "
    "SPY has risen 1.5% over the last 3 days on strong volume. Give a "
    "one-sentence bullish/bearish/neutral call and a one-sentence reason."
)

try:
    response = client.chat.completions.create(
        model=os.getenv("FEATHERLESS_MODEL"),
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,  # Featherless rejects requests with no token limit
    )
    print("SUCCESS: got a response from Featherless")
    print(response.choices[0].message.content)
except Exception as e:
    print("FAILED: could not get a response from Featherless")
    print(f"  Error: {e}")
