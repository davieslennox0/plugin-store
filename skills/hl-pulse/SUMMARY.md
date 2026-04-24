# hl-pulse

## Overview

`hl-pulse` is a Hyperliquid intraday trading skill for liquid perp markets that offers either one clean setup in `pulse` mode or staged entries and exits in `ladder` mode while making stop-loss and max-loss explicit before execution.

The default first step is a dry-run preview: the skill scans, sizes, and presents the trade plan before any live order is allowed.

Core operations:

- Scan BTC, ETH, SOL, and other liquid Hyperliquid perp markets for one clean intraday setup
- Build a preview-first trade plan with entry zone, stop, first target, leverage, and max loss
- Deploy staged ladder entries and exits through `hyperliquid-plugin` with `--strategy-id hl-pulse`
- Manage open positions by reducing risk, taking partial profits, or flattening and standing down

Tags: `hyperliquid` `perps` `intraday` `execution` `risk-control`

## Prerequisites

- OKX Onchain OS is installed and the user's Agentic Wallet is connected
- `hyperliquid-plugin` version `^0.3.9` is available in the environment
- The wallet has USDC on Arbitrum for Hyperliquid collateral
- The user is comfortable with leveraged trading and explicit stop-losses

## Quick Start

1. Ask for one clean setup: `Find one hl-pulse setup on BTC or ETH with low risk.`
2. Review the preview, then confirm the approved trade: `Open the best hl-pulse trade with a clear stop and target.`
3. Switch to staged execution when needed: `Switch hl-pulse to ladder mode on ETH and stage entries conservatively.`
4. Ask the agent to manage, reduce, or fully close the trade as price evolves.
