# pm-5m-crypto-arena

## Overview

PM 5M Crypto Arena is a guarded trading co-pilot for Polymarket 5-minute crypto Up/Down markets.

Core operations:

- Check Polymarket access before any live trading path
- List nearby 5-minute BTC, ETH, SOL, or supported crypto markets
- Present a compact one-tap confirmation prompt
- Execute confirmed buys through `polymarket-plugin`
- Attribute every write operation with `--strategy-id pm-5m-crypto-arena`

## Prerequisites

- `polymarket-plugin` installed from the OKX Plugin Store
- Polymarket access allowed in the user's jurisdiction
- A configured wallet and Polymarket proxy setup
- USDC funding appropriate for the user's chosen stake

## Quick Start

Install the dependency:

```bash
npx skills add okx/plugin-store --skill polymarket-plugin --yes
```

Check access and setup:

```bash
polymarket-plugin check-access
polymarket-plugin quickstart
```

List active 5-minute markets:

```bash
polymarket-plugin list-5m --coin BTC --count 3
```

Preview a trade:

```bash
polymarket-plugin buy --market-id <conditionId> --outcome up --amount 5 --dry-run --strategy-id pm-5m-crypto-arena
```

Execute only after explicit user confirmation:

```bash
polymarket-plugin buy --market-id <conditionId> --outcome up --amount 5 --strategy-id pm-5m-crypto-arena
```
