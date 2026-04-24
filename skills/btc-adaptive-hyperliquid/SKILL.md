---
name: btc-adaptive-hyperliquid
description: "Adaptive BTC perpetual strategy planner for Hyperliquid Plugin with dry-run safety, dynamic risk controls, and explicit user confirmation."
version: "1.0.0"
author: "cw"
tags:
  - hyperliquid
  - bitcoin
  - perpetuals
  - trading-strategy
  - risk-management
---

# BTC Adaptive Hyperliquid

## Overview

BTC Adaptive Hyperliquid is an advanced Strategy Skill for BTC perpetual futures. It generates a structured action plan for Hyperliquid execution using adaptive breakout, failed-breakout fade, funding, RSI, ATR volatility, and real-time position risk rules.

This Skill is intentionally designed as a **plan-only strategy layer**:

- The included Python script does **not** submit orders.
- Live execution must be performed by the installed **Hyperliquid Plugin** through Onchain OS / Agentic Wallet after explicit user confirmation.
- Dry-run mode is the default.

Use this Skill when a user asks for an adaptive BTC perpetual strategy on Hyperliquid, such as:

- "Run the BTC adaptive Hyperliquid strategy in dry-run."
- "Check whether I should open, reduce, close, or hold my BTC perp position."
- "Use the strategy plan and execute through Hyperliquid Plugin after I confirm."

## Risk Disclaimer

This is an advanced trading Skill. Crypto perpetual futures are high-risk instruments and can result in total loss of deployed capital. The strategy output is not financial advice. Historical behavior, indicators, and model outputs do not guarantee future results. Always show the user the proposed action, notional amount, leverage, stop loss, take profit, and risk explanation before any live execution.

## Competition Eligibility Notice

For Plugin Store DApp Challenge usage, every live trade must be executed through the **Hyperliquid Plugin** execution chain. The script in this Skill only generates the decision plan and must not be used to bypass the Basic Skill. Do not use this Skill for wash trading, volume padding, sybil activity, or artificial leaderboard manipulation.

## Pre-flight Checks

Before using this Skill:

1. Confirm the user has installed the Hyperliquid Plugin from Plugin Store.
2. Confirm the user wants BTC perpetual exposure on Hyperliquid.
3. Run in dry-run mode first.
4. Obtain fresh account and position data using the Hyperliquid Plugin.
5. Do not ask the user for private keys, seed phrases, API secrets, or raw signing material.
6. Check that `config/default.json` has dry-run enabled and hard risk limits configured.

## Files

- `scripts/btc_adaptive_hyperliquid.py` — dependency-free Python decision engine.
- `config/default.json` — default strategy and risk parameters.
- `examples/` — sample account and position payloads.
- `references/strategy-design.md` — strategy design and conflict-resolution rules.
- `references/hyperliquid-execution-contract.md` — how the agent should map plans into Hyperliquid Plugin calls.

## Commands

### 1. Validate configuration

```bash
python3 scripts/btc_adaptive_hyperliquid.py validate-config --config config/default.json
```

**When to use:** Before the first run, before submission review, and after changing risk settings.

**Output:** JSON with `ok: true` or validation errors.

### 2. Run deterministic demo

```bash
python3 scripts/btc_adaptive_hyperliquid.py demo --config config/default.json --output text
```

**When to use:** To verify the Skill works without network access or wallet access.

**Output:** A synthetic dry-run plan.

### 3. Generate dry-run action plan with public market fetch

```bash
python3 scripts/btc_adaptive_hyperliquid.py plan \
  --config config/default.json \
  --account-json @examples/account.sample.json \
  --position-json @examples/position-flat.sample.json \
  --fetch-market \
  --dry-run
```

**When to use:** To produce a plan using public BTCUSDT market data from Binance futures while still relying on Hyperliquid Plugin for wallet/account/position data and any execution.

**Output:** JSON action plan containing:

- `action`: `noop`, `hold`, `open_long`, `open_short`, `scale_in`, `reduce`, `close_all`, or `halt_new_entries`
- `parameters`: notional, leverage, stop loss, take profit, fraction, TTL as applicable
- `risk_controls`: confirmation and reduce-only requirements
- `hyperliquid_plugin_execution_hint`: human-readable execution mapping

### 4. Generate plan from provided market JSON

```bash
python3 scripts/btc_adaptive_hyperliquid.py plan \
  --config config/default.json \
  --account-json @examples/account.sample.json \
  --position-json @examples/position-long.sample.json \
  --market-json @examples/market.sample.json \
  --dry-run
```

Use this when the agent already obtained market data from the Hyperliquid Plugin or another declared source.

## Agent Workflow

### Dry-run workflow

1. Use the Hyperliquid Plugin to read account state and BTC-PERP position state.
2. Run `btc_adaptive_hyperliquid.py plan` with `--dry-run`.
3. Present the plan to the user.
4. Do not execute orders.

### Live workflow after explicit user confirmation

1. Use the Hyperliquid Plugin to refresh account, open orders, and current BTC-PERP position.
2. Run the planner using fresh inputs.
3. Show the user:
   - action
   - reason code
   - notional or fraction
   - leverage
   - take profit and stop loss
   - major warnings
4. Ask for explicit confirmation to execute.
5. Execute only through the Hyperliquid Plugin / Onchain OS Agentic Wallet flow.
6. For `reduce` and `close_all`, use reduce-only behavior where supported.
7. Re-read the position after execution and report the result.

## Action Semantics

| Action | Meaning | Execution rule |
|---|---|---|
| `noop` | No clean setup | No trade |
| `hold` | Existing position within risk bounds | No trade |
| `halt_new_entries` | Risk regime is high | Do not open new positions until TTL expires |
| `open_long` | Adaptive long setup | Open BTC-PERP long via Hyperliquid Plugin only |
| `open_short` | Adaptive short setup | Open BTC-PERP short via Hyperliquid Plugin only |
| `scale_in` | Add to an existing profitable position | Only after confirmation and only if exposure caps remain valid |
| `reduce` | Partial risk reduction | Use reduce-only close for the stated fraction |
| `close_all` | Full risk exit | Use reduce-only close for 100% of position |

## Built-in Risk Controls

- Dry-run is the default.
- Per-trade margin ratio default is `0.30`.
- Maximum configurable per-trade ratio is `0.80`.
- Session loss cap default is `6%` of equity.
- Soft unrealized loss reduction default is `2%` of equity.
- Emergency full close default is `4%` of equity.
- Mixed hedge exposure triggers `close_all` recommendation.
- The script never submits orders or touches private keys.

## Error Handling

| Error | Cause | Resolution |
|---|---|---|
| `market required` | No market data provided and `--fetch-market` was not used | Pass `--market-json` or use `--fetch-market` |
| `json_decode_error` | Invalid account/position/market JSON | Re-run Hyperliquid Plugin read step and pass valid JSON |
| `network_error` | Public market fetch failed | Use provided market JSON or retry later |
| `no_equity_or_account_data` | Account state missing or equity is zero | Re-read account through Hyperliquid Plugin |
| `mixed_hedge_position_detected` | Both long and short exposure detected | Ask user before reduce-only closing exposure |

## Security Notices

- This Skill has no wallet signing code.
- This Skill has no hardcoded keys, seed phrases, Telegram tokens, or API secrets.
- External market-data domains must be declared in `plugin.yaml`.
- Live trade execution must stay inside the Hyperliquid Plugin / Agentic Wallet path.
- Do not split orders to inflate transaction count or leaderboard ranking.
