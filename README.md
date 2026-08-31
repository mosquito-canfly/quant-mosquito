# Quant Mosquito

An autonomous options trading agent built for an Alpaca paper trading hackathon. It reads real SPY technical indicators, asks a Featherless-hosted LLM for a bullish/bearish/neutral call grounded in those numbers, selects a slightly out-of-the-money option contract in that direction, sizes the position with a fixed risk budget, and places the order on an Alpaca paper account — all logged for review.

## Architecture

**Data → signal → contract selection → position sizing → order → logging**

- **`get_signal.py`** — pulls SPY's last 25 daily bars from Alpaca, computes a 5-day SMA, 20-day SMA, and 5-day momentum, then sends those numbers to the Featherless LLM and parses back a `SIGNAL` / `CONFIDENCE` / `REASON`.
- **`options_selector.py`** — given a signal, fetches SPY's current price and Alpaca's option chain, filters to calls (bullish) or puts (bearish), and picks the nearest out-of-the-money strike expiring 5–14 days out.
- **`position_manager.py`** — reads open positions and closes any that hit take-profit (+50%), stop-loss (-30%), or are within a day of expiring.
- **`run_agent.py`** — the entry point. Checks the market is open, closes any positions that need exiting, calls `get_signal()`, calls `select_option_contract()`, sizes the position (1% of account cash, capped at $2,000 per trade), submits the order, and appends a JSON record of the whole cycle to `trade_log.jsonl`.

Two Alpaca tools split the work: the **Python SDK** (`alpaca-py`) handles everything read-only — market data, indicators, account/clock checks, listing positions. The **Alpaca CLI** (`tools\alpaca.exe`) handles the two actions that actually move money: submitting the entry order and closing a position on exit, via `position_manager.run_alpaca_cli()`. Every order submission passes a fresh `--client-order-id` so a retried run can't double-submit.

## Setup

```bash
git clone <this repo>
cd quant-mosquito
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Then fill in `.env` with your real Alpaca and Featherless keys. `.env` is gitignored — never commit it.

Order execution also needs the [Alpaca CLI](https://github.com/alpacahq/cli/releases/latest) at `tools\alpaca.exe` (gitignored, download separately — grab the `windows_amd64` zip and extract `alpaca.exe` into `tools\`).

## Running

**Manually:**
```bash
python run_agent.py
```

**Scheduled:** `run_agent.bat` activates the venv, runs the agent, and logs output to `logs\`. Register it with Windows Task Scheduler to run hourly:

```bash
schtasks /create /tn "QuantMosquitoAgent" /tr "C:\Projects\quant-mosquito\run_agent.bat" /sc hourly /mo 1 /st 09:30 /f
```

It's safe to run outside market hours — `run_agent.py` checks Alpaca's clock first and logs a `skipped` cycle instead of trading.

## Dashboard

`dashboard.html` is a static, dependency-free page that reads `trade_log.jsonl` and renders each cycle as a card (signal, reasoning, contract, order status), newest first, with header counts for total/traded/skipped cycles.

Open it directly, or if your browser blocks local `fetch()` on `file://` URLs, serve the folder:

```bash
python -m http.server
```

then visit `http://localhost:8000/dashboard.html`.

## Risk management

- Each trade risks at most **1%** of current account cash.
- Regardless of the 1% calculation, no single trade risks more than a **$2,000 hard cap**.
- If 1% of cash can't afford even one contract but one contract still fits under the $2,000 cap, the agent buys a minimum of 1 contract; if even one contract exceeds the cap, it skips the trade.
