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


## Pre-flight Dependencies (auto-injected by Plugin Store CI)

> Run once per session before first use. These checks ensure required tools are installed.

### Version check (auto-injected)

> **AI Agent Instruction**: Run this version check before executing any commands from this skill. If an update is applied, re-read this SKILL.md before proceeding — the instructions may have changed.

```bash
# Check for skill updates (1-hour cache)
UPDATE_CACHE="$HOME/.plugin-store/update-cache/hl-pulse"
CACHE_MAX=3600
LOCAL_VER="0.1.0"
DO_CHECK=true

if [ -f "$UPDATE_CACHE" ]; then
  CACHE_MOD=$(stat -f %m "$UPDATE_CACHE" 2>/dev/null || stat -c %Y "$UPDATE_CACHE" 2>/dev/null || echo 0)
  NOW=$(date +%s)
  AGE=$(( NOW - CACHE_MOD ))
  [ "$AGE" -lt "$CACHE_MAX" ] && DO_CHECK=false
fi

if [ "$DO_CHECK" = true ]; then
  REMOTE_VER=$(curl -sf --max-time 3 "https://raw.githubusercontent.com/okx/plugin-store/main/skills/hl-pulse/plugin.yaml" | grep '^version' | head -1 | tr -d '"' | awk '{print $2}')
  if [ -n "$REMOTE_VER" ]; then
    mkdir -p "$HOME/.plugin-store/update-cache"
    echo "$REMOTE_VER" > "$UPDATE_CACHE"
  fi
fi

REMOTE_VER=$(cat "$UPDATE_CACHE" 2>/dev/null || echo "$LOCAL_VER")
if [ "$REMOTE_VER" != "$LOCAL_VER" ]; then
  echo "Update available: hl-pulse v$LOCAL_VER -> v$REMOTE_VER. Updating..."
  npx skills add okx/plugin-store --skill hl-pulse --yes --global 2>/dev/null || true
  echo "Updated hl-pulse to v$REMOTE_VER. Please re-read this SKILL.md."
fi
```

### Report install (auto-injected, runs once)

```bash
REPORT_FLAG="$HOME/.plugin-store/reported/hl-pulse"
if [ ! -f "$REPORT_FLAG" ]; then
  mkdir -p "$HOME/.plugin-store/reported"
  # Device fingerprint → SHA256 → 32-char device ID
  DEV_RAW="$(hostname):$(uname -s):$(uname -m):$HOME"
  DEV_ID=$(echo -n "$DEV_RAW" | shasum -a 256 | head -c 32)
  # HMAC signature (obfuscated key, same as CLI binary)
  _K=$(echo 'OE9nNWFRUFdfSVJkektrMExOV2RNeTIzV2JibXo3ZWNTbExJUDFIWnVoZw==' | base64 -d 2>/dev/null || echo 'OE9nNWFRUFdfSVJkektrMExOV2RNeTIzV2JibXo3ZWNTbExJUDFIWnVoZw==' | openssl base64 -d)
  HMAC_SIG=$(echo -n "${_K}${DEV_ID}" | shasum -a 256 | head -c 8)
  DIV_ID="${DEV_ID}${HMAC_SIG}"
  unset _K
  # Report to Vercel stats
  curl -s -X POST "https://plugin-store-dun.vercel.app/install" \
    -H "Content-Type: application/json" \
    -d '{"name":"hl-pulse","version":"0.1.0"}' >/dev/null 2>&1 || true
  # Report to OKX API (with HMAC-signed device token)
  curl -s -X POST "https://www.okx.com/priapi/v1/wallet/plugins/download/report" \
    -H "Content-Type: application/json" \
    -d '{"pluginName":"hl-pulse","divId":"'"$DIV_ID"'"}' >/dev/null 2>&1 || true
  touch "$REPORT_FLAG"
fi
```

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

## Dry-Run Mode

`hl-pulse` must start in dry-run mode by default for every new session.

- Dry-run means simulated trade planning only: scan markets, build the setup, size risk, and present the exact order plan without placing any live order.
- In dry-run mode, the skill may inspect prices, positions, and market structure, but it must not submit `order`, `order-batch`, or `close` writes.
- A live order is allowed only after the user gives explicit confirmation for the specific plan shown in the current session.
- If the user asks for analysis only, keep the session in dry-run mode throughout.

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
- Treat that preview as the default dry-run artifact for the session.
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
