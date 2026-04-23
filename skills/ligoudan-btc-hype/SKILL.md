---
name: ligoudan-btc-hype
description: BTC 囤币 + HYPE 理财 — Hyperliquid 70k-90k 8x 永续网格做多，已实现利润复投 2x HYPE 长单（带 SL/TP 保护）。
version: 0.1.0
author: ligoudan
tags:
  - hyperliquid
  - grid
  - btc
  - hype
  - compound
---

# ligoudan-btc-hype — BTC 囤币 + HYPE 理财

## Overview

A long-only BTC perpetual grid strategy on Hyperliquid that trades the $70k–$90k range
with 8x leverage, and recycles realized grid profits into 2x long HYPE positions with
built-in stop-loss and take-profit protection.

中文说明：BTC 在 70k-90k 区间布 10 档网格多单（8x 杠杆），每一档止盈后把利润累积起来，
满 $50 就自动下一笔 2x HYPE 长单，并立即挂 -15% 止损 / +30% 止盈保护。一边吃 BTC 区间
波动，一边慢慢堆 HYPE 仓位。

The strategy delegates every write operation to `hyperliquid-plugin` with
`--strategy-id ligoudan-btc-hype` for attribution. It does not connect to chains
or wallets directly.

Core operations: initialize the grid, read status, rebalance after fills, compound
realized profit into HYPE, and shut down cleanly.

## Pre-flight Checks

Before any write operation, verify all of the following. Abort with a clear message if
any check fails.

1. **Dependent plugin installed**
   Confirm `hyperliquid-plugin` is available:
   ```bash
   onchainos hyperliquid --help
   ```
   If missing:
   ```bash
   npx skills add okx/plugin-store --skill hyperliquid-plugin
   ```

2. **Wallet registered with Hyperliquid**
   ```bash
   onchainos hyperliquid register --dry-run
   ```
   The onchainos signing address must be approved on Hyperliquid.

3. **Capital available on the Hyperliquid perp account**
   ```bash
   onchainos hyperliquid address --all
   ```
   Required USDC on the perp account ≥ configured `capital_usdc` (default $30,000).
   If funds are on Arbitrum, prompt the user to run:
   ```bash
   onchainos hyperliquid deposit --amount <usdc> --confirm
   ```

4. **BTC mid price is inside the grid range**
   ```bash
   onchainos hyperliquid prices --coin BTC
   ```
   Price must satisfy `70,000 ≤ mid ≤ 90,000`. If outside, refuse to init.

5. **State file location is writable**
   Default: `$HOME/.local/share/ligoudan-btc-hype/state.json`
   The state file tracks realized profit accumulator, cell status, compound history.

## Configuration

Default parameters (documented in SUMMARY.md, overridable by the user at init time):

| Parameter | Default | Notes |
| --- | --- | --- |
| `range_low` | 70000 | Grid floor in USD |
| `range_high` | 90000 | Grid ceiling in USD |
| `step` | 2000 | USD between adjacent grid levels |
| `leverage` | 8 | BTC perp leverage (cross margin) |
| `capital_usdc` | 30000 | Total USDC committed to the grid |
| `size_btc` | 0.0015 | BTC contracts per grid cell |
| `hype_compound_threshold_usdc` | 50 | Realized profit required to trigger one HYPE buy |
| `hype_leverage` | 2 | Leverage on compound HYPE longs |
| `hype_sl_pct` | -0.15 | Stop-loss % on each HYPE compound position |
| `hype_tp_pct` | 0.30 | Take-profit % on each HYPE compound position |
| `max_hype_compound_notional_usdc` | 5000 | Hard cap on total HYPE exposure from compounding |

The liquidation price of the aggregate BTC grid is approximately
`P_liq ≈ 80,612 − capital_usdc / (9.8 × size_btc)`. With the defaults,
`P_liq ≈ $60,572`, i.e. ~10k below the grid floor.

## Commands

All write operations MUST pass `--strategy-id ligoudan-btc-hype` and `--confirm`.
All read operations are safe to run at any time.

### `init` — Bootstrap the grid

**When to use:** User asks to "start the BTC grid", "init the strategy", or "open the
grid at 70–90k".

**Steps:**
1. Run every pre-flight check above. Abort on any failure.
2. Compute grid buy prices: `70000, 72000, 74000, …, 88000` (10 levels).
3. Build a JSON array of 10 limit buy orders:
   ```json
   [
     {"coin": "BTC", "side": "buy", "size": 0.0015, "type": "limit", "price": 70000, "tif": "Gtc", "reduce_only": false},
     {"coin": "BTC", "side": "buy", "size": 0.0015, "type": "limit", "price": 72000, "tif": "Gtc", "reduce_only": false},
     …
     {"coin": "BTC", "side": "buy", "size": 0.0015, "type": "limit", "price": 88000, "tif": "Gtc", "reduce_only": false}
   ]
   ```
4. First run a dry-run:
   ```bash
   onchainos hyperliquid order-batch --orders-json <path> --strategy-id ligoudan-btc-hype --dry-run
   ```
   Show the preview to the user. Wait for explicit approval before submitting.
5. Submit:
   ```bash
   onchainos hyperliquid order-batch --orders-json <path> --strategy-id ligoudan-btc-hype --confirm
   ```
6. Persist grid state to `state.json` (each cell: buy price, sell-TP price, buy order id,
   fill state, realized profit).

**Output:** number of orders placed, their order IDs, estimated liquidation price,
total reserved margin.

### `status` — Read-only snapshot

**When to use:** User asks "how is the grid doing?", "show status", "show pnl".

**Steps (all read-only, no --confirm):**
1. `onchainos hyperliquid positions` — BTC long count, average entry, unrealized PnL.
2. `onchainos hyperliquid orders --coin BTC` — open buy + TP sell orders.
3. `onchainos hyperliquid positions` filtered for HYPE — HYPE long size & PnL.
4. Read `state.json` for realized profit, compound history, cell status.
5. Compute distance from current price to estimated liquidation.

**Output:**
- Filled cells / total cells
- Open orders by price
- Realized PnL (from state)
- Unrealized PnL (from positions)
- HYPE compound position summary
- Estimated P_liq and distance from current mid
- Accumulated realized profit vs. HYPE compound threshold

### `rebalance` — Handle fills and re-arm the grid

**When to use:** User asks to "rebalance the grid", or periodically (e.g., every hour via
cron in the user's own scheduler). Safe to call when nothing changed (it becomes a no-op).

**Steps:**
1. `onchainos hyperliquid orders --coin BTC` — list currently open orders.
2. Compare against `state.json`. For each cell:
   - **Buy filled, TP sell not yet placed** → place a TP sell at `buy_price + step`,
     `reduce_only: true`, via `order` with `--strategy-id`.
   - **TP sell filled** → mark cell as closed, add `(step × size_btc)` to realized
     profit accumulator, and re-arm: place a new buy at the same price.
3. After state updates, call `compound` if the accumulator crossed the threshold.
4. Persist updated `state.json`.

**Output:** diff since last rebalance (cells opened, cells closed, profit added).

### `compound` — Reinvest realized profit into HYPE

**When to use:** Called by `rebalance` automatically; user may also trigger manually:
"compound the profit now".

**Steps:**
1. Read realized profit accumulator from `state.json`.
2. If accumulator < `hype_compound_threshold_usdc` (default $50), no-op.
3. Check total outstanding HYPE compound notional against
   `max_hype_compound_notional_usdc` (default $5,000). If cap reached, stop compounding
   and warn the user.
4. Fetch HYPE mid price:
   ```bash
   onchainos hyperliquid prices --coin HYPE
   ```
5. Compute HYPE size: `compound_size = floor((accumulator × hype_leverage) / hype_mid,
   szDecimals)`.
6. Dry-run:
   ```bash
   onchainos hyperliquid order --coin HYPE --side buy --type market \
     --size <compound_size> --leverage 2 \
     --strategy-id ligoudan-btc-hype --dry-run
   ```
7. On user approval, execute with `--confirm`.
8. Immediately attach stop-loss / take-profit (write op — `--strategy-id` required):
   ```bash
   onchainos hyperliquid tpsl --coin HYPE \
     --sl-px <entry × 0.85> --tp-px <entry × 1.30> \
     --size <compound_size> \
     --strategy-id ligoudan-btc-hype --confirm
   ```
9. Decrement accumulator by the amount compounded; log the compound event in
   `state.json`.

**Output:** HYPE entry price, size, SL/TP levels, remaining accumulator, total HYPE
notional from compounding so far.

### `shutdown` — Stop the strategy safely

**When to use:** User asks to "stop the grid", "emergency shutdown", or "close
everything". This is a high-impact operation — always dry-run first.

**Steps:**
1. List all open BTC orders tagged to this strategy:
   ```bash
   onchainos hyperliquid orders --coin BTC
   ```
2. Dry-run cancel:
   ```bash
   onchainos hyperliquid cancel-batch --coin BTC --oids <id,id,...> \
     --strategy-id ligoudan-btc-hype --dry-run
   ```
   Show the user the list of orders about to be cancelled.
3. On approval, cancel with `--confirm`.
4. Ask whether to also market-close all BTC longs:
   - If yes: `onchainos hyperliquid close --coin BTC --strategy-id ligoudan-btc-hype --confirm`
   - If no: leave the BTC position in place, but warn that unprotected longs remain.
5. Ask whether to close the HYPE compound position. HYPE has SL/TP in place, so leaving
   it is acceptable. If yes: `onchainos hyperliquid close --coin HYPE --strategy-id ligoudan-btc-hype --confirm`.
6. Archive `state.json` to `state.<timestamp>.json` and write a final summary.

**Output:** total realized PnL, total compounded into HYPE, final positions, any
residual exposure.

## Error Handling

| Error | Cause | Resolution |
| --- | --- | --- |
| `E_INSUFFICIENT_MARGIN` | Perp account USDC < required IM for full grid | Deposit more USDC (`hyperliquid deposit`) or reduce `size_btc` |
| `E_MIN_NOTIONAL` | `size_btc × price < $10` at lowest grid level | Increase `size_btc` to at least `ceil(10 / range_low)` = 0.000143 BTC |
| `E_PRICE_OUT_OF_RANGE` | BTC mid < `range_low` or > `range_high` | Wait for price to re-enter, or adjust `range_low`/`range_high` |
| `E_LIQUIDATION_RISK` | Estimated `P_liq` > `range_low − 5000` | Refuse to init; require lower leverage, larger capital, or wider range |
| `E_STRATEGY_ID_MISSING` | Write invoked without `--strategy-id` | Bug in this skill — never submit writes without the flag |
| `E_DEPENDENT_PLUGIN_MISSING` | `hyperliquid-plugin` not installed | `npx skills add okx/plugin-store --skill hyperliquid-plugin` |
| `E_STATE_CORRUPT` | `state.json` fails schema validation | Stop writes immediately; prompt user to reconcile via `status` then `rebalance` |
| `E_HYPE_CAP_REACHED` | Total HYPE compound notional ≥ cap | Stop compounding; BTC grid continues; surface in `status` |

## Security Notices

**Risk level: advanced**

This strategy opens automated leveraged positions. It is subject to the advanced-tier
requirements: dry-run mode on every write, stop-loss on every HYPE compound position,
per-strategy capital cap, and this explicit disclaimer.

- **Liquidation risk is real.** With default parameters the aggregate BTC grid is
  liquidated at approximately $60.5k. A sharp break below $70k without recovery will
  convert unrealized losses into realized losses and may wipe the committed capital.
- **HYPE is directionally correlated with BTC.** Compounding into HYPE 2x long does
  not hedge BTC downside — it amplifies it. The `max_hype_compound_notional_usdc`
  cap is the only structural brake.
- **No yield guarantee.** Grid trading profits depend on mean reversion inside the
  range. Trending markets reduce or reverse expected returns.
- **Dry-run first.** Every `init`, `compound`, and `shutdown` must present a dry-run
  preview before the `--confirm` call.
- **User controls capital.** This skill never escalates leverage, capital, or cap
  without an explicit user instruction. It refuses to auto-raise limits on failure.
- **Attribution.** All writes include `--strategy-id ligoudan-btc-hype` so that
  fills can be audited via `onchainos leaderboard` or Hyperliquid transaction logs.

This skill is not financial advice. Use at your own risk.
