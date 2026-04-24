# BTC Adaptive Hyperliquid

## Overview

BTC Adaptive Hyperliquid is an advanced Strategy Skill that generates BTC perpetual futures action plans for execution through the Hyperliquid Plugin. It combines adaptive breakout, failed-breakout fade, ATR volatility, RSI, funding-rate filters, and real-time position risk management.

The included Python script is plan-only and does not execute trades. Live trading must be performed through the Hyperliquid Plugin / Onchain OS Agentic Wallet flow after explicit user confirmation.

## Prerequisites

- Hyperliquid Plugin installed from Plugin Store.
- Python 3.8+ for the local decision script.
- Fresh account and BTC-PERP position data obtained through the Hyperliquid Plugin.
- Optional public market access to `fapi.binance.com` for BTCUSDT mark price, funding, and 1h candles.

## Quick Start

Validate configuration:

```bash
python3 scripts/btc_adaptive_hyperliquid.py validate-config --config config/default.json
```

Run a deterministic dry-run demo:

```bash
python3 scripts/btc_adaptive_hyperliquid.py demo --config config/default.json --output text
```

Generate a dry-run plan using sample account/position data and public market data:

```bash
python3 scripts/btc_adaptive_hyperliquid.py plan \
  --config config/default.json \
  --account-json @examples/account.sample.json \
  --position-json @examples/position-flat.sample.json \
  --fetch-market \
  --dry-run
```

## Safety Model

- Dry-run default.
- Configurable stop-loss and max-loss limits.
- Configurable per-trade and per-session caps.
- No wallet signing code and no private-key handling.
- Execution must route through the Hyperliquid Plugin.
