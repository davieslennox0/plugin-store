# pmbasket — Plugin Store Skill

Natural-language event baskets on Polymarket. Describe an event thesis,
the Skill discovers related markets, filters by liquidity, and places a
risk-capped basket of small bets via `polymarket-plugin`, tagging each
trade with `--strategy-id pmbasket` so it counts on the Plugin Store
leaderboard.

## Install

```
npx skills add okx/plugin-store --skill pmbasket
```

## Requires

- `onchainos` CLI + unlocked wallet (auto-injected by `polymarket-plugin`)
- **`polymarket-plugin`** installed separately — this is the dependency
  that actually talks to Polymarket's Gamma / CLOB APIs and signs
  orders. Install:
  `npx skills add okx/plugin-store --skill polymarket-plugin`
- **USDC.e** (bridged USDC on Polygon, contract
  `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`) in the wallet
- Eligibility to trade on Polymarket (US / France / Singapore and
  certain other jurisdictions are restricted by Polymarket's Terms of
  Service — verified via `polymarket-plugin check-access`)

## Usage

Once installed, talk to any Onchain-OS agent in natural language:

> "FOMC May meeting will be dovish, $5 YES across related markets"

The agent will:
1. Discover matching markets via
   `polymarket-plugin list-markets --keyword "FOMC"`.
2. Filter by liquidity, `accepting_orders`, `end_date`, and
   binary-outcome constraint; rank by deterministic keyword-match score.
3. Show the DRY-RUN plan with the basket label, ticket list, max loss,
   and warnings for markets whose phrasing contradicts the thesis.
4. Execute only after you confirm, by calling
   `polymarket-plugin buy --market-id <slug> --outcome yes --amount 5
   --price <p> --order-type GTC --strategy-id pmbasket` per ticket.

## Safety

- Dry-run default; first session forces $5/ticket × 5 tickets training wheels
- Max $300 per basket / $30 per ticket / 15 tickets max
- $10,000 liquidity floor per market
- Mandatory price re-check before each order (tolerance: 0.05 absolute
  or 30% relative, whichever tighter)
- 24h realized-loss stop at −$30
- Pre-sell liquidity check (best_bid / spread / thin-market warnings)
- Rebalance requires per-ticket user approval (no batch-approve)
- Skill-only — `api_calls: []`, no binary, no external API calls
  originate from this Skill. All Polymarket traffic flows through
  `polymarket-plugin`.

## Attribution

Every write operation (`buy`, `sell`, `redeem`) passes
`--strategy-id pmbasket`. `polymarket-plugin` then reports to
`onchainos wallet report-plugin-info` with the order metadata so OKX's
Plugin Store Season 1 leaderboard can attribute trades to pmbasket
rather than aggregating them under plain polymarket-plugin usage.

## License

MIT — see `LICENSE`.

## Season 1 Developer Challenge

Submitted to the OKX Onchain OS Plugin Store Season 1 Developer
Challenge. All on-chain writes flow through `polymarket-plugin` as
required by challenge eligibility. See SKILL.md §Attribution for how
trades are tagged.
