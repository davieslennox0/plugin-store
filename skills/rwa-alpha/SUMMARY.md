# rwa-alpha

## Overview

Real World Asset intelligence trading skill that detects macro events (Fed rate decisions, CPI, gold, SEC rulings) via news headlines and Polymarket probability confirmation, then trades 15 tokenized RWA tokens via OKX DEX with dual exit systems. Paper mode and PAUSED=True by default.

Core operations:

- Detect macro events from NewsNow headlines with 3-layer classification (keyword -> LLM confirm -> LLM discover)
- Confirm event probability via Polymarket prediction markets
- Auto-trade 15 RWA tokens across treasury, gold, yield, and governance categories
- Manage positions with dual exit: NAV premium/discount for asset-backed, TP/SL/trailing for governance
- Multi-chain execution on Ethereum and Solana via Agentic Wallet TEE signing

Tags: `rwa` `real-world-assets` `treasury` `gold` `macro` `trading` `ethereum` `solana`

## Prerequisites

- Python 3.8+ (stdlib only, no pip dependencies)
- OnchainOS CLI (`onchainos`) installed and authenticated (`onchainos wallet status`)
- OKX Agentic Wallet with funded balance on Ethereum or Solana
- Optional: `ANTHROPIC_API_KEY` env var for LLM headline classification

## Quick Start

1. **Start in paper mode**: Run `python3 rwa_alpha.py` from the skill directory. Dashboard opens at `http://localhost:3249`. Default mode is paper trading with PAUSED=True.

2. **Monitor signals**: The dashboard shows detected macro events, sentiment scores, active positions, and trade history. News polls every 120 seconds.

3. **Switch to live mode**: Edit `config.py` to set `MODE = "live"` and `PAUSED = False`. The bot will autonomously execute trades based on macro signals — ensure you understand the risk controls (daily limit, session stop, cooldown).

4. **Choose a strategy**: Three modes available in `config.py` — Yield Optimizer (asset-backed only), Macro Trader (balanced), Full Alpha (all strategies).
