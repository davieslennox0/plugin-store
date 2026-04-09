# raydium — Skill Summary

## Overview
This skill enables token swaps, price queries, and pool info lookups on Raydium AMM on Solana mainnet. It supports getting swap quotes, executing swaps via the Raydium transaction API, querying token prices, and browsing liquidity pools.

## Commands

| Command | Description |
|---------|-------------|
| `get-swap-quote` | Get expected output amount, price impact, and route for a swap (read-only) |
| `swap` | Execute a token swap on Raydium (write) |
| `get-price` | Get token price in USD (read-only) |
| `get-token-price` | Get detailed price info for a token mint (read-only) |
| `get-pools` | Get pool info for a token pair (read-only) |
| `get-pool-list` | List Raydium liquidity pools (read-only) |

## Triggers
Activate when users want to swap tokens on Raydium, get a Raydium swap quote, check Raydium pool info, or query token prices on Solana. Also triggered by: "swap on raydium", "raydium swap", "raydium price", "raydium pool", "get swap quote raydium", "raydium dex", "swap solana raydium".
