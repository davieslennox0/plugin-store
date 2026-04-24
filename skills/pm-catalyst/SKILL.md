---
name: pm-catalyst
description: "Polymarket first-trade strategy skill for major catalysts and short-dated event setups, built for clear yes/no positioning, dry-run previews, and low-friction onboarding."
version: "0.1.0"
author: "doublekunkun"
tags:
  - strategy
  - polymarket
  - prediction-market
  - catalysts
  - events
  - flash
---

# pm-catalyst

## Overview

`pm-catalyst` is the public Polymarket competition entry in this pack.

It should be treated as one beginner-friendly hero product with two internal modes:

- `catalyst` mode: major event trades with clear yes/no framing
- `flash` mode: short-dated crypto or timing-sensitive setups with small stake sizes

The public strategy name stays the same in both cases so the product can compete on both trading addresses and some repeat activity without splitting attribution into multiple Polymarket listings.

The design goal is simple:

- make the first Polymarket trade feel understandable
- make the downside obvious before execution
- keep the first position small enough that a new user can say yes
- create a second-use path through `flash` mode without turning the product into a confusing market scanner

## Pre-flight Checks

1. Confirm `polymarket-plugin` is installed and available.
2. Confirm OKX Onchain OS is ready and the Agentic Wallet is connected.
3. Run the access and setup checks required by `polymarket-plugin` before proposing a live trade.
4. Confirm the user has USDC available and can fund the trade.
5. Prefer liquid markets with clear wording and a known resolution path.
6. Keep default stake sizing modest unless the user explicitly asks for more.
7. Start every new session in preview mode. Do not place a live order until the user clearly confirms they want to proceed.
8. If two `pm-catalyst` trades have gone poorly in the last 24 hours, or if liquidity quality deteriorates sharply, switch to status-only or idea-only mode until the next UTC day unless the user explicitly asks to continue.

## Dry-Run Mode

`pm-catalyst` must start in dry-run mode by default for every new session.

- Dry-run means simulated market selection and trade planning only.
- In dry-run mode, the skill may run access checks, setup checks, market discovery, odds inspection, and order planning.
- In dry-run mode, it must not place `buy`, `sell`, `cancel`, or `redeem` writes.
- A live order is allowed only after the user explicitly confirms the specific market, side, and stake shown in the current session.
- If the user asks for ideas only, keep the entire interaction in dry-run mode.

## Attribution Rule

Every write operation routed to `polymarket-plugin` must include:

`--strategy-id pm-catalyst`

Read-only checks do not need `--strategy-id`.

## When to Use

Use this skill when the user:

- wants a simple event-driven position instead of a leveraged perp
- wants the agent to handle market selection, order choice, and setup flow
- wants a capped-loss position with a short explanation in plain language
- wants either a major catalyst trade or a short-dated crypto opportunity
- wants a low-friction first trade that can convert into a real funded address

## Internal Modes

### `catalyst` mode

Use when the user wants a clear real-world catalyst such as an election, sports result, macro release, or crypto milestone.

Default behavior:

- understandable market wording first
- modest stake size
- clear time-to-resolution framing
- best fit for new-user trust and address growth
- default first-trade mode

### `flash` mode

Use when the user wants a short-dated crypto or timing-sensitive market with faster turnover.

Default behavior:

- very small default stake size
- tighter timing awareness
- only on liquid, active markets
- good fit for repeat usage without turning the product into an unattended betting loop

## Address Conversion Rules

For a first-time `pm-catalyst` user:

- show one preferred market and at most two alternatives
- prefer markets that can be explained in one sentence
- keep the first suggested stake modest, typically in the low double-digit USDC range unless the user explicitly asks for more
- prefer markets resolving within 7 days for the first trade when a clean candidate exists
- make exact maximum loss and expected resolution timing explicit before any live action
- do not introduce `flash` mode unless the user asks for it or already understands the base event-trade flow

## Market Ranking Rubric

When `pm-catalyst` compares candidate markets, score each one against the same rubric instead of improvising:

- `wording clarity` (0-3): can the market be explained in one sentence, with obvious resolution criteria?
- `liquidity and spread quality` (0-3): are odds active enough and spreads tight enough for a calm entry?
- `resolution timing` (0-2): does the market resolve soon enough to feel understandable, especially for a first trade?
- `event salience` (0-1): is the catalyst something a mainstream user can recognize without a long briefing?
- `readiness fit` (0-1): does this market fit the current user's setup, balance, and confidence level?

Interpretation:

- `8-10`: preferred candidate
- `7`: acceptable backup only
- `6 or below`: no-trade for first-time users unless the user explicitly insists

Tie-breakers:

- prefer the market with clearer wording over slightly better odds
- prefer the nearer clean resolution over the more distant thesis
- prefer the market that needs less explanation over the more exotic setup

## Stake Sizing Tiers

Default size guidance should stay explicit:

- first `catalyst` trade: `10-25 USDC`
- standard `catalyst` trade for a returning user: `25-75 USDC`
- `flash` trade: `5-20 USDC`

Adjustment rules:

- if balance or confidence is limited, size down before changing the market
- if the user explicitly asks for a larger size, restate exact maximum loss before any live action
- never let `flash` mode size exceed the current default `catalyst` size without a specific user request
- if setup, access, or funding is not ready, do not simulate a live size at all; stop at readiness guidance

## Mode Selection Rules

Default to `catalyst` mode when:

- the user is new to Polymarket or to this skill
- the user wants a simple first trade
- the user prefers clear wording and obvious resolution criteria
- the goal is address conversion and user trust

Switch to `flash` mode when:

- the user explicitly asks for a short-dated opportunity
- the user wants a faster cycle with a small stake
- the market is active and liquid enough to justify faster turnover
- the user already understands the basic event-trade flow

## Default First Session Flow

For a first-time `pm-catalyst` user:

1. run access and setup checks first
2. start in `catalyst` mode
3. if the user is not ready, return the next required setup step and stop there
4. score candidate markets using the ranking rubric
5. show one preferred market and at most two alternatives
6. prefer a market with simple wording and relatively near resolution
7. keep the first suggested stake inside the first-trade size tier unless the user explicitly asks for more
8. only introduce `flash` mode after the user sees one clean event-trade flow

## Preview And Confirmation Rules

- The first actionable response in a session should be a preview, not a live order.
- Treat that preview as the default dry-run artifact for the session.
- In `catalyst` mode, present market wording, side, current odds, stake, exact maximum loss, and expected resolution path before any write action.
- In `catalyst` mode, also include why this market is understandable enough for a first trade.
- In `flash` mode, present timing window, side, current odds, smaller stake size, exact maximum loss, and why the faster setup is still liquid enough to justify action.
- If liquidity, wording clarity, or resolution timing is weak, return no-trade instead of pushing the user into a marginal market.
- If the user is not access-ready or setup is incomplete, stop at readiness guidance instead of pretending the trade can go live.
- Before any write operation, ask for one clear confirmation line such as: `Open this pm-catalyst position now with this stake and max loss. Confirm?`

## Strategy Rules

- Prefer liquid, understandable markets over obscure ones.
- Prefer markets whose resolution criteria can be summarized in plain language.
- Prefer catalysts that resolve within 30 days unless the user explicitly wants longer duration.
- Prefer catalysts resolving within 7 days for a first-time user if quality is otherwise similar.
- Prefer tighter spreads and active orderbooks.
- Keep default per-trade risk inside the published sizing tiers unless the user explicitly asks for more.
- Do not chase illiquid prices or unclear wording.
- If no high-quality market exists, return no-trade instead of forcing a bet.
- In `flash` mode, prefer short-dated markets with obvious timing and active pricing, but keep stake size smaller than `catalyst` mode.
- Open at most one new `pm-catalyst` thesis at a time unless the user explicitly asks for more.
- For first-time use, optimize for trust and comprehension before speed.
- Use the market ranking rubric before presenting a preferred trade.

## Commands

### Check Access And Build Readiness

When to use:

- The user is new to Polymarket, not yet ready to trade, or asks to get set up first.

Execution flow:

1. Run the access and setup checks documented by `polymarket-plugin`.
2. Confirm whether the user can trade and whether funding or setup work is still needed.
3. If the user is not ready, stop there and explain the next required step clearly in one short action line.
4. If the user is ready, offer to move into `catalyst` mode with one simple first market.

Example prompt:

`Get me ready for my first pm-catalyst trade.`

### Find A Catalyst Market

When to use:

- The user wants the best current `pm-catalyst` opportunity.

Execution flow:

1. Use read-only market discovery through `polymarket-plugin`.
2. Rank markets with the published rubric: clarity, liquidity, resolution timing, event salience, and readiness fit.
3. Return one preferred market and up to two alternatives.
4. Explain the thesis in plain language, not just market jargon.
5. Prefer one market a first-time user can understand immediately.
6. Mark the result as `catalyst` mode unless the user asks for a faster setup.

Example prompt:

`Find a pm-catalyst trade around a major crypto event this week.`

### Open A Catalyst Position

When to use:

- The user accepts one proposed market and wants to enter.

Execution flow:

1. Confirm the current odds and the maximum loss.
2. Restate the market wording, side, stake, exact maximum loss, and expected resolution timing in one line and wait for a clear confirmation if the user has not already given one in the current session.
3. Choose the order style through `polymarket-plugin` with `--strategy-id pm-catalyst`.
4. If needed, let the dependent plugin handle the funding move into Polygon.
5. Report side, entry price, stake, expected resolution timing, and the exact amount at risk.

Example prompt:

`Open the best pm-catalyst position with a small stake.`

### Find A Flash Setup

When to use:

- The user wants a short-dated crypto or timing-sensitive Polymarket opportunity.

Execution flow:

1. Use read-only discovery through `polymarket-plugin` to find active short-dated markets.
2. Rank candidates with the same rubric, but weight timing and liquidity most heavily.
3. Return one preferred setup and up to two backups.
4. Keep the suggested size inside the `flash` size tier and smaller than the default `catalyst` mode size.
5. Use this mode only when the user is ready for faster repetition, not as the default onboarding path.

Example prompt:

`Use pm-catalyst flash mode to find a short-dated crypto opportunity.`

### Open A Flash Position

When to use:

- The user approves a faster setup and wants to enter with a small stake.

Execution flow:

1. Confirm the timing still makes sense and that the market is still active.
2. Restate the side, stake, timing window, and exact maximum loss in one line and wait for a clear confirmation if the user has not already given one in the current session.
3. Use `polymarket-plugin` with `--strategy-id pm-catalyst`.
4. Report side, entry price, stake, and exact maximum loss.
5. Remind the user that this mode is for small, timing-sensitive positions only.

Example prompt:

`Open the pm-catalyst flash trade with the minimum sensible stake.`

### Manage Open Orders And Odds

When to use:

- The user wants to check price movement or update an order.

Execution flow:

1. Inspect current odds, open orders, and live position value.
2. Cancel or replace stale orders through `polymarket-plugin` with `--strategy-id pm-catalyst`.
3. If the user only wants a status update, use read-only calls and explain PnL simply.
4. In `flash` mode, be quicker to stand down if timing or liquidity quality deteriorates.
5. If the original thesis is no longer easy to explain, favor simplification and exit over forced activity.

Example prompt:

`Check my pm-catalyst position and cancel anything stale.`

### Cash Out Or Redeem

When to use:

- The event has moved far enough, or it has resolved.

Execution flow:

1. Exit or redeem through `polymarket-plugin` with `--strategy-id pm-catalyst`.
2. Summarize the result, realized PnL, and whether a new catalyst trade is worth considering.

Example prompt:

`Redeem or close the pm-catalyst position and summarize the outcome.`

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| "No clean market" | Spread, wording, or liquidity is poor | Return no-trade and explain why |
| "Stake too large" | Requested size is too aggressive for the account | Reduce stake and restate max loss |
| "Funding not ready" | Wallet lacks usable USDC | Ask the user to fund before submitting |
| "Resolution too far away" | Market ties up capital too long for the default rules | Suggest a nearer catalyst instead |
| "Flash window has passed" | Timing-sensitive setup is no longer attractive | Stand down and wait for the next short-dated opportunity |
| "Access not ready" | Polymarket access or setup checks did not clear | Stop at readiness instructions and do not simulate a live entry |

## Security Notices

- Event markets still carry real money risk even without leverage.
- Do not force a trade just because a headline is trending.
- Avoid unclear market wording or thin liquidity.
- Prefer small first positions for new users.
- Default to dry-run planning before any real-money action.
