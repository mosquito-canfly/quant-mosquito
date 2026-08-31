"""Given a BULLISH/BEARISH/NEUTRAL signal, pick a slightly-OTM SPY option contract.

For now SIGNAL is hardcoded below for standalone testing; wiring it to
get_signal.py's real output is a follow-up step.
"""

import os
import sys
from datetime import date, timedelta

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOptionContractsRequest
from alpaca.trading.enums import ContractType
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest
from alpaca.data.enums import DataFeed

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

SYMBOL = "SPY"
SIGNAL = "BEARISH"  # hardcoded test value: BULLISH, BEARISH, or NEUTRAL


def check_options_enabled():
    """Options orders fail outright if the paper account isn't approved for
    options trading, so surface the account's approval level up front."""
    client = TradingClient(
        os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"), paper=True
    )
    account = client.get_account()
    level = account.options_trading_level
    print(f"Options trading level: {level} (0 = not enabled)")
    if not level or level == "0":
        print("This paper account is not approved for options trading.")
        sys.exit(1)
    return client


def fetch_current_price():
    """Latest traded price for SYMBOL."""
    client = StockHistoricalDataClient(
        os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    )
    request = StockLatestTradeRequest(symbol_or_symbols=SYMBOL, feed=DataFeed.IEX)
    trade = client.get_stock_latest_trade(request)[SYMBOL]
    return trade.price


def pick_contract(trading_client, signal, current_price):
    """Fetch SPY's option chain and pick one slightly out-of-the-money contract.

    - Expiration: earliest one 5-14 days out.
    - Strike: for a call, the lowest strike above current price; for a put,
      the highest strike below current price (i.e. just OTM either way).
    """
    contract_type = ContractType.CALL if signal == "BULLISH" else ContractType.PUT

    request = GetOptionContractsRequest(
        underlying_symbols=[SYMBOL],
        type=contract_type,
        expiration_date_gte=date.today() + timedelta(days=5),
        expiration_date_lte=date.today() + timedelta(days=14),
    )
    contracts = trading_client.get_option_contracts(request).option_contracts
    if not contracts:
        print("No contracts found in the 5-14 day expiration window.")
        sys.exit(1)

    # Earliest expiration available in that window.
    earliest_expiration = min(c.expiration_date for c in contracts)
    same_expiration = [c for c in contracts if c.expiration_date == earliest_expiration]

    if contract_type == ContractType.CALL:
        otm = [c for c in same_expiration if c.strike_price > current_price]
        best = min(otm, key=lambda c: c.strike_price) if otm else None
    else:
        otm = [c for c in same_expiration if c.strike_price < current_price]
        best = max(otm, key=lambda c: c.strike_price) if otm else None

    if best is None:
        print("No out-of-the-money strike found for that expiration.")
        sys.exit(1)
    return best


def select_option_contract(signal):
    """Pick a contract for the given signal. Returns the alpaca-py contract
    object (has .symbol, .strike_price, .expiration_date, .type) or None
    for NEUTRAL, where there's nothing to select."""
    if signal == "NEUTRAL":
        return None
    trading_client = check_options_enabled()
    price = fetch_current_price()
    return pick_contract(trading_client, signal, price)


if __name__ == "__main__":
    if SIGNAL == "NEUTRAL":
        print("No trade")
        sys.exit(0)

    trading_client = check_options_enabled()
    price = fetch_current_price()
    contract = pick_contract(trading_client, SIGNAL, price)

    print(f"\nCurrent {SYMBOL} price: {price}")
    print(f"Selected contract: {contract.symbol}")
    print(f"  Type:       {contract.type.value}")
    print(f"  Strike:     {contract.strike_price}")
    print(f"  Expiration: {contract.expiration_date}")
