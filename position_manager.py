"""Check open option positions for exit conditions and close them when hit."""

import os
import re
from datetime import date, datetime

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass

load_dotenv()

TAKE_PROFIT_PCT = 0.50  # close once a position is up 50%
STOP_LOSS_PCT = -0.30  # close once a position is down 30%
TIME_EXIT_DAYS = 1  # close once expiration is this many days away or closer

# OCC option symbols end in a fixed 15-char suffix: 6-digit date (YYMMDD),
# 1-char C/P, 8-digit strike (e.g. "SPY260908P00769000" -> "260908").
_OCC_DATE_RE = re.compile(r"(\d{6})[CP]\d{8}$")


def _expiration_from_symbol(symbol):
    """Pull the expiration date out of an OCC option symbol."""
    match = _OCC_DATE_RE.search(symbol)
    return datetime.strptime(match.group(1), "%y%m%d").date()


def get_open_positions():
    """All currently open option positions on the paper account."""
    client = TradingClient(
        os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"), paper=True
    )
    positions = client.get_all_positions()
    return [p for p in positions if p.asset_class == AssetClass.US_OPTION]


def check_exit_conditions(position):
    """Decide whether to exit a position. Checked in this order:

    1. TAKE_PROFIT: Alpaca already computes unrealized_plpc (gain/loss as a
       fraction of cost basis) for us, so we just threshold it — no need to
       recompute from entry/current price ourselves.
    2. STOP_LOSS: same field, other direction.
    3. TIME_EXIT: options lose value fast right before expiration and can
       become hard to exit, so bail out a day ahead rather than hold to the wire.
    4. Otherwise hold.
    """
    plpc = float(position.unrealized_plpc)
    if plpc >= TAKE_PROFIT_PCT:
        return "TAKE_PROFIT"
    if plpc <= STOP_LOSS_PCT:
        return "STOP_LOSS"
    if (_expiration_from_symbol(position.symbol) - date.today()).days <= TIME_EXIT_DAYS:
        return "TIME_EXIT"
    return None


def close_position(position):
    """Submit a market order to close this position."""
    client = TradingClient(
        os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"), paper=True
    )
    return client.close_position(position.symbol)
