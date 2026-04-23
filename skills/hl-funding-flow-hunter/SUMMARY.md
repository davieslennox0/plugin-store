# hl-funding-flow-hunter

## Overview

HL Funding Flow Hunter is a guarded Hyperliquid strategy scanner for funding-rate and flow-based perpetual futures setups.

Core operations:

- Scan public Hyperliquid market data for funding, volume, and open interest notional candidates
- Rank candidates with risk flags
- Prepare low-leverage isolated order previews
- Execute only through `hyperliquid-plugin` after explicit confirmation
- Attribute every write operation with `--strategy-id hl-funding-flow-hunter`

## Prerequisites

- `hyperliquid-plugin` installed from the OKX Plugin Store
- Python 3 for the read-only scanner script
- A registered Hyperliquid account
- Available USDC margin on Hyperliquid
- User-defined risk budget, stop loss, take profit, and maximum holding time

## Quick Start

Install the dependency:

```bash
npx skills add okx/plugin-store --skill hyperliquid-plugin --yes
```

Register and check setup:

```bash
hyperliquid register
hyperliquid quickstart
```

Scan funding candidates:

```bash
python3 ./scripts/scan_funding.py --top 5
```

Preview a guarded order:

```bash
hyperliquid order --coin <COIN> --side sell --size <SIZE> --type market --leverage 2 --isolated --sl-px <SL> --tp-px <TP> --dry-run --strategy-id hl-funding-flow-hunter
```

Execute only after explicit user confirmation:

```bash
hyperliquid order --coin <COIN> --side sell --size <SIZE> --type market --leverage 2 --isolated --sl-px <SL> --tp-px <TP> --confirm --strategy-id hl-funding-flow-hunter
```

Close only after explicit user confirmation:

```bash
hyperliquid close --coin <COIN> --confirm --strategy-id hl-funding-flow-hunter
```
