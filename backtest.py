"""Backtest the SMA5/SMA20 cross signal against 90 days of SPY history.

IMPORTANT: this only backtests the technical (SMA cross) component of the
signal logic -- it does NOT replicate the live agent, which also feeds the
LLM real news headlines and lets it reason freely. Backtesting the LLM+news
layer isn't practical here (no way to replay historical news context into
a live model call for each past day). This validates the technical
foundation the signal is built on, not the full pipeline's real performance.
"""

import csv
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed

from get_signal import compute_indicators

load_dotenv()

SYMBOL = "SPY"
LOOKAHEAD_DAYS = 5  # how far ahead we check whether the call was right
RESULTS_FILE = "backtest_results.csv"
DISCLAIMER = (
    "Note: hypothetical backtest results do not guarantee future performance; "
    "this validates directional signal accuracy only, not simulated P&L."
)


def fetch_history():
    """(date, close) pairs for the last 90 daily bars, oldest first."""
    client = StockHistoricalDataClient(
        os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    )
    request = StockBarsRequest(
        symbol_or_symbols=SYMBOL,
        timeframe=TimeFrame.Day,
        start=datetime.now() - timedelta(days=180),  # generous window to guarantee 90 trading days
        feed=DataFeed.IEX,
    )
    bars = client.get_stock_bars(request).df.tail(90).reset_index()
    dates = bars["timestamp"].dt.strftime("%Y-%m-%d").tolist()
    closes = bars["close"].tolist()
    return list(zip(dates, closes))


def run_backtest(history):
    """One row per day with enough history behind it (SMA20) and enough
    days ahead of it (5-day lookahead) to score. Reuses get_signal's own
    compute_indicators() so the backtest mirrors the live signal logic
    exactly, not a reimplementation of it."""
    closes = [c for _, c in history]
    rows = []

    for i in range(20, len(history) - LOOKAHEAD_DAYS):
        sma5, sma20, _momentum = compute_indicators(closes[: i + 1])
        signal = "BULLISH" if sma5 > sma20 else "BEARISH"

        price_now = closes[i]
        price_later = closes[i + LOOKAHEAD_DAYS]
        actual_direction = "UP" if price_later > price_now else "DOWN"
        correct = (signal == "BULLISH" and actual_direction == "UP") or \
                  (signal == "BEARISH" and actual_direction == "DOWN")

        rows.append({
            "date": history[i][0],
            "sma5": round(sma5, 2),
            "sma20": round(sma20, 2),
            "signal": signal,
            "price_5d_later": price_later,
            "actual_direction": actual_direction,
            "correct": correct,
        })

    return rows


def summarize(rows):
    total = len(rows)
    bullish = [r for r in rows if r["signal"] == "BULLISH"]
    bearish = [r for r in rows if r["signal"] == "BEARISH"]
    accuracy = lambda subset: sum(r["correct"] for r in subset) / len(subset) * 100 if subset else 0.0

    print(f"{SYMBOL} SMA-cross backtest — {total} signals over the last {total + LOOKAHEAD_DAYS + 20} trading days\n")
    print(f"{'':14}{'count':>8}{'% of total':>12}{'accuracy':>12}")
    print(f"{'BULLISH':14}{len(bullish):>8}{len(bullish) / total * 100:>11.1f}%{accuracy(bullish):>11.1f}%")
    print(f"{'BEARISH':14}{len(bearish):>8}{len(bearish) / total * 100:>11.1f}%{accuracy(bearish):>11.1f}%")
    print(f"{'OVERALL':14}{total:>8}{100.0:>11.1f}%{accuracy(rows):>11.1f}%")
    print(f"\n{DISCLAIMER}")


def write_csv(rows):
    with open(RESULTS_FILE, "w", newline="") as f:
        f.write(f"# {DISCLAIMER}\n")
        writer = csv.DictWriter(f, fieldnames=[
            "date", "sma5", "sma20", "signal", "price_5d_later", "actual_direction", "correct"
        ])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    history = fetch_history()
    rows = run_backtest(history)
    summarize(rows)
    write_csv(rows)
    print(f"\nWrote {len(rows)} rows to {RESULTS_FILE}")
