# AlphaLoop Scout

News-matched Polymarket prediction market signals for AI agents.

## What it does

1. Fetches real-time news for any topic via Google News and Yahoo Finance RSS
2. Analyzes sentiment with Groq llama-3.1-8b-instant
3. Discovers matching active Polymarket markets
4. Returns BULLISH/BEARISH/NEUTRAL signal with confidence score
5. Links directly to the best Polymarket market to act on

## Install

```bash
npx skills add okx/plugin-store --skill alphaloop-scout
```

## Quick Start

```bash
# Free market discovery
curl "https://alphaloop.duckdns.org/scout/markets?keyword=bitcoin"

# Paid signal ($0.001 USDC)
curl -X POST https://alphaloop.duckdns.org/scout/signal \
  -H "Content-Type: application/json" \
  -d '{"market": "BTC-5m", "query": "bitcoin price"}'
```

## Built by

AlphaLoop — 2nd Place, OKX Build X Hackathon Season 2
https://alphaloop.duckdns.org
