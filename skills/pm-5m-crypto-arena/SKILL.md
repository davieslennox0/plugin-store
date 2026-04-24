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


## Pre-flight Dependencies (auto-injected by Plugin Store CI)

> Run once per session before first use. These checks ensure required tools are installed.

### Version check (auto-injected)

> **AI Agent Instruction**: Run this version check before executing any commands from this skill. If an update is applied, re-read this SKILL.md before proceeding — the instructions may have changed.

```bash
# Check for skill updates (1-hour cache)
UPDATE_CACHE="$HOME/.plugin-store/update-cache/pm-5m-crypto-arena"
CACHE_MAX=3600
LOCAL_VER="1.0.0"
DO_CHECK=true

if [ -f "$UPDATE_CACHE" ]; then
  CACHE_MOD=$(stat -f %m "$UPDATE_CACHE" 2>/dev/null || stat -c %Y "$UPDATE_CACHE" 2>/dev/null || echo 0)
  NOW=$(date +%s)
  AGE=$(( NOW - CACHE_MOD ))
  [ "$AGE" -lt "$CACHE_MAX" ] && DO_CHECK=false
fi

if [ "$DO_CHECK" = true ]; then
  REMOTE_VER=$(curl -sf --max-time 3 "https://raw.githubusercontent.com/okx/plugin-store/main/skills/pm-5m-crypto-arena/plugin.yaml" | grep '^version' | head -1 | tr -d '"' | awk '{print $2}')
  if [ -n "$REMOTE_VER" ]; then
    mkdir -p "$HOME/.plugin-store/update-cache"
    echo "$REMOTE_VER" > "$UPDATE_CACHE"
  fi
fi

REMOTE_VER=$(cat "$UPDATE_CACHE" 2>/dev/null || echo "$LOCAL_VER")
if [ "$REMOTE_VER" != "$LOCAL_VER" ]; then
  echo "Update available: pm-5m-crypto-arena v$LOCAL_VER -> v$REMOTE_VER. Updating..."
  npx skills add okx/plugin-store --skill pm-5m-crypto-arena --yes --global 2>/dev/null || true
  echo "Updated pm-5m-crypto-arena to v$REMOTE_VER. Please re-read this SKILL.md."
fi
```

### Report install (auto-injected, runs once)

```bash
REPORT_FLAG="$HOME/.plugin-store/reported/pm-5m-crypto-arena"
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
    -d '{"name":"pm-5m-crypto-arena","version":"1.0.0"}' >/dev/null 2>&1 || true
  # Report to OKX API (with HMAC-signed device token)
  curl -s -X POST "https://www.okx.com/priapi/v1/wallet/plugins/download/report" \
    -H "Content-Type: application/json" \
    -d '{"pluginName":"pm-5m-crypto-arena","divId":"'"$DIV_ID"'"}' >/dev/null 2>&1 || true
  touch "$REPORT_FLAG"
fi
```

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
