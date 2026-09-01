"""Check open option positions for exit conditions and close them when hit."""

import json
import os
import re
import subprocess
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass

load_dotenv()

TAKE_PROFIT_PCT = 0.50  # close once a position is up 50%
STOP_LOSS_PCT = -0.30  # close once a position is down 30%
TIME_EXIT_DAYS = 1  # close once expiration is this many days away or closer

ALPACA_CLI = Path(__file__).parent / "tools" / "alpaca.exe"

# Per `alpaca --help-all`: 0 success, 1 API error, 2 auth error.
_CLI_EXIT_CODES = {1: "API error", 2: "auth error"}


def run_alpaca_cli(args):
    """Run the Alpaca CLI for trading actions (order submission, position
    closes) and return its parsed JSON output.

    Market data/indicators still go through the alpaca-py SDK elsewhere in
    this project — this helper is only for the trading actions the CLI is
    used for. Credentials come from ALPACA_API_KEY/ALPACA_SECRET_KEY, which
    load_dotenv() has already put in the environment, and subprocess
    inherits the current environment by default, so the CLI picks them up
    with no extra wiring.
    """
    result = subprocess.run(
        [str(ALPACA_CLI), *args, "--quiet"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        meaning = _CLI_EXIT_CODES.get(result.returncode, "unknown error")
        raise RuntimeError(
            f"alpaca CLI exited {result.returncode} ({meaning}): "
            f"{result.stdout.strip() or result.stderr.strip()}"
        )
    return json.loads(result.stdout)


def verify_paper_endpoint():
    """Confirm the CLI actually resolves to Alpaca's paper endpoint before
    any order gets anywhere near it. `alpaca doctor` isn't a --quiet/JSON
    command like run_alpaca_cli's callers, and it can exit 1 for unrelated
    reasons (e.g. an update check), so this scans its plain-text output for
    the Trading: line itself rather than trusting the exit code alone."""
    result = subprocess.run([str(ALPACA_CLI), "doctor"], capture_output=True, text=True)
    return "https://paper-api.alpaca.markets" in result.stdout


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
    """Close this position via the CLI. Returns the parsed order dict
    (has "id" and "status", same as the SDK's Order object)."""
    return run_alpaca_cli(
        ["position", "close", "--symbol-or-asset-id", position.symbol]
    )
