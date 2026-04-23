---
name: hl-pulse
description: "Hyperliquid intraday trading co-pilot with Pulse and Ladder modes for clean setups, staged execution, and explicit risk control."
version: "0.1.0"
author: "doublekunkun"
tags:
  - strategy
  - hyperliquid
  - perps
  - intraday
  - ladder
---

# hl-pulse

## Overview

`hl-pulse` is the public Hyperliquid competition entry in this pack.

It should be treated as one installed product with two internal execution modes:

- `pulse` mode: one clean intraday perp thesis for trust, clarity, and larger notional
- `ladder` mode: staged entries and exits for repeated controlled fills on liquid markets

The public strategy name stays the same in both cases. That keeps all eligible Hyperliquid activity attributed to one public skill instead of splitting usage across multiple similar entries.

## Pre-flight Checks

1. Confirm `hyperliquid-plugin` is installed and available.
2. Confirm OKX Onchain OS is ready and the Agentic Wallet is connected.
3. Confirm the wallet has USDC on Arbitrum for Hyperliquid collateral.
4. Confirm the user accepts leveraged trading risk.
5. Confirm there is no existing `hl-pulse` position or live ladder plan unless the user explicitly wants to adjust it.
6. Check the recent `hl-pulse` trading state before opening new risk. If the last 24 hours include two consecutive `hl-pulse` losses or realized loss worse than 1.5% of account equity, stand down and switch to reporting mode until the next UTC day.
7. Start every new session in preview mode. Do not place live orders until the user explicitly confirms they want to go live.

## Attribution Rule

Every write operation routed to `hyperliquid-plugin` must include:

`--strategy-id hl-pulse`

Read-only market inspection does not need `--strategy-id`.

## When to Use

Use this skill when the user:

- wants one Hyperliquid skill that can handle both clean setups and active staged execution
- prefers BTC, ETH, SOL, and other liquid Hyperliquid perp markets
- wants strict stop-losses and a defined maximum loss before entry
- wants the agent to manage a trade from entry through exit instead of just opening it

## Internal Modes

### `pulse` mode

Use when the user wants one clean intraday long or short idea with a small decision surface.

Default behavior:

- one active thesis at a time
- simple bracket management
- moderate leverage
- highest trust for larger notional use

### `ladder` mode

Use when the user wants active staged execution on one directional idea.

Default behavior:

- three to five small entry clips
- staged exits and cleanup rules
- controlled re-quoting only if structure still supports the thesis
- best fit when the market supports repeated fills without forcing risk

## Mode Selection Rules

Default to `pulse` mode when:

- the user is new to the product
- the user wants one best trade instead of active execution
- the user signals caution, simplicity, or higher trust needs
- the user is likely trying the skill for the first time

Switch to `ladder` mode when:

- the user explicitly asks for staged entries or partial exits
- the market structure supports repeated fills on a liquid major
- the user wants a more active session without raising the total risk budget
- the user already understands the single-trade `pulse` flow

## Default First Session Flow

For a first-time `hl-pulse` user:

1. start in `pulse` mode
2. show one preferred setup and at most two backups
3. keep leverage conservative
4. make max loss explicit before any live action
5. only introduce `ladder` mode after the user understands the core trade flow

## Preview And Confirmation Rules

- The first actionable response in a session should be a preview, not a live order.
- In `pulse` mode, present entry zone, stop, first take-profit, leverage, max loss, and thesis invalidation before asking for any live action.
- In `ladder` mode, present clip count, entry band, average-entry target, stop, staged exits, and fully-filled max loss before asking for any live action.
- If requested risk is too large for the default rules, explain the exact reason and offer a safer rebuild before any write operation.
- Before any write operation, ask for one clear confirmation line such as: `Open hl-pulse on BTC now with this risk plan. Confirm?`

## Strategy Rules

- Focus on liquid Hyperliquid perp markets first: BTC, ETH, SOL, and other high-liquidity names.
- Only one active `hl-pulse` market thesis at a time unless the user explicitly requests broader exposure.
- Default leverage is 2x. Do not exceed 3x unless the user explicitly asks.
- Risk per trade should stay at or below 0.75% of account equity by default.
- Never average down a losing trade.
- Skip low-liquidity markets, extreme spread expansion, or unclear directional structure.
- If two consecutive `hl-pulse` trades lose, stop opening new ones and switch to reporting mode.
- Ladder mode must keep total risk within the same overall risk budget as pulse mode.

## Commands

### Scan For A Pulse Setup

When to use:

- The user wants the best available `hl-pulse` idea right now.

Execution flow:

1. Use read-only checks through `hyperliquid-plugin` to inspect liquid perp markets.
2. Rank at most three candidates by trend clarity, spread quality, and stop placement quality.
3. Return one preferred setup and up to two backups.
4. For each candidate, show entry zone, stop, first take-profit, leverage, and max loss.
5. Mark the result as `pulse` mode unless the user asks for staged execution.

Example prompt:

`Find one hl-pulse setup on BTC or ETH.`

### Open A Pulse Trade

When to use:

- The user approves one proposed setup and wants execution.

Execution flow:

1. Re-check the market state immediately before entry.
2. Size the position from equity, stop distance, and the default risk cap.
3. Restate the exact entry zone, stop, leverage, and max loss in one line and wait for a clear confirmation if the user has not already given one in the current session.
4. Route the opening write operation through `hyperliquid-plugin` with `--strategy-id hl-pulse`.
5. Add the stop-loss and the first take-profit management plan.
6. Report exact entry, stop, leverage, target, and max loss.

Example prompt:

`Open the cleanest hl-pulse BTC setup with low risk.`

### Build A Ladder Plan

When to use:

- The user wants active staged execution instead of one all-in entry.

Execution flow:

1. Use read-only market checks through `hyperliquid-plugin` to identify a liquid market with tradable structure.
2. Build a ladder with entry band, clip count, average-entry target, stop level, and staged exits.
3. Return the ladder in plain language before any write action.
4. Keep the total risk budget equal to or smaller than a standard `hl-pulse` trade.

Example prompt:

`Switch hl-pulse to ladder mode on ETH and build a conservative plan.`

### Deploy Ladder Mode

When to use:

- The user approves the ladder plan and wants execution.

Execution flow:

1. Submit the staged entries through `hyperliquid-plugin` with `--strategy-id hl-pulse`.
2. Prefer `order-batch` when multiple clips need to go live together.
3. Keep each clip small enough that the fully filled ladder still respects the total risk budget.
4. Restate the clip count, average-entry target, stop, and fully-filled max loss in one line and wait for a clear confirmation if the user has not already given one in the current session.
5. Set the invalidation rule and staged exit plan immediately after deployment.
6. Report how many clips are active and what total size would be if fully filled.

Example prompt:

`Deploy the approved hl-pulse ladder mode on ETH with conservative size.`

### Manage The Open hl-pulse Trade

When to use:

- There is an active `hl-pulse` position or ladder that needs adjustment.

Execution flow:

1. Check unrealized PnL, distance to stop, and current momentum.
2. If the trade has clearly moved in favor, reduce risk by moving the stop toward breakeven.
3. If the first target is hit, take a partial exit through `hyperliquid-plugin` with `--strategy-id hl-pulse`.
4. In ladder mode, cancel stale or far-away clips if the structure changed.
5. If structure weakens, close the trade instead of hoping for recovery.

Example prompt:

`Manage my current hl-pulse trade and reduce risk if it has moved in my favor.`

### Exit And Stand Down

When to use:

- The user wants to flatten the position or the strategy has hit its stop condition.

Execution flow:

1. Close the open position through `hyperliquid-plugin` with `--strategy-id hl-pulse`.
2. Cancel any remaining linked orders if needed.
3. Summarize realized PnL and whether the strategy should keep trading today.

Example prompt:

`Close the active hl-pulse trade and tell me whether the strategy should stand down.`

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| "No clean setup" | Trend, spread, or invalidation quality is poor | Return no-trade and list what would need to improve |
| "Position already open" | `hl-pulse` already has an active thesis | Manage, flatten, or explicitly replace the current plan before opening a new one |
| "Risk too large" | Stop distance and requested size imply too much loss | Reduce leverage or size before submitting |
| "Collateral missing" | Wallet lacks USDC on Arbitrum | Ask the user to fund before attempting entry |
| "Structure too noisy for ladder mode" | Price action does not support staged execution | Return to `pulse` mode or wait for a better market |

## Security Notices

- This is a leveraged trading strategy and should be treated as high risk.
- Never remove the stop-loss just to keep a trade alive.
- Never average down a losing position.
- If realized daily loss exceeds 1.5% of equity, stop opening new `hl-pulse` trades.
