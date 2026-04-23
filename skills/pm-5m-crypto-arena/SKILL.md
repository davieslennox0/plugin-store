---
name: pm-5m-crypto-arena
description: "One-tap Polymarket 5-minute crypto Up/Down trading co-pilot"
version: "1.0.0"
author: "KB"
tags:
  - polymarket
  - prediction-market
  - crypto
  - trading-strategy
  - five-minute
---

# PM 5M Crypto Arena

## Overview

This skill helps users participate in Polymarket 5-minute crypto Up/Down markets with a guarded one-tap workflow. It finds active BTC, ETH, SOL, or other supported 5-minute markets through `polymarket-plugin`, summarizes the next trade window, and executes only after explicit user confirmation.

This skill must not choose a side for the user unless the user has already specified the intended outcome. If the user asks which side to buy, present neutral market information, prices, timing, and risk notes, then ask the user to choose `UP` or `DOWN`.

## Pre-flight Checks

Before any trade workflow:

1. Ensure the dependency is installed:

```bash
npx skills add okx/plugin-store --skill polymarket-plugin --yes
```

2. Check jurisdiction and account access:

```bash
polymarket-plugin check-access
```

If access is restricted, stop the trade flow. Do not guide the user through deposits or live trading from restricted jurisdictions.

3. Check wallet, balance, and proxy readiness:

```bash
polymarket-plugin quickstart
```

4. Confirm the user understands that prediction markets can lose the full amount staked.

## Commands

### Check Access

```bash
polymarket-plugin check-access
```

**When to use**: Before showing a live trading path or deposit instructions.
**Output**: Polymarket availability and access status.
**If restricted**: Stop. Do not continue with funding, deposit, or trade guidance.

### Check Setup

```bash
polymarket-plugin quickstart
```

**When to use**: At the start of a session, before a dry-run, or when the user reports wallet/proxy/balance issues.
**Output**: Wallet readiness, balance state, and setup guidance from the Polymarket Plugin.

### List 5-Minute Markets

```bash
polymarket-plugin list-5m --coin BTC --count 3
```

**When to use**: When the user asks for current or upcoming 5-minute crypto markets.
**Output**: Recent or upcoming market windows, condition IDs, order availability, and outcome prices.
**Selection rule**: Prefer the nearest market with `acceptingOrders=true` and enough time left for the user to confirm.

### Dry-run Buy

```bash
polymarket-plugin buy \
  --market-id <conditionId> \
  --outcome up \
  --amount 5 \
  --dry-run \
  --strategy-id pm-5m-crypto-arena
```

**When to use**: Before the first live trade in a session, whenever the user asks for a preview, or when market details changed after the user first asked.
**Output**: A preview of the intended order without placing a real trade.
**Required**: Use `--strategy-id pm-5m-crypto-arena` on every buy preview and live buy.

### Confirmed Buy

```bash
polymarket-plugin buy \
  --market-id <conditionId> \
  --outcome up \
  --amount 5 \
  --strategy-id pm-5m-crypto-arena
```

**When to use**: Only after the user explicitly confirms the exact market, outcome, amount, and price context.
**Output**: A Polymarket buy result from the dependency plugin.
**Required**: The user must confirm before this command is run.

## One-Tap Workflow

Use this workflow for requests like "BTC 5 minutes, 5 USDC UP" or "show me the next SOL 5-minute market":

1. Run `polymarket-plugin check-access`.
2. If allowed, run `polymarket-plugin quickstart`.
3. Run `polymarket-plugin list-5m --coin <COIN> --count 3`.
4. Choose the nearest market that is accepting orders and not too close to settlement.
5. Present a compact confirmation prompt:

```text
BTC 5-minute market: <window>
Market ID: <conditionId>
UP price: <price>
DOWN price: <price>
Requested outcome: UP
Amount: 5 USDC
Strategy ID: pm-5m-crypto-arena

Reply confirm to buy, skip to ignore this window, switch to buy DOWN, or exit.
```

6. If the user confirms, run the live `polymarket-plugin buy` command with `--strategy-id pm-5m-crypto-arena`.
7. Report the result and the remaining session budget.

## Guardrails

- Do not recommend a specific outcome unless the user has already specified it.
- Do not execute a live buy without explicit confirmation.
- Do not support unlimited automatic betting, recurring unattended bets, or "buy every 5 minutes until stopped" instructions.
- Default single-trade amount: 5 USDC.
- Suggested single-trade range: 5-20 USDC.
- Suggested session cap: 60 USDC.
- If either outcome price is above 0.70, warn that the payout profile is less favorable before asking for confirmation.
- Skip markets that are not accepting orders or are too close to settlement for a calm confirmation flow.
- Never ask for private keys, seed phrases, API secrets, or email OTP codes.

## Examples

### User Specifies Direction

User: "Use 5 USDC to buy BTC next 5-minute UP."

Agent:

1. Runs `check-access`.
2. Runs `quickstart`.
3. Runs `list-5m --coin BTC --count 3`.
4. Shows the selected market and asks for confirmation.
5. After the user confirms, executes:

```bash
polymarket-plugin buy \
  --market-id <conditionId> \
  --outcome up \
  --amount 5 \
  --strategy-id pm-5m-crypto-arena
```

### User Asks Which Side

User: "BTC next 5 minutes, UP or DOWN?"

Agent: Present market window, UP/DOWN prices, time remaining, and risk notes. Do not choose for the user. Ask the user to reply with `UP`, `DOWN`, `skip`, or `exit`.

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| Access restricted | Polymarket is unavailable for the user's jurisdiction | Stop trading guidance and do not provide deposit or live trade steps |
| No accepting 5-minute market | Market closed, stale, or too close to settlement | List the next 3 markets or ask the user to try again later |
| Insufficient balance | The wallet or Polymarket proxy lacks funds | Show the `quickstart` output and ask the user whether they want setup guidance |
| User has not confirmed | Live trade lacks explicit approval | Ask for confirmation of market, outcome, amount, and price context |
| Price changed materially | Market moved after preview | Re-run `list-5m`, present updated details, and ask for fresh confirmation |

## Security Notices

- This is a standard-risk trading strategy skill for prediction markets.
- The user can lose the full amount committed to a market.
- All live writes must go through `polymarket-plugin` and include `--strategy-id pm-5m-crypto-arena`.
- This skill does not custody funds and must never request private keys, seed phrases, API secrets, or OTP codes.
- This skill is a trading co-pilot, not an unattended trading bot.
