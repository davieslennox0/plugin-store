# pmbasket

## Overview

pmbasket turns a trader's one-sentence event view ("FOMC May 2026 will
be dovish", "CPI prints hot", "Trump tariff sticks") into a
liquidity-filtered, risk-capped basket of small bets across related
Polymarket markets. Discovery, filtering, ranking, and side-conflict
detection all happen before a single dollar is committed; every buy,
sell, and redeem flows through the `polymarket-plugin` CLI with a
fixed `--strategy-id pmbasket` tag for leaderboard attribution.

Core operations:

- Parse a natural-language event theme into a dry-run basket plan
- Discover candidate Polymarket markets via `polymarket-plugin list-markets` and filter by liquidity, `accepting_orders`, `end_date`, and binary-outcome constraint
- Rank candidates with a deterministic keyword-match score and flag side-conflicts where a market's phrasing contradicts the user's thesis
- Place per-ticket limit orders through `polymarket-plugin buy` after an explicit user confirmation
- Rebalance (take-profit, cut-loss, redeem) with per-ticket approval, or resume an existing basket heuristically across sessions

Tags: `polymarket` `prediction-markets` `basket` `event-driven` `agentic-wallet`

## Prerequisites

- Polymarket's Terms of Service restrict residents of the United States, France, Singapore, and several other jurisdictions from trading — enforced in pre-flight via `polymarket-plugin check-access`
- Supported chain: Polygon (Polymarket CLOB)
- Supported collateral: USDC.e (bridged USDC on Polygon, `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`), not native USDC
- onchainos CLI installed and wallet accessible (the `polymarket-plugin` dependency auto-injects its install steps)
- `polymarket-plugin` installed: `npx skills add okx/plugin-store --skill polymarket-plugin`
- A funded wallet with USDC.e on Polygon (deposit via `polymarket-plugin deposit` if needed)

## Quick Start

1. **Describe your event view in natural language**
   Tell the agent what you expect to happen. For example:
   "FOMC May meeting will be dovish, $5 YES across related markets" or
   "CPI prints hot — small NO bets across CPI markets". pmbasket starts
   every new intent in dry-run by default, so nothing is placed yet.

2. **Review the dry-run basket**
   The agent calls `polymarket-plugin list-markets` with keywords
   extracted from your theme, filters out illiquid / resolved / non-binary
   markets, and ranks the survivors by a mechanical keyword-match score.
   You'll see the ticket list, the basket label, total exposure, max loss
   at full drawdown, and any side-conflict warnings for markets whose
   phrasing contradicts your thesis direction. Hard caps ($300 per basket,
   $30 per ticket, max 15 tickets, $10k liquidity floor) are applied
   automatically — if your request exceeds them, the agent refuses and
   proposes a compliant alternative rather than silently clamping.

3. **Go live only after explicit confirmation**
   Reply "place it" (or "go live") to execute. For each ticket the agent
   re-fetches the current price via `polymarket-plugin get-market` — if
   the market has drifted beyond 0.05 absolute or 30% relative from the
   planned price, execution pauses for you to re-confirm. Every order is
   placed with `polymarket-plugin buy --strategy-id pmbasket` so it
   counts toward this Skill's leaderboard attribution at
   `onchainos wallet report-plugin-info`. First-time pmbasket sessions
   are capped at $5/ticket × 5 tickets regardless of your request, as a
   training-wheels safeguard.

4. **Rebalance, resume, or redeem**
   Ask "how is my basket doing" for per-ticket PnL. The rebalance engine
   tags each ticket with `take_profit` / `cut_loss` / `hold` / `resolved`
   based on explicit price-based rules, but never executes without your
   per-ticket approval — no batch approvals. Since Polymarket orders
   carry no on-chain tag, pmbasket reconstructs baskets heuristically
   across sessions (by shared `event_id`, near-same `end_date`, and
   keyword overlap) and tells you when a cluster might contain
   non-pmbasket positions.
