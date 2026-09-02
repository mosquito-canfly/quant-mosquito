"""Export Alpaca's portfolio history to JSON for the dashboard's equity chart.

Re-run this before opening dashboard.html to refresh the chart with the
latest equity data -- it's a static export, not live.
"""

import json
import os
from datetime import date, datetime, timedelta, timezone

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetPortfolioHistoryRequest

load_dotenv()

OUTPUT_FILE = "portfolio_history.json"
DAYS = 4


def fetch_portfolio_history():
    """Last DAYS calendar days of equity value at 15-minute resolution,
    fetched one day at a time.

    Alpaca's paper-account history can permanently corrupt a day's equity
    to roughly double its real value -- confirmed reproducible on this
    account for 2026-08-31 even querying that single day in isolation, so
    it's bad at the source, not an artifact of one request spanning
    multiple days. A single multi-day request also only returns one
    base_value for the whole window, which is stale for any day whose
    real starting equity had already moved (e.g. after real P&L) -- so
    each day is fetched and filtered against its own base_value instead.
    """
    client = TradingClient(
        os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"), paper=True
    )

    points = []
    for days_ago in range(DAYS - 1, -1, -1):
        day = date.today() - timedelta(days=days_ago)
        request = GetPortfolioHistoryRequest(period="1D", timeframe="15Min", date_end=day)
        history = client.get_portfolio_history(request)
        base_value = history.base_value

        day_points = [
            (ts, equity)
            for ts, equity in zip(history.timestamp, history.equity)
            if equity  # Alpaca pads with 0.0 for days before the account had a balance
            and abs(equity - base_value) <= 0.5 * base_value  # this account can't move ~2x on real trades
        ]
        print(f"  {day}: {len(day_points)} usable points" + ("" if day_points else " (skipped -- no data or corrupted)"))
        points.extend(day_points)

    return [
        {
            "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
            "equity_value": equity,
        }
        for ts, equity in points
    ]


if __name__ == "__main__":
    points = fetch_portfolio_history()
    with open(OUTPUT_FILE, "w") as f:
        json.dump(points, f, indent=2)

    print(f"Wrote {len(points)} points to {OUTPUT_FILE}")
    if points:
        print(f"  First: {points[0]['timestamp']}  ${points[0]['equity_value']:.2f}")
        print(f"  Last:  {points[-1]['timestamp']}  ${points[-1]['equity_value']:.2f}")
