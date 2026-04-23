# market-structure-analyzer

## Overview
Crypto market-structure research agent delivering institutional-grade analysis with 24+ indicators across derivatives, options (gamma wall, skew), on-chain (MVRV, smart money, DEX hot tokens), and macro sentiment. Features a live auto-refreshing dashboard with K-line candlestick charts, TA overlays (RSI, MACD, Bollinger Bands), and a 12-signal composite scoring engine (-100 to +100). Powered by OKX CeFi CLI + OnchainOS CLI, zero pip dependencies.

## Prerequisites
- Python 3.8+
- OKX CeFi CLI (`npm install -g @okx_ai/okx-trade-cli`) — no API key needed for read-only market data
- OnchainOS CLI (`onchainos`) at `~/.local/bin/onchainos` — for smart money signals and DEX hot tokens
- No pip dependencies required (Python stdlib only)

## Quick Start
```bash
# Start live dashboard (recommended)
cd skills/market-structure-analyzer
python3 msa_server.py
# → Open http://localhost:8420

# CLI-only mode (backward compatible)
python3 scripts/fetch_market_data.py BTC ETH SOL 2>/dev/null
```

The dashboard auto-refreshes: price every 3s, candles every 30s, structure indicators every 60s. Supports 10 tokens (BTC/ETH/SOL/BNB/DOGE/AVAX/ARB/XRP/LINK/PEPE) and 5 timeframes (5m/15m/1H/4H/1D).
