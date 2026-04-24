# Hyperliquid Execution Contract

This document defines how an AI agent should convert a strategy plan into Hyperliquid Plugin operations.

## Non-negotiable execution rule

The Python script must never be used as a trading executor. It only outputs a JSON plan. Any live order must be executed through the installed Hyperliquid Plugin / Onchain OS Agentic Wallet flow.

## Required read steps

Before live execution, use Hyperliquid Plugin to read:

1. Account equity and available collateral.
2. Current BTC-PERP position.
3. Current open orders / protective orders if available.
4. Latest Hyperliquid market state if available.

Pass the account and position data into the planner.

## Plan-to-execution mapping

| Plan action | Hyperliquid Plugin behavior |
|---|---|
| `noop` | Do nothing |
| `hold` | Do nothing; continue monitoring |
| `halt_new_entries` | Do not open new BTC-PERP exposure until TTL expires |
| `open_long` | Open BTC-PERP long for `parameters.notional_usd` |
| `open_short` | Open BTC-PERP short for `parameters.notional_usd` |
| `scale_in` | Increase existing profitable position by `parameters.notional_usd` |
| `reduce` | Reduce-only close `parameters.fraction` of current position |
| `close_all` | Reduce-only close 100% of current position |

## User confirmation template

Before any live order, show:

```text
Action: <action>
Reason: <reason_code>
Notional / fraction: <parameters>
Leverage: <leverage>
Stop loss: <stop_loss>
Take profit: <take_profit>
Warnings: <warnings>
Execution path: Hyperliquid Plugin / Agentic Wallet
```

Then request explicit confirmation.

## Post-execution verification

After the Hyperliquid Plugin returns, re-read the position and report:

- executed side/action
- filled size or reduced fraction
- remaining position
- current unrealized PnL
- updated stop-loss / take-profit status where applicable

## Anti-abuse rules

- Do not split orders for leaderboard padding.
- Do not generate repetitive churn trades for transaction count.
- Do not coordinate sybil addresses.
- Do not bypass the Hyperliquid Plugin execution chain.
