---
name: pmbasket
description: "Natural-language event baskets on Polymarket: one sentence of intent becomes a liquidity-filtered, risk-capped basket placed through Polymarket CLOB via polymarket-plugin."
version: "1.0.0"
author: "dddd86971-cloud"
tags:
  - polymarket
  - prediction-markets
  - basket
  - event-driven
  - agentic-wallet
---

# pmbasket

## Overview

`pmbasket` turns a trader's one-sentence event view — "FOMC May 2026 will
be dovish", "CPI April prints hot", "Trump tariff sticks" — into a
risk-capped basket of small bets across related Polymarket markets. One
natural-language intent becomes N liquidity-filtered tickets, each
executed via Polymarket's CLOB.

This Skill **depends on the `polymarket-plugin` plugin** (author:
skylavis-sky, published in the OKX Plugin Store). `polymarket-plugin`
is a Rust CLI binary that wraps Polymarket's Gamma + CLOB APIs and
talks to the onchainos wallet for signing. It exposes commands like
`list-markets`, `get-market`, `buy`, `sell`, `get-positions`,
`redeem`, and handles USDC.e approvals, order signing, proxy wallet
setup, and — critically — Plugin Store Leaderboard attribution via
its `--strategy-id` flag.

`pmbasket` builds a **basket-strategy layer** on top: discovery,
ranking, per-basket risk caps, side-conflict detection, rebalance
logic, and consistent `--strategy-id pmbasket` tagging on every
write.

What makes pmbasket different from single-market Polymarket betting:

- **Theme-driven discovery.** The Skill guides the agent to search
  Polymarket for all markets related to the user's theme, rather than
  stopping at the first one that matches.
- **Liquidity and freshness filters are explicit.** The Skill defines
  hard rules (minimum liquidity, not-yet-resolved, binary-only) so the
  agent cannot accidentally bet into illiquid or expired markets.
- **Hard per-basket caps prevent over-sizing** even if the user asks
  for more. Caps are documented and enforced in pre-flight.
- All on-chain writes go through `polymarket-plugin`. pmbasket adds
  basket-level structure; it does not reinvent the trading primitives.

**Risk level: `advanced`.** This Skill places multiple live prediction-
market bets from a single confirmation. Read Security Notices before
using it with real funds.

## When to Use

Use this Skill when the user:

- Has an **event-level thesis** that plausibly maps to several Polymarket
  markets, not just one — e.g. "FOMC hawkish", "Trump wins", "BTC above
  100k by X", "recession by year-end"
- Wants to express the thesis across a **basket** to reduce per-market
  variance while keeping total risk small
- Is comfortable with multiple simultaneous prediction-market positions
  and has USDC available on the Polymarket chain

Do **not** use this Skill when:

- The user has conviction on a single specific market — direct them to
  the `polymarket-plugin` plugin for a single bet
- The event has already resolved or will resolve before the user's
  position could matter — the Skill will filter these out but the user
  should know
- The user wants leveraged exposure — Polymarket is cash bets, no leverage

## First Session Flow

After Pre-flight Checks (below) have run and the list-positions query
has returned, examine whether the user has **any** recent Polymarket
positions at all (since pmbasket orders carry no distinguishing tag,
we cannot tell pmbasket activity from other activity). If the user
has **zero open positions and no closed positions in the last 30
days**, this is likely a first-time Polymarket session via pmbasket —
prefer this training-wheels introduction:

1. Start in **dry-run** regardless of what the user typed, unless they
   explicitly demanded live execution with phrases like "just place it"
   or "skip the preview".
2. Build the basket with **conservative defaults** even if the user
   asked for more:
   - `perTicketUsd = min(requested, 5)` — cap at $5 per ticket for a
     first basket, even if the user said $30
   - `maxTickets = min(requested, 5)` — cap at 5 markets for a first
     basket
   - `minLiquidityUsd = 10_000` — do not relax this
3. Present the dry-run plan with the basket label, ticket list, and
   `totalExposureUsd`. Make clear this is a conservative first basket.
4. Explicitly tell the user: "This is a preview at reduced size so you
   can see how the Skill works. Reply 'place it' to execute as shown,
   or 'larger' to rebuild with your original request."
5. Only after the user has successfully completed one full pmbasket
   cycle (plan → place → at least one market resolved or the user
   sold their position) in this session, follow their requested sizes
   without this adjustment.

Note: this decision happens **inside** the `basket-plan` flow after
pre-flight completes — not before. The same list-positions call used
for the same-theme lockout check (pre-flight step 4) provides the
signal.

## Pre-flight Checks

Before using this Skill, the agent must verify:

1. The `onchainos` CLI is installed and the wallet is accessible (the
   `polymarket-plugin` auto-injects its install steps; verify via
   `onchainos --version`).
2. The **`polymarket-plugin` plugin** is installed — the Polymarket
   prediction-market plugin (author: skylavis-sky) published in the
   OKX Plugin Store. pmbasket shells out to this plugin for every
   Polymarket operation. If not installed:
   `npx skills add okx/plugin-store --skill polymarket-plugin`
3. The user has sufficient **USDC.e** (bridged USDC on Polygon,
   contract `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`, not native
   USDC). Run `polymarket-plugin balance` to check. If low, point the
   user at `polymarket-plugin deposit`.
4. **Geographic eligibility.** Run `polymarket-plugin check-access`
   before any trading flow. Polymarket's Terms of Service prohibit
   residents of the United States, France, Singapore, and several
   other jurisdictions from trading. If `check-access` reports a
   restriction, refuse to proceed and tell the user. Do not attempt
   to bypass. If the user volunteers that they are in a restricted
   jurisdiction but `check-access` passes (VPN, etc.), still refuse
   — pmbasket is not a tool for circumventing ToS.
5. **No overlapping active basket on the same theme.** Run
   `polymarket-plugin get-positions` to list the user's open
   positions. Since pmbasket's `--strategy-id pmbasket` attribution is
   tracked server-side by `onchainos wallet report-plugin-info`, not
   in the position output, the agent cannot tell pmbasket positions
   apart from non-pmbasket ones here. Approximate:
   - For each open position, compute the keyword-match score (from
     `basket-plan` step 4) between the position's `title` and the
     user's current theme tokens.
   - If any position has keyword-match ≥ 1, warn the user:
     "You already have a position on {that market's title}. Do you
     want to open a new basket that may include overlapping markets?"
   - Proceed only on explicit user confirmation.
6. **24h realized-loss circuit breaker.** From `get-positions`, sum
   `realized_pnl` across all positions. If cumulative ≤ −$30 over
   the last 24h window (if timestamps are available; otherwise all
   realized PnL on open positions), refuse to open a new basket until
   the next UTC day and tell the user why. This filter errs on the
   safe side — it counts all realized PnL, not just pmbasket-sourced,
   because per-Skill filtering is not available to the agent.
7. **Dry-run mode is the default.** Every new intent starts in dry-run
   and produces a basket plan only. Live execution requires an explicit
   user confirmation in the same session.

## Attribution for Plugin Store Leaderboard

Every write operation (`buy`, `sell`, `redeem`) performed via
`polymarket-plugin` must be called with the flag `--strategy-id pmbasket`.

This is the **real** attribution mechanism: when `polymarket-plugin`
receives a non-empty `--strategy-id`, it calls
`onchainos wallet report-plugin-info` after a successful order with
the metadata `{wallet, proxyAddress, order_id, tx_hashes, market_id,
side, amount, symbol, price, strategy_id, plugin_name}`. This is how
OKX's Plugin Store leaderboard links trades back to a specific Skill
and wallet. The underlying Polymarket CLOB order itself does not carry
the tag — attribution is at the onchainos reporting layer, above the
CLOB.

Concretely for every `buy`/`sell`/`redeem` call:

```
polymarket-plugin buy --strategy-id pmbasket ...
polymarket-plugin sell --strategy-id pmbasket ...
polymarket-plugin redeem --strategy-id pmbasket ...
```

Read-only operations (`list-markets`, `get-market`, `get-positions`,
`balance`, `check-access`) do not need `--strategy-id` and do not
report.

The tag is **a fixed string**, not a per-basket identifier. Every
write operation issued by this Skill uses `pmbasket`. This keeps
attribution simple and reliable across sessions without relying on the
agent to compute stable identifiers.

**If the user later upgrades `polymarket-plugin` to a version that
dropped `--strategy-id`**, surface this to the user explicitly rather
than silently placing untagged orders:
> "The installed polymarket-plugin version no longer accepts
> `--strategy-id`. Orders will be placed correctly but may not count
> toward pmbasket's Plugin Store leaderboard attribution. Proceed
> anyway?"

## Polymarket API Reference

This Skill delegates all Polymarket API interaction to the
`polymarket-plugin` binary (author: skylavis-sky, published in
`okx/plugin-store`). That plugin is a Rust CLI binary that wraps the
Polymarket Gamma and CLOB APIs and talks to the onchainos wallet for
signing. pmbasket never makes HTTP calls directly to Polymarket — it
only invokes `polymarket-plugin` CLI commands and reads their JSON
output.

This Skill does not re-document the polymarket-plugin API. If anything
below conflicts with the installed `polymarket-plugin` SKILL.md, defer
to the plugin — it is the canonical source.

**Commands this Skill uses:**

- `polymarket-plugin list-markets [--limit N] [--keyword TEXT] [--breaking] [--category sports|elections|crypto]`
  Browse active markets. Returns `question, condition_id, slug,
  end_date, active, accepting_orders, neg_risk, yes_price, no_price,
  yes_token_id, no_token_id, volume_24hr, liquidity` per market. Used
  in `basket-plan` step 1.
- `polymarket-plugin get-market --market-id <condition_id|slug>`
  Fetch full market detail including orderbook. Returns `question,
  condition_id, slug, end_date, fee_bps, tokens (outcome, token_id,
  price, best_bid, best_ask), volume_24hr, liquidity, last_trade_price`.
  Used in `basket-place` for price re-check and in `basket-rebalance`
  for current prices and liquidity assessment.
- `polymarket-plugin get-positions [--address <wallet>]`
  List the wallet's open positions. Returns per-position `title,
  outcome, size (shares), avg_price, initial_value, total_bought,
  cur_price, current_value, cash_pnl, percent_pnl, realized_pnl,
  percent_realized_pnl, redeemable, redeemable_note, mergeable,
  opposite_outcome, opposite_asset, event_id, event_slug, end_date`.
  Used in pre-flight, `basket-resume`, `basket-status`,
  `basket-rebalance`.
- `polymarket-plugin balance`
  Wallet USDC.e balance. Used in pre-flight.
- `polymarket-plugin check-access`
  Verify region is not Polymarket-restricted. Used in pre-flight.
- `polymarket-plugin buy --market-id <id> --outcome <yes|no|label> --amount <usdc> [--price <0-1>] [--order-type GTC|FOK] [--post-only] [--expires <unix_ts>] [--round-up] [--strategy-id pmbasket]`
  Place a buy. `--amount` is in USDC.e dollars. `--outcome` is the
  label (`yes`, `no`, or candidate name for multi-outcome markets) —
  the plugin resolves the tokenID internally. Used in `basket-place`.
- `polymarket-plugin sell --market-id <id> --outcome <yes|no|label> --shares <n> [--price <0-1>] [--order-type GTC|FOK] [--post-only] [--strategy-id pmbasket]`
  Sell shares. `--shares` is in outcome tokens, not USDC — the agent
  must convert "$X worth" to shares by dividing by the current best
  bid. Used in `basket-rebalance-execute` for take-profit and cut-loss.
- `polymarket-plugin cancel --order-id <id>`
  Cancel a resting order. Used rarely.
- `polymarket-plugin redeem --market-id <id> [--strategy-id pmbasket]`
  Claim payout from a resolved winning position. Used when the user
  has resolved positions and asks to redeem.

All of these are subprocess calls. The plugin returns JSON; parse it.
Errors (insufficient balance, market closed, slippage, minimum-size
rejections) come back as structured error responses — see the
Error Handling table.

**Key concepts (from polymarket-plugin):**

- `condition_id` is the market identifier (hex or slug). `--market-id`
  accepts either.
- Each outcome (yes/no or candidate name) has its own `token_id`. For
  a binary market: `yes_token_id` and `no_token_id`. pmbasket does not
  need to handle token_ids directly — it passes `--outcome yes` or
  `--outcome no` and the plugin resolves it.
- `price` is probability in [0, 1], tick size 0.01 (or tighter for
  some markets — the plugin handles this).
- USDC.e (bridged USDC on Polygon, `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`)
  is the collateral.
- Trading modes: `eoa` (direct signing, requires on-chain approvals)
  or `proxy` (POLY_PROXY gasless). The user sets a default via
  `polymarket-plugin switch-mode`; pmbasket should not override unless
  asked.

## Commands

### basket-plan

Build a proposed basket from the user's natural-language theme.
**Does not place any bets.**

**When to use:** User describes an event-level view and wants to spread
a small amount across related markets. Always run before `basket-place`.

**Inputs parsed from natural language:**

- `theme` — free-form string: "FOMC May 2026 dovish", "CPI hot", etc.
- `side` — `YES` or `NO` (inferred from theme wording unless explicit)
- `perTicketUsd` — default $5, min $1, max $30
- `maxTickets` — default 10, max 15
- `minLiquidityUsd` — default $10,000

**Agent execution steps:**

1. Discover candidate markets via `polymarket-plugin list-markets`:
   - Extract 2-4 salient keyword tokens from the user's theme.
   - Run `polymarket-plugin list-markets --keyword "<first_keyword>" --limit 50`
     and, if the theme has a clear category, pair it with
     `--category crypto|sports|elections`. For theme-style queries
     with no obvious category keyword, also try
     `polymarket-plugin list-markets --breaking --limit 20` to catch
     topical events.
   - Merge results from these calls and dedupe by `condition_id`.
   - Total call budget for discovery: at most 3 `list-markets` calls.
2. Extract candidate markets from the JSON output. Each market has:
   `question, condition_id, slug, end_date, active, accepting_orders,
   neg_risk, yes_price, no_price, yes_token_id, no_token_id,
   volume_24hr, liquidity`. Everything needed for filtering and
   ranking is here — **do not call `get-market` per candidate** in
   this step; that comes later in `basket-place` for the final price
   re-check.
3. **Filter** candidates down to those that satisfy all of:
   - `active == true` and `accepting_orders == true`.
   - `liquidity >= minLiquidityUsd`. If `liquidity` is missing or
     zero but `volume_24hr` is present, fall back to
     `volume_24hr >= minLiquidityUsd`. If both are missing for a
     candidate, drop it.
   - `end_date` is in the future.
   - Market is binary (has both `yes_token_id` and `no_token_id`).
     Multi-outcome events (where `--outcome` would be a candidate
     name like `trump`, `republican`) are out of scope for pmbasket
     v1 — drop them and note in the plan summary ("N multi-outcome
     markets filtered out — pmbasket v1 supports binary markets only").
   - `neg_risk: true` is fine — binary per market still holds; just
     preserve the flag if any later command needs it.
4. **Score** remaining candidates with this **specific deterministic
   procedure**:
   - Split the user's theme into lowercase keyword tokens. Drop very
     common English words. Use **exactly this stop-words set** to keep
     the procedure reproducible:
     `{the, a, an, will, would, is, are, be, been, to, of, on, in, by,
     for, and, or, not, no, yes}`. Do not extend this set.
   - For each candidate market, compute
     `keywordMatches = number of theme tokens that appear as substrings
     in the market's question text (case-insensitive)`.
   - Set `relevanceScore = keywordMatches`. Ties are broken by higher
     liquidity. Do not use any subjective judgement — this score is
     mechanical.
   - Drop candidates with `keywordMatches == 0` (zero relevance).
5. **Detect side conflicts.** For each surviving candidate, check
   whether the market's question phrasing is aligned or opposed to the
   user's thesis direction:
   - The user's thesis is expressed by their theme + their side. If
     the theme is "FOMC dovish" and side = YES, the user is betting
     that dovish-related questions resolve true.
   - A market whose question is a **direct positive statement of the
     thesis** ("Will the Fed be dovish?", "Will they cut rates?") is
     **aligned** — bet the user's stated side.
   - A market whose question **negates the thesis** ("Will the Fed be
     hawkish?", "Will they hold rates?") is **opposed** — betting the
     user's stated side is a contradictory bet.
   - If the agent detects an opposed market, mark the ticket with
     `sideConflict = true`. Do not automatically flip the side. Show
     the conflict clearly in the dry-run plan so the user can remove
     or flip that ticket manually.
   - Agent judgement is allowed here (this is natural-language
     interpretation), but prefer conservative behaviour: if unsure
     whether a market is aligned or opposed, mark it conflicted and
     let the user decide.
6. Sort surviving candidates by `relevanceScore` descending, then
   liquidity descending. **Truncate** to `maxTickets` (or fewer if
   the filter removed more).
7. For each surviving candidate, build a ticket:
   - `market_id` = the market's `condition_id` (or the `slug` — both
     work with `polymarket-plugin buy --market-id`)
   - `outcome` = `"yes"` if the user's side is YES, `"no"` if NO.
     `polymarket-plugin buy` takes `--outcome yes|no` directly; it
     resolves the token_id internally. pmbasket does not handle
     token_ids at all — it only passes `--outcome`.
   - `priceAtPlan` = `yes_price` (if side=YES) or `no_price`
     (if side=NO), both float in [0, 1] returned by `list-markets`.
   - `sizeUsd` = `perTicketUsd` (this becomes `--amount` for buy)
   - `sideConflict` = as computed in step 5
   - `question`, `slug`, `end_date` — carried through for user-facing
     display
8. Present the plan to the user, clearly labeled **DRY-RUN PLAN —
   no bets placed**. Include:
   - `ticketCount` and `totalExposureUsd = perTicketUsd × ticketCount`
   - `maxLossUsd` (worst case: every ticket loses = `totalExposureUsd`)
   - Each ticket's `question`, `side` (YES/NO from user's view),
     `priceAtPlan`, `relevanceScore`
   - **A separate warning section** listing any tickets with
     `sideConflict = true`, with a one-line explanation per ticket
     ("this market asks about HAWKISH, your thesis is DOVISH; betting
     YES here is betting against your own thesis"). Ask the user to
     either flip the side, remove the ticket, or acknowledge the
     conflict before proceeding.
   - A summary of filters that removed candidates ("N candidates
     filtered: liquidity=X, resolved=Y, off-theme=Z")
   - A short "basket label" the user can use to refer to this basket
     later — use the first 4 lowercase keyword tokens of the theme
     joined by `-` (e.g. `fomc-may-2026-dovish`). This label is for
     human reference only (see Attribution section for why there is
     no on-order tag).

**Critical: the agent must never fabricate tickets, invent markets not
returned by `polymarket-plugin list-markets`, or exceed the caps.
Always show the plan to the user before placing bets. Never place bets
inside the `basket-plan` command — that is `basket-place`'s job.**

### basket-place

Execute the plan produced by `basket-plan`.

**When to use:** Only after `basket-plan` has been shown to the user in
the same session and the user has explicitly confirmed ("place it", "go
live", or equivalent).

**Mandatory pre-execution checks (abort if any fails):**

1. Dry-run flag off (user explicitly went live this session).
2. The basket was built by `basket-plan` in this session — never
   hand-constructed by the agent on the fly.
3. `totalExposureUsd` ≤ $300 and every `ticket.sizeUsd` ≤ $30.
4. **Re-fetch current prices** for each market in the basket by
   calling `polymarket-plugin get-market --market-id <slug_or_condition_id>`
   per ticket. Extract the `tokens[]` array; find the token matching
   the ticket's `outcome` (`yes` or `no`); read its `price` (or
   midpoint of `best_bid` / `best_ask`). Compare to `priceAtPlan`.
   If the drift is **`|currentPrice − priceAtPlan| ≥ 0.05`** (5 cents
   on the [0,1] scale) **OR `|currentPrice − priceAtPlan| / priceAtPlan ≥ 30%`**,
   whichever triggers first, pause and ask the user whether to proceed
   at the new price, skip that ticket, or cancel the whole batch.
   These thresholds are calibrated for prediction-market price
   dynamics — they fire on meaningful directional moves, not routine
   noise.
5. Present a **final one-line confirmation** and wait for a clear
   "yes":
   > Placing {ticketCount} bets on '{theme}' ({side}), total exposure
   > ${totalExposureUsd}, max loss ${maxLossUsd}. Confirm?

**Execution:**

For each ticket in the basket, invoke:

```
polymarket-plugin buy \
  --market-id <ticket.market_id> \
  --outcome <ticket.outcome> \
  --amount <ticket.sizeUsd> \
  --price <ticket.priceAtPlan> \
  --order-type GTC \
  --strategy-id pmbasket
```

Notes:

- **`--amount` is USDC.e dollars**, not shares. A $5 ticket is
  `--amount 5`. The plugin handles share-size conversion internally.
- **`--price` is explicit**, matching `priceAtPlan` (or the post-drift
  price the user agreed to). Never call `buy` without `--price` from
  this Skill — that would become a FOK market order with unbounded
  slippage. pmbasket always places resting limit orders at the
  planned price.
- **`--order-type GTC`** keeps the order on the book until filled or
  cancelled. For time-boxed baskets (e.g. resolving within 24h) the
  agent may offer `--expires <unix_ts>` — this auto-sets to GTD.
- **`--strategy-id pmbasket`** — mandatory; this is the leaderboard
  attribution signal (see Attribution section).
- **Minimum-size errors** — if the plugin returns an error about
  divisibility (`"rounds to 0 shares"`) or share minimum (`"below this
  market's minimum of N shares"`), surface the error to the user,
  state the minimum in both shares and ≈USDC, and ask once whether
  to retry that ticket with `--round-up`. Never auto-escalate.
- **Approval** — on first buy in EOA mode the plugin auto-submits a
  USDC.e `approve` transaction (for exactly the order amount). This
  fires without a separate onchainos confirmation gate; the agent's
  user-facing confirmation before calling `buy` is the only safety
  gate. Tell the user this is happening on their first buy.

If a single ticket is rejected, surface the exact error and continue
with the remaining tickets. Report skipped tickets in the final
summary. Do not silently retry. Do not silently skip.

Final summary: placed count, skipped count, total spent, average price,
and per-ticket `order_id`.

### basket-rebalance

Compare an existing basket's tickets to current market prices and
suggest action per ticket — hold, take profit, or cut loss.

**When to use:** User asks "how is my basket doing", "should I take
profit on anything", "should I cut losses".

**Agent execution steps:**

1. Identify which basket to operate on:
   - If the user gave a basket label (e.g. `fomc-may-2026-dovish`),
     the label's keyword tokens match against the user's open
     positions' `title` text (from `get-positions`). Group matching
     positions that share an `event_id` or have similar `end_date`
     (within a ~30-day window) — that group is one basket.
   - If the user has a single obvious cluster of positions sharing an
     event or theme, use it.
   - Otherwise list all open positions and ask the user which ones
     they want to treat as the basket.
2. For current state, `polymarket-plugin get-positions` already
   returns `cur_price`, `current_value`, and `cash_pnl` per position.
   If a specific orderbook view is needed (e.g. to assess SELL
   liquidity), call `polymarket-plugin get-market --market-id <slug>`
   for that one market.
3. For each ticket in the basket, compute the action using
   these **explicit rules** (Polymarket prices are in the [0, 1]
   range, where price = implied probability of the token resolving
   to $1):
   - If the market has resolved → `action = "resolved"`; show realized
     PnL (price of 1.0 means the ticket's side won, 0.0 means it lost).
   - Else if the ticket is on the YES side and the current YES price
     has moved **at least half of the remaining distance toward 1.0**
     compared to `priceAtPlan` → `action = "take_profit"`. Formally:
     `currentYes >= priceAtPlan + 0.5 × (1.0 - priceAtPlan)`.
     Suggest closing half the position.
     Example: bought YES at 0.4 → take profit when YES ≥ 0.7.
   - Symmetrically for NO-side tickets: if
     `currentNo >= priceAtPlan + 0.5 × (1.0 - priceAtPlan)` →
     `take_profit`.
   - Else if the ticket's side price has dropped to **≤ 50% of
     `priceAtPlan`** → `action = "cut_loss"`. Suggest closing the
     position.
     Example: bought YES at 0.4 → cut loss when YES ≤ 0.2.
   - Otherwise → `action = "hold"`; no action suggested.
4. Present the actions to the user. For each ticket show: `action`,
   current price vs plan price, price change (absolute, not %), and a
   short reason ("moved >50% of remaining distance to resolution" /
   "price halved vs entry" / "within tolerance").
5. Ask the user explicitly which suggestions to act on — this is a
   **planning** step, not an execution step. Actual trades go through
   `basket-rebalance-execute` (below) with explicit per-ticket consent.

### basket-rebalance-execute

Execute a subset of rebalance actions approved by the user.

**When to use:** After `basket-rebalance` has shown suggestions and the
user picks which ones to act on.

**Mandatory pre-execution checks:**

1. User has explicitly named which markets (by `market_id`/slug or by
   question) to act on — no batch approval without per-ticket
   confirmation.
2. For each action, re-fetch current price and verify the drift since
   the rebalance plan was shown is within tolerance: no more than 0.05
   absolute OR 30% relative (whichever is tighter). If exceeded,
   surface the new price and ask the user to re-confirm.
3. Caps still apply — any new entries respect the $30/ticket, $300
   total-exposure caps.

**Execution:** For each approved action:

Before each SELL, run `polymarket-plugin get-market --market-id <id>`
and assess liquidity on the outcome being sold (from the matching
entry in `tokens[]`):

- `best_bid` is null or 0 → warn "No active buyers; sell may not fill."
- `best_bid < 0.5 × last_trade` → warn "Best bid is less than half the
  last trade price — you'd sell at a significant loss from recent
  levels."
- `best_ask − best_bid > 0.15` → warn "Wide spread; poor fill likely."
- market `liquidity < 1000` → warn "Thin market; large sells will
  have high price impact."

Present the user with `best_bid`, `last_trade`, `liquidity`, and
estimated USDC received (`shares × best_bid`). Require explicit
user confirmation. Skip the liquidity check only if the user
provided an explicit `--price` — they've already set an acceptable
price.

Then:

- **take_profit** — convert "sell 50% of the position" to a shares
  count: the `size` field on the position (from `get-positions`) is
  shares held; take 50% of that (or 100% for full take-profit). Run:
  ```
  polymarket-plugin sell \
    --market-id <ticket.market_id> \
    --outcome <ticket.outcome> \
    --shares <computed_shares> \
    --price <target_price> \
    --order-type GTC \
    --strategy-id pmbasket
  ```
  `polymarket-plugin sell` takes `--shares` in outcome tokens, not
  USDC. Polymarket has no separate "close position" endpoint; selling
  your tokens is how exposure is reduced.
- **cut_loss** — same as take-profit but default to 100% of the
  position's `size` field by default.
- **hold** — no-op (should not appear in the approved list; if it
  does, skip it).
- **resolved** — call `polymarket-plugin redeem --market-id <id>
  --strategy-id pmbasket` to claim the payout. On Polymarket,
  redemption is not automatic; the user has to call redeem (or the
  Relayer if using gasless mode).

If a SELL order is rejected (e.g. the orderbook has no bid at or near
the target price), surface the exact error from the plugin and offer
alternatives: (a) lower `--price`, (b) switch to `--order-type FOK`
(market order — warn about slippage), or (c) skip this action. Do
not silently retry at a different price.

### basket-status

Query the current state and PnL of an existing pmbasket basket.

**When to use:** User asks "how is my basket doing", "what's my PnL".

**Identifying the right basket:** Baskets are reconstructed from
placement-time clustering, not from a per-order tag (Polymarket has no
order tags — see Attribution section). If the user gives a basket
label, match its keyword tokens against the `question` text of their
open positions and take the matching cluster placed within a ~5-minute
window. If the user has one obvious recent cluster, use it. Otherwise
ask the user which cluster to check.

**Execution:** Fetch the user's positions with
`polymarket-plugin get-positions`. For each position in the chosen
cluster, the output already includes `cur_price`, `current_value`,
`cash_pnl`, `percent_pnl`, and `end_date` — no further lookups
needed. Return: open vs resolved count (look at `redeemable`),
aggregate mark-to-market PnL, days until earliest `end_date`, and
per-ticket PnL summary.

### basket-resume

Reattach to existing pmbasket-style baskets across sessions.

**When to use:** User comes back after closing the session and asks
"how's my Polymarket basket doing" or "what positions do I have".

**Execution:**

1. Fetch open positions with `polymarket-plugin get-positions`.
2. Since `onchainos wallet report-plugin-info` attribution is tracked
   server-side (not in `get-positions` output), pmbasket **cannot**
   directly read which positions came from pmbasket vs direct use.
   Reconstruct baskets **heuristically** using the data
   `get-positions` does expose:
   - Group positions by **shared event** (`event_id` or `event_slug`
     when multiple outcomes in the same event are held) and by
     **similar `end_date`** (within ~30 days) — a basket is usually a
     cluster of markets resolving around the same event window.
   - Within each group, compute common keywords across `title` fields
     to produce a human-readable label.
3. Present each inferred basket as a brief row: the top market
   `title`s (abbreviated), position count, total `initial_value`,
   current aggregate `cash_pnl`. **Tell the user this is a heuristic
   reconstruction, not a system-of-record lookup** — positions opened
   via the Polymarket UI directly or via other Skills will show up
   too.
4. Let the user identify which group they mean by pointing at a top
   market title or stating their original theme. Do not ask the user
   to recall a basket hash or tag — there are none.
5. Once identified, run `basket-status` or `basket-rebalance` on the
   selected group.

Note: pmbasket's "baskets" are agent-side logical groupings. The
source of truth is whatever `polymarket-plugin get-positions`
returns. If the user has positions from non-pmbasket sources, those
will appear in the same query — be clear with the user about the
limits of this heuristic.

## Examples

### Example 1 — FOMC dovish basket, dry-run only

**User:** "I think the May FOMC will be dovish. Small $5 bets across
related markets."

**Agent:**

1. Run `polymarket-plugin list-markets --keyword "FOMC"` to discover
   matching markets.
2. Run `basket-plan` with `theme="FOMC May 2026 dovish"`, `side=YES`,
   `perTicketUsd=5`, `maxTickets=10` — `list-markets --keyword "FOMC"`
   then filter, rank, truncate.
3. Present the plan labeled "DRY-RUN PLAN".
4. End with: "No bets placed. Reply 'place it' to execute."

### Example 2 — CPI contrarian, live execution

**User:** "CPI will come in hot. $10 on YES across CPI markets, place
it."

**Agent:**

1. Run `basket-plan` with the parsed inputs (`list-markets --keyword
   "CPI"` + `--category crypto` if relevant).
2. Re-fetch current prices per ticket via
   `polymarket-plugin get-market --market-id <slug>`.
3. Present the final one-line confirmation.
4. Wait for explicit "yes".
5. Run `basket-place`: for each ticket, call
   `polymarket-plugin buy --market-id <slug> --outcome yes --amount 10
   --price <priceAtPlan> --order-type GTC --strategy-id pmbasket`.
6. Report each returned `order_id` and tell the user they can ask
   "how is my CPI basket doing" later.

### Example 3 — User asks beyond caps

**User:** "Put $100 on each of 25 markets about the election"

**Agent:**

1. Refuse to silently clamp. Explain: per-ticket cap is $30, max
   tickets is 15, total exposure cap is $300.
2. Offer a compliant alternative: "I can place up to $20/ticket × 15
   tickets (= $300 total), or $30/ticket × 10 tickets (= $300), or
   any smaller variation. Which?"
3. Only re-plan after the user chooses.

### Example 4 — Mid-basket rebalance with profit

**User:** "Check my FOMC basket, take profit on anything that moved."

**Agent:**

1. Run `basket-rebalance` with the original basket and fresh market
   prices.
2. Present each ticket's action. For example: "Market X: bought YES
   at 0.4, now 0.75 — crossed 50% of the remaining distance to 1.0 →
   suggested action: `take_profit` at 50% of position". And: "Market
   Y: bought YES at 0.6, now 0.55 — within tolerance → `hold`".
3. Ask which to act on — **do not batch-approve**.
4. User says "take profit on X".
5. Run `basket-rebalance-execute` with only that market's slug.

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| "polymarket-plugin not installed" | Required dependency plugin missing | Tell user: `npx skills add okx/plugin-store --skill polymarket-plugin` |
| "No candidate markets found" | Theme too narrow or misspelled, all resolved, or all illiquid | Ask user to broaden the theme or lower the liquidity threshold. Suggest `list-markets --breaking` or a `--category` filter. |
| Filtering removed all candidates | All discovered markets failed liquidity/binary/end_date filter | Quote which filters fired; widen the theme or lower `minLiquidityUsd` |
| User asked for caps exceeding hard limits | perTicketUsd > $30, maxTickets > 15, or implied total > $300 | Refuse; offer a compliant alternative (see Example 3) |
| Plan tickets array is empty | All candidates filtered out | Widen the theme or the filters; re-plan |
| Basket composition differs between two `basket-plan` runs | `list-markets` returns live data; new markets appear, some resolve, liquidity shifts | Expected — the plan is deterministic given a fixed candidate set, but the candidate set is live. Tell the user; re-show the plan. |
| `polymarket-plugin` CLI flags/output differ from what this Skill expects | Plugin version drift | Defer to the installed plugin's SKILL.md. If a semantic capability (positions query, `--strategy-id`, etc.) is entirely gone, surface this to the user. |
| "Insufficient balance" on `buy` | USDC.e balance < totalExposureUsd | Show required USDC.e; direct user to `polymarket-plugin deposit`; do not silently reduce ticket sizes |
| Divisibility / minimum-size error on `buy` | Order amount too small for share granularity | Surface the error (which includes the computed minimum). Ask once whether to retry with `--round-up`. Never auto-escalate. |
| "Market already resolved" mid-execution | Event resolved between plan and place | Skip that ticket; continue with remaining; report skip in final summary |
| Price drifted beyond tolerance mid-execution | Market moved ≥ 0.05 absolute or ≥ 30% relative between plan and place | Pause; surface new price from `get-market`; ask user whether to proceed, skip, or cancel |
| Order rejected by CLOB | Market closed, slippage, tick-size violation, post-only would take liquidity, etc. | Surface the plugin's exact error. Continue with remaining tickets. Do not silently retry. |
| Cloudflare-style rejection on order POST | Upstream anti-abuse layer may reject writes from some IPs (reported by third-party tooling, not documented by Polymarket officially) | Surface the exact error; suggest retrying after a short delay. Do not attempt to bypass. |
| SELL rejected with no liquidity | Pre-sell liquidity check missed or market thin | Surface `best_bid` / `liquidity`; offer: lower `--price`, switch to `--order-type FOK` (warn slippage), or skip |
| `redeem` needed | Position shows `redeemable: true` in `get-positions` output | Offer to run `polymarket-plugin redeem --market-id <id> --strategy-id pmbasket` for the user |

## Security Notices

**Risk level: advanced.** This Skill places multiple real on-chain
prediction-market bets. Each ticket is binary — it can resolve to zero.
A basket reduces variance but does not eliminate directional risk.

**Hard safety limits (enforced in this Skill's pre-flight and
`basket-plan` / `basket-place` rules):**

- Maximum **$300 total exposure** per basket.
- Maximum **$30 per ticket**.
- Maximum **15 tickets** per basket.
- Illiquid markets (< $10,000 liquidity by default) filtered out.
- Stale plans (price drifted ≥ 0.05 absolute or ≥ 30% relative
  since plan was built) trigger a mandatory user confirmation loop
  at execution time.

These limits are documented in SKILL.md and enforced by the agent
following the rules in `basket-plan` and `basket-place`. The agent
must refuse to override them even on explicit user request.

**Behavioral safety:**

- **Dry-run mode by default** on every new intent.
- **Mandatory price re-check** before each ticket is placed.
- **Explicit final confirmation** before any bet batch.
- **Per-ticket rebalance approval** — no batch-approve for rebalance
  actions; each suggestion must be named by the user to execute.
- **Rule-based planning.** Basket construction follows the explicit
  filter-rank-truncate procedure documented in `basket-plan`. The
  scoring is a mechanical count of theme-token matches, not a
  subjective judgement. The agent must follow the documented steps
  and must not fabricate tickets or invent markets that
  `polymarket-plugin list-markets` did not return.

**Circuit breakers (enforced by this Skill's pre-flight):**

- **Same-theme lockout.** If the user has open positions in the last
  7 days whose market questions overlap with the user's current theme
  (by the same keyword-match rule used for ranking), warn the user
  before opening a second basket.
- **Daily loss stop.** If cumulative realized PnL from all closed
  Polymarket positions over the last 24 hours is worse than −$30,
  refuse to open a new basket until the next UTC day. Note: because
  Polymarket has no per-order tag, this counts all closed positions,
  not just those from prior pmbasket runs — the filter is intentionally
  conservative (errs on the side of halting).

**What this Skill does not do:**

- It does not hold or touch private keys. All signing happens inside
  `polymarket-plugin` via the onchainos wallet (typically via
  Agentic Wallet TEE for OKX users).
- It does not collect, store, or transmit user wallet addresses,
  balances, or betting history to any external server.
- It makes no external API calls of its own (`api_calls: []` in
  `plugin.yaml`). All Polymarket API traffic flows through
  `polymarket-plugin` per its own declared endpoints.

**Geographic restrictions.** Polymarket's Terms of Service prohibit
residents of the United States, France, Singapore, and several other
jurisdictions from trading — both via the UI and via the API/SDK,
including through agents. Users in restricted jurisdictions must not
use this Skill for live trading. If a user discloses that they are in
a restricted jurisdiction, the agent must refuse to place live bets
and explain why. Market-data viewing is not restricted. Authoritative
and up-to-date geo rules are maintained by `polymarket-plugin`
in `geoblock.md`.

**Disclaimer:** Prediction market outcomes are binary — each ticket can
result in a 100% loss for that ticket. A basket reduces variance but
not directional risk: if the thesis is wrong, most or all tickets can
resolve against the user. Nothing in this Skill is financial,
political, or investment advice.

## Skill Routing

- **For a single Polymarket bet (no basket)** → use the Polymarket basic
  plugin (`polymarket-plugin`) directly.
- **For portfolio / balance overview across chains** → use OKX's
  portfolio skills from Onchain OS.
- **For DEX swaps on other chains** → use OKX DEX skills.
