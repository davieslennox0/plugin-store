# ligoudan-btc-hype — BTC 囤币 + HYPE 理财

## Overview

A long-only BTC perpetual grid strategy on Hyperliquid that trades the $70k–$90k range
with 8x leverage and recycles realized grid profits into 2x long HYPE positions with
built-in stop-loss and take-profit protection.

> BTC 在 70k-90k 布 10 档 8x 网格多单，止盈利润累积到 $50 就下一笔 2x HYPE 长单（自动挂
> -15% SL / +30% TP）。一个策略同时吃 BTC 区间波动 + 慢速堆 HYPE 长期仓位。

Core operations:
- `init` — bootstrap a 10-cell grid between $70k and $90k with 8x leverage
- `status` — read current grid fills, unrealized PnL, realized PnL, HYPE compound PnL
- `rebalance` — re-arm filled cells and place take-profit sells
- `compound` — reinvest realized profit into HYPE 2x longs with SL/TP
- `shutdown` — cancel all grid orders and optionally close all positions

Tags: hyperliquid, grid, btc, hype, compound, perp, strategy

## Prerequisites

- **Region/IP:** Hyperliquid must be accessible from the user's jurisdiction.
- **Chains:** Hyperliquid L1 (perp), Arbitrum (USDC bridge).
- **Tokens:** USDC collateral on the Hyperliquid perp account.
- **Required plugins:** `hyperliquid-plugin` (^0.3.9) installed via
  `npx skills add okx/plugin-store --skill hyperliquid-plugin`.
- **Required capital:** At least $30,000 USDC on the Hyperliquid perp account is the
  recommended minimum to keep the aggregate liquidation price below $60,500 (about
  $9,500 below the grid floor).

## Quick Start

1. Install the dependent plugin:
   ```
   npx skills add okx/plugin-store --skill hyperliquid-plugin
   ```
2. Install this strategy skill:
   ```
   npx skills add okx/plugin-store --skill ligoudan-btc-hype
   ```
3. Ensure USDC collateral is on the Hyperliquid perp account. If it is on Arbitrum,
   bridge it first with `onchainos hyperliquid deposit --amount <usdc> --confirm`.
4. Ask the assistant to run the strategy:
   > "Init the BTC grid at 70k–90k with the default parameters."
   The assistant will run every pre-flight check, show a dry-run preview of all 10
   grid orders, and require explicit approval before submitting.
5. Call `status` whenever you want a read-only snapshot; call `rebalance` periodically
   (or on demand) to re-arm filled cells and trigger compounding when realized profit
   crosses the $50 threshold.
