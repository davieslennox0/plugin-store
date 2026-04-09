
# polymarket — Skill Summary

## Overview
This skill enables trading prediction markets on Polymarket — a decentralized CLOB-based prediction market on Polygon. It supports buying/selling YES/NO outcome tokens, querying market data and prices, viewing open positions and orders, and cancelling orders. Authentication uses a locally-generated k256 signing key; no private key passthrough is required.

## Usage
Install the plugin and connect your wallet with `onchainos wallet login`. All write operations (buy, sell, cancel) show a preview and require explicit user confirmation before submitting.

## Commands
| Command | Description |
|---------|-------------|
| `list-markets` | Search and filter prediction markets by keyword or category |
| `get-market` | Fetch prices, liquidity, and details for a specific market |
| `get-positions` | View open YES/NO token positions for the connected wallet |
| `get-orders` | View open limit orders |
| `buy` | Buy YES or NO outcome tokens (market or limit order) |
| `sell` | Sell YES or NO outcome tokens |
| `cancel` | Cancel an open limit order |

## Triggers
Activate when users want to trade prediction markets, buy or sell outcome tokens, check market odds, view their Polymarket positions, or cancel orders. Key phrases include "polymarket", "prediction market", "buy YES", "buy NO", "outcome token", and "cancel order".
