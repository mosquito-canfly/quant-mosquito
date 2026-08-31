"""Main entry point: signal -> contract selection -> sized market order -> log.

Run this to execute one trading cycle on the paper account.
"""

import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import OptionLatestQuoteRequest
from alpaca.common.exceptions import APIError

from get_signal import get_signal
from options_selector import select_option_contract

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

LOG_FILE = "trade_log.jsonl"
RISK_FRACTION = 0.01  # risk 1% of cash per trade
HARD_CAP_USD = 2000  # never risk more than this on one trade, no matter what


def fetch_ask_price(symbol):
    """Latest ask price for an option contract (what we'd pay to buy now)."""
    client = OptionHistoricalDataClient(
        os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    )
    request = OptionLatestQuoteRequest(symbol_or_symbols=symbol)
    return client.get_option_latest_quote(request)[symbol].ask_price


def calculate_contracts(cash, ask_price):
    """How many contracts to buy.

    Each option contract controls 100 shares, so its dollar cost is
    ask_price * 100. We budget 1% of cash for the trade, but never more
    than HARD_CAP_USD even if 1% of cash would be bigger. If that budget
    can't afford even one contract, we still buy 1 as long as a single
    contract itself fits under the hard cap — otherwise we buy 0 (skip).
    """
    cost_per_contract = ask_price * 100
    budget = min(cash * RISK_FRACTION, HARD_CAP_USD)
    contracts = int(budget // cost_per_contract)
    if contracts == 0 and cost_per_contract <= HARD_CAP_USD:
        contracts = 1
    return contracts


def log_trade(record):
    """Print the record and append it as one JSON line to the trade log."""
    print(json.dumps(record, indent=2, default=str))
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def run():
    signal, confidence, reason = get_signal()
    print(f"Signal: {signal} | Confidence: {confidence} | Reason: {reason}")

    if signal == "NEUTRAL":
        print("No trade this cycle")
        return

    contract = select_option_contract(signal)
    trading_client = TradingClient(
        os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"), paper=True
    )

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signal": signal,
        "confidence": confidence,
        "reason": reason,
        "contract_symbol": contract.symbol,
        "strike": contract.strike_price,
        "expiration": contract.expiration_date,
        "contracts_bought": 0,
        "premium_paid": None,
        "order_id": None,
        "order_status": None,
    }

    try:
        ask_price = fetch_ask_price(contract.symbol)
        cash = float(trading_client.get_account().cash)
        contracts = calculate_contracts(cash, ask_price)

        if contracts == 0:
            record["order_status"] = "skipped_too_expensive"
            log_trade(record)
            return

        order = trading_client.submit_order(
            order_data=MarketOrderRequest(
                symbol=contract.symbol,
                qty=contracts,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )
        )
        record["contracts_bought"] = contracts
        record["premium_paid"] = ask_price
        record["order_id"] = str(order.id)
        record["order_status"] = order.status.value
    except APIError as e:
        # Paper account quirks (contract not tradable, insufficient buying
        # power, etc.) shouldn't crash the agent — log and move on so the
        # next scheduled run can still try.
        record["order_status"] = f"error: {e}"

    log_trade(record)


if __name__ == "__main__":
    run()
