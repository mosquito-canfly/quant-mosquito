"""Export Alpaca's portfolio history to JSON for the dashboard's equity chart.

Re-run this before opening dashboard.html to refresh the chart with the
latest equity data -- it's a static export, not live.
"""

import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetPortfolioHistoryRequest

load_dotenv()

OUTPUT_FILE = "portfolio_history.json"


def fetch_portfolio_history():
    """Last 2 days of equity value at 15-minute resolution -- fine enough
    to show intraday moves from actual trades, not just daily closes."""
    client = TradingClient(
        os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"), paper=True
    )
    request = GetPortfolioHistoryRequest(period="2D", timeframe="15Min")
    history = client.get_portfolio_history(request)

    return [
        {
            "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
            "equity_value": equity,
        }
        for ts, equity in zip(history.timestamp, history.equity)
        if equity  # Alpaca pads with 0.0 for days before the account had a balance
    ]


if __name__ == "__main__":
    points = fetch_portfolio_history()
    with open(OUTPUT_FILE, "w") as f:
        json.dump(points, f, indent=2)

    print(f"Wrote {len(points)} points to {OUTPUT_FILE}")
    if points:
        print(f"  First: {points[0]['timestamp']}  ${points[0]['equity_value']:.2f}")
        print(f"  Last:  {points[-1]['timestamp']}  ${points[-1]['equity_value']:.2f}")
