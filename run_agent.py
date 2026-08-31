"""Main entry point: signal -> contract selection -> sized market order -> log.

Run this to execute one trading cycle on the paper account.
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import OptionLatestQuoteRequest

from get_signal import get_signal
from options_selector import select_option_contract
from position_manager import (
    get_open_positions,
    check_exit_conditions,
    close_position,
    run_alpaca_cli,
)

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

LOG_FILE = "trade_log.jsonl"
HARD_CAP_USD = 2000  # never risk more than this on one trade, no matter what

# A more confident signal earns a bigger risk budget; a less confident one
# stays small in case the LLM's read on the market is wrong.
RISK_FRACTION_BY_CONFIDENCE = {
    "LOW": 0.005,
    "MEDIUM": 0.01,
    "HIGH": 0.015,
}


def fetch_ask_price(symbol):
    """Latest ask price for an option contract (what we'd pay to buy now)."""
    client = OptionHistoricalDataClient(
        os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    )
    request = OptionLatestQuoteRequest(symbol_or_symbols=symbol)
    return client.get_option_latest_quote(request)[symbol].ask_price


def calculate_contracts(cash, ask_price, confidence):
    """How many contracts to buy.

    Each option contract controls 100 shares, so its dollar cost is
    ask_price * 100. We budget a fraction of cash for the trade based on
    the LLM's confidence (see RISK_FRACTION_BY_CONFIDENCE), but never more
    than HARD_CAP_USD even if that fraction of cash would be bigger. If
    the budget can't afford even one contract, we still buy 1 as long as a
    single contract itself fits under the hard cap — otherwise we buy 0.
    """
    # Falls back to MEDIUM if the LLM ever replies with something outside
    # LOW/MEDIUM/HIGH — consistent with the rest of the agent never crashing
    # on a malformed model response.
    risk_fraction = RISK_FRACTION_BY_CONFIDENCE.get(confidence, RISK_FRACTION_BY_CONFIDENCE["MEDIUM"])
    cost_per_contract = ask_price * 100
    budget = min(cash * risk_fraction, HARD_CAP_USD)
    contracts = int(budget // cost_per_contract)
    if contracts == 0 and cost_per_contract <= HARD_CAP_USD:
        contracts = 1
    return contracts


def log_trade(record):
    """Print the record and append it as one JSON line to the trade log."""
    print(json.dumps(record, indent=2, default=str))
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def manage_open_positions():
    """Close any open position that's hit take-profit, stop-loss, or is
    about to expire, and log each close. Returns the symbols still open
    afterward, so the entry logic can avoid re-buying the same contract."""
    positions = get_open_positions()
    still_open = set()

    for position in positions:
        exit_reason = check_exit_conditions(position)
        if exit_reason is None:
            still_open.add(position.symbol)
            continue

        record = {
            "type": "exit",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": position.symbol,
            "exit_reason": exit_reason,
            "entry_price": float(position.avg_entry_price),
            "exit_price": float(position.current_price),
            "realized_pl": float(position.unrealized_pl),
            "order_id": None,
            "order_status": None,
        }
        try:
            order = close_position(position)
            record["order_id"] = order["id"]
            record["order_status"] = order["status"]
        except RuntimeError as e:
            # A close failing shouldn't crash the cycle — log it and leave
            # the position open so the next run tries again.
            record["order_status"] = f"error: {e}"
            still_open.add(position.symbol)

        log_trade(record)

    return still_open


def run():
    trading_client = TradingClient(
        os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"), paper=True
    )

    # Check market hours before spending anything on the LLM — there's no
    # point paying for a signal we can't act on.
    if not trading_client.get_clock().is_open:
        print("Market closed, skipping this cycle")
        log_trade({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "skipped",
            "reason": "market closed",
        })
        return

    open_symbols = manage_open_positions()

    signal, confidence, reason = get_signal()
    print(f"Signal: {signal} | Confidence: {confidence} | Reason: {reason}")

    if signal == "NEUTRAL":
        print("No trade this cycle")
        return

    contract = select_option_contract(signal)

    if contract.symbol in open_symbols:
        print(f"Already holding {contract.symbol}, skipping duplicate entry")
        return

    record = {
        "type": "trade_attempt",
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
        contracts = calculate_contracts(cash, ask_price, confidence)

        if contracts == 0:
            record["order_status"] = "skipped_too_expensive"
            log_trade(record)
            return

        # A fresh client-order-id per attempt lets a retried run be told
        # apart from a genuine duplicate order, per Alpaca's automation guidance.
        order = run_alpaca_cli([
            "order", "submit",
            "--symbol", contract.symbol,
            "--side", "buy",
            "--qty", str(contracts),
            "--type", "market",
            "--client-order-id", str(uuid.uuid4()),
        ])
        record["contracts_bought"] = contracts
        record["premium_paid"] = ask_price
        record["order_id"] = order["id"]
        record["order_status"] = order["status"]
    except RuntimeError as e:
        # Paper account quirks (contract not tradable, insufficient buying
        # power, etc.) shouldn't crash the agent — log and move on so the
        # next scheduled run can still try.
        record["order_status"] = f"error: {e}"

    log_trade(record)


if __name__ == "__main__":
    run()
