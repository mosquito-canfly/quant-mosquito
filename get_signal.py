"""Fetch SPY daily bars, compute simple indicators, and ask the LLM for a signal."""

import os
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import StockBarsRequest, NewsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from openai import OpenAI

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

SYMBOL = "SPY"


def fetch_closes():
    """Return the last 25 daily closing prices for SYMBOL, oldest first."""
    client = StockHistoricalDataClient(
        os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    )
    # Free/paper accounts only get the IEX feed, and the API needs an explicit
    # start date (a bare "limit" returns nothing) — ask for 60 calendar days
    # so 25 trading days are guaranteed to be in range, then trim to the last 25.
    request = StockBarsRequest(
        symbol_or_symbols=SYMBOL,
        timeframe=TimeFrame.Day,
        start=datetime.now() - timedelta(days=60),
        feed=DataFeed.IEX,
    )
    bars = client.get_stock_bars(request).df
    return bars["close"].tail(25).tolist()


def fetch_recent_news(symbol="SPY", limit=5):
    """Most recent headlines for symbol from the last 3 days, newest first.
    Just headlines (not full articles) to keep the prompt small. Returns
    an empty list if there's no news, rather than erroring out."""
    client = NewsClient(os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"))
    request = NewsRequest(symbols=symbol, start=datetime.now() - timedelta(days=3), limit=limit)
    articles = client.get_news(request).data.get("news", [])
    return [a.headline for a in articles]


def compute_indicators(closes):
    """SMA5, SMA20, and 5-day momentum (%) from a list of closes, oldest first."""
    sma5 = sum(closes[-5:]) / 5
    sma20 = sum(closes[-20:]) / 20
    momentum_pct = (closes[-1] - closes[-6]) / closes[-6] * 100
    return sma5, sma20, momentum_pct


def ask_llm(sma5, sma20, momentum_pct, headlines=None):
    """Send the indicators (and any recent headlines) to Featherless and
    return the raw text response."""
    client = OpenAI(
        api_key=os.getenv("FEATHERLESS_API_KEY"),
        base_url=os.getenv("FEATHERLESS_BASE_URL"),
    )
    # Only mention news at all if we actually found some — an empty
    # "Recent headlines:" section would just be noise in the prompt.
    news_section = ""
    if headlines:
        bullets = "\n".join(f"- {h}" for h in headlines)
        news_section = f"Recent headlines:\n{bullets}\n\n"

    prompt = (
        f"You are a stock market analyst looking at {SYMBOL}.\n"
        f"5-day SMA: {sma5:.2f}\n"
        f"20-day SMA: {sma20:.2f}\n"
        f"5-day momentum: {momentum_pct:.2f}%\n\n"
        f"{news_section}"
        "Respond in exactly this format:\n"
        "SIGNAL: [BULLISH/BEARISH/NEUTRAL]\n"
        "CONFIDENCE: [LOW/MEDIUM/HIGH]\n"
        "REASON: [one sentence]"
    )
    response = client.chat.completions.create(
        model=os.getenv("FEATHERLESS_MODEL"),
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
    )
    return response.choices[0].message.content


def parse_signal(text):
    """Pull SIGNAL/CONFIDENCE/REASON out of the LLM's plain-text reply."""
    result = {"SIGNAL": "?", "CONFIDENCE": "?", "REASON": "?"}
    for line in text.splitlines():
        for key in result:
            if line.strip().upper().startswith(key + ":"):
                result[key] = line.split(":", 1)[1].strip()
    return result


def get_signal():
    """Run the full pipeline and return (signal, confidence, reason)."""
    closes = fetch_closes()
    sma5, sma20, momentum_pct = compute_indicators(closes)
    headlines = fetch_recent_news(SYMBOL)
    raw_reply = ask_llm(sma5, sma20, momentum_pct, headlines)
    parsed = parse_signal(raw_reply)
    return parsed["SIGNAL"], parsed["CONFIDENCE"], parsed["REASON"]


if __name__ == "__main__":
    closes = fetch_closes()
    sma5, sma20, momentum_pct = compute_indicators(closes)

    print(f"{SYMBOL} indicators (from {len(closes)} daily bars)")
    print(f"  SMA5:            {sma5:.2f}")
    print(f"  SMA20:           {sma20:.2f}")
    print(f"  5-day momentum:  {momentum_pct:.2f}%")

    headlines = fetch_recent_news(SYMBOL)
    print(f"\nRecent headlines ({len(headlines)} found)")
    if headlines:
        for h in headlines:
            print(f"  - {h}")
    else:
        print("  none found")

    raw_reply = ask_llm(sma5, sma20, momentum_pct, headlines)
    signal = parse_signal(raw_reply)

    print("\nLLM signal")
    print(f"  Signal:     {signal['SIGNAL']}")
    print(f"  Confidence: {signal['CONFIDENCE']}")
    print(f"  Reason:     {signal['REASON']}")
