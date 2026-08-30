"""Quick sanity check that your Alpaca paper trading credentials work."""

import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

# Load ALPACA_API_KEY / ALPACA_SECRET_KEY from the .env file in this folder
load_dotenv()

api_key = os.getenv("ALPACA_API_KEY")
secret_key = os.getenv("ALPACA_SECRET_KEY")

try:
    # paper=True points this at Alpaca's paper trading endpoint, not live money
    client = TradingClient(api_key, secret_key, paper=True)
    account = client.get_account()

    print("SUCCESS: connected to Alpaca paper trading account")
    print(f"  Status:          {account.status}")
    print(f"  Buying power:    ${account.buying_power}")
    print(f"  Cash:            ${account.cash}")
    print(f"  Portfolio value: ${account.portfolio_value}")
except Exception as e:
    print("FAILED: could not connect to Alpaca")
    print(f"  Error: {e}")
