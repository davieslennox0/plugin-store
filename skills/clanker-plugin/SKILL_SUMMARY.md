
# clanker -- Skill Summary

## Overview
The clanker skill enables deployment and management of ERC-20 tokens through the Clanker platform on Base and Arbitrum networks. It provides comprehensive token lifecycle management including deployment via REST API, creator-based search functionality, reward claiming from liquidity provider fees, and real-time token information retrieval with built-in security scanning.

## Usage
Install with `npx skills add okx/plugin-store --skill clanker-plugin --global` and ensure `onchainos` is logged in. Use `deploy-token` to deploy directly on-chain via the Clanker V4 factory — no API key required.

## Commands
| Command | Description |
|---------|-------------|
| `list-tokens` | List recently deployed Clanker tokens with pagination |
| `search-tokens --query <address\|username>` | Search tokens by creator address or Farcaster username |
| `token-info --address <addr>` | Get on-chain token metadata and price information |
| `deploy-token --name X --symbol Y` | Deploy new ERC-20 token directly on-chain via Clanker V4 factory (requires confirmation) |
| `claim-rewards --token-address <addr>` | Claim LP fee rewards for token creators (requires confirmation) |

## Triggers
Activate when users want to deploy tokens with phrases like "launch token on Clanker", "create token on Base", search for tokens with "show tokens by creator", or manage rewards with "claim my Clanker rewards". Also triggered for listing recent Clanker launches or getting token information.
