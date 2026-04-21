## Overview

Hyperliquid is a high-performance on-chain perpetuals DEX on its own L1, settling in USDC. This skill lets you deposit from Arbitrum, trade perps & spot (market/limit, TP/SL, leverage), close positions, transfer between perp/spot, and withdraw back to Arbitrum.

## Prerequisites
- onchainos CLI installed and logged in
- USDC on Arbitrum (chain 42161) to deposit into Hyperliquid
- A small amount of ETH on Arbitrum for gas

## Quick Start
1. Check your current state and get a guided next step: `hyperliquid quickstart`
2. If you see `status: no_funds` / `low_balance` — get your deposit address and top up USDC on Arbitrum: `hyperliquid address`
3. If you see `status: needs_deposit` — bridge Arbitrum USDC into Hyperliquid (arrives in 2–5 min): `hyperliquid deposit --amount 50 --confirm`
4. One-time: bind your signing address so orders can be signed: `hyperliquid register`
5. If you see `status: ready` — place your first perpetual order: `hyperliquid order --coin BTC --side buy --size 0.001 --leverage 5 --confirm`
6. If you see `status: active` — review positions and attach stop-loss / take-profit: `hyperliquid positions` → `hyperliquid tpsl --coin BTC --sl-px 60000 --tp-px 80000 --confirm`
7. Close a position: `hyperliquid close --coin BTC --confirm`
8. Withdraw USDC back to Arbitrum: `hyperliquid withdraw --amount 50 --confirm`
