# Polymarket Arbitrage Bot

This repository contains a minimal Python bot for spotting and trading Polymarket arbitrage opportunities where the summed price of **YES** and **NO** shares is below 1.0. The bot can notify a Telegram chat, wait for manual confirmation (or auto-trade), execute trades via the Polymarket CLOB client, and report results.

## Features
- Scan Polymarket markets for YES/NO price sums under a configurable threshold.
- Send Telegram alerts with actionable inline buttons for manual confirmation.
- Optional automatic execution when a high-quality opportunity is found.
- Wallet bootstrapper for quickly generating a new private key and address.
- Trade executor built on the official [`py_clob_client`](https://github.com/Polymarket/py-clob-client) SDK with signed CLOB orders.
- Balance, fee, and gas-aware risk checks plus lightweight position/settlement tracking.

## Configuration
Set the following environment variables (a `.env` file is recommended):

- `POLYMARKET_API` – Market data endpoint. Defaults to `https://gamma-api.polymarket.com`.
- `AUTO_TRADE` – Set to `true` to execute automatically; otherwise the bot waits for a Telegram confirmation.
- `ARBITRAGE_THRESHOLD` – Price sum threshold; defaults to `0.99` to account for fees.
- `ARBITRAGE_STEP` – Adjustment increment for the threshold when using the Telegram control buttons (default `0.01`).
- `TELEGRAM_TOKEN` – Bot token from BotFather.
- `TELEGRAM_CHAT_ID` – Chat or channel ID to receive alerts.
- `PRIVATE_KEY` – Polygon private key used for trading.
- `CHAIN_ID` – Target chain ID (e.g., `137` for Polygon mainnet, `80002` for Amoy testnet).

Optional parameters for risk controls and settlement tracking:

- `QUOTE_SIZE` – Notional size per leg (defaults to `20` USDC).
- `QUOTE_STEP` – Size increment/decrement when adjusting the notional via Telegram buttons (default `5` USDC).
- `TAKER_FEE_BPS` – Expected taker fee in basis points; used to pre-compute costs.
- `GAS_FEE_USD` – Estimated gas cost (USD) to include in balance checks.
- `MIN_BALANCE_BUFFER` – Extra USDC cushion required beyond the trade cost.
- `AUTO_SETTLE` – When `true`, automatically mark tracked positions as settled when external hooks call `mark_settled`.

## Usage
Install dependencies and start the scanner:

```bash
pip install -r requirements.txt
python main.py
```

The bot will:
1. Fetch active markets, focusing on binary (YES/NO) contracts.
2. Detect opportunities where the best YES ask plus the best NO ask is below the threshold.
3. Send a Telegram alert with an Execute/Ignore inline keyboard.
4. Persist a bottom control keyboard in Telegram so you can raise/lower the arbitrage threshold, increase/decrease the order size, or request the current status without leaving the chat.
5. On confirmation (or when `AUTO_TRADE=true`), place balanced buy orders for both legs with fee/gas-aware cost checks and report the result.

## Notes
- The trading and wallet helpers rely on the Polymarket CLOB client and expect funded wallets.
- Network access is required to fetch markets and deliver Telegram messages.
- For testing without trading, omit `PRIVATE_KEY` or set `AUTO_TRADE=false`; the bot will still send alerts but skip order placement.
