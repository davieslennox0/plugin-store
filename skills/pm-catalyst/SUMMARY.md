# pm-catalyst

## Overview

`pm-catalyst` is a Polymarket strategy skill that turns major catalysts and short-dated event setups into clear yes/no trade plans, with `catalyst` mode for simple first trades and `flash` mode for faster crypto-linked opportunities.

The default first step is a dry-run preview: the skill checks readiness, scores candidate markets, selects one understandable market, and shows the exact stake and maximum loss before any live order is allowed.

Core operations:

- Find major event or crypto-linked Polymarket opportunities with simple yes/no framing
- Build a preview-first trade plan with stake size, maximum loss, and clear event thesis
- Open and manage `catalyst` or `flash` positions through `polymarket-plugin` with `--strategy-id pm-catalyst`
- Review open orders, monitor odds, and redeem or close positions after resolution

Tags: `polymarket` `prediction-market` `events` `catalysts` `flash`

## Prerequisites

- OKX Onchain OS is installed and the user's Agentic Wallet is connected
- `polymarket-plugin` version `^0.4.10` is available in the environment
- The wallet holds USDC and can fund Polymarket through the existing plugin flow
- The user understands event-risk and binary-outcome market behavior

## Quick Start

1. Ask for a clear setup: `Find the best pm-catalyst trade around a major crypto event this week.`
2. Review the preview, then open a small first position: `Open the safest pm-catalyst trade with a 10 to 25 USDC stake.`
3. Use short-dated flow when appropriate: `Use pm-catalyst flash mode to find a short-dated crypto opportunity with a 5 USDC stake.`
4. Ask the agent to manage open orders, check odds, or redeem proceeds after resolution.
