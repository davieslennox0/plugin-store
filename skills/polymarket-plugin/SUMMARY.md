**Overview**

Polymarket is a prediction market protocol on Polygon where users trade YES/NO outcome shares of real-world events. This skill lets you browse markets (including 5-minute crypto up/down markets), buy and sell outcome shares, check positions, cancel orders, redeem winning tokens, and optionally set up a proxy wallet for gasless trading.

**Prerequisites**
- onchainos CLI installed and logged in with a Polygon address (chain 137)
- USDC.e on Polygon for trading (≥ $5 recommended for a first test trade)
- POL for gas in EOA mode (default; each buy/sell does an on-chain approve) — skip with one-time POLY_PROXY setup
- Accessible region — Polymarket blocks the US and OFAC-sanctioned jurisdictions

**Quick Start**
1. Verify your region is not restricted: `polymarket-plugin check-access`
2. Check balances on both EOA and proxy wallets: `polymarket-plugin balance`
3. (Optional, recommended) Switch to gasless mode by creating a proxy wallet and funding it: `polymarket-plugin setup-proxy` then `polymarket-plugin deposit --amount 50`
4. Browse active markets by keyword, or list 5-minute crypto up/down markets: `polymarket-plugin list-markets --keyword "trump"` or `polymarket-plugin list-5m`
5. Get details and order book for a specific market: `polymarket-plugin get-market --market-id <SLUG>`
6. Buy YES or NO outcome shares at market price: `polymarket-plugin buy --market-id <SLUG> --outcome yes --amount 5`
7. Review your open positions and P&L: `polymarket-plugin get-positions`
8. Exit a position, or redeem winnings when the market resolves: `polymarket-plugin sell --market-id <SLUG> --outcome yes --amount 5` / `polymarket-plugin redeem --market-id <SLUG>`
