---
name: alphaloop-scout
description: "News-matched Polymarket prediction market signals powered by AlphaLoop AI"
version: "1.0.0"
author: "Favour Ezeoke"
tags:
  - polymarket
  - prediction-market
  - signals
  - news
  - ai
  - crypto
---

# AlphaLoop Scout

## Overview

AlphaLoop Scout is a composite Skill that fetches live news, analyzes sentiment
with Groq AI, and matches it to active Polymarket prediction markets. It combines
the Transfer Skill for micro-fee collection, the AlphaLoop backend for AI signal
generation, and the Polymarket Plugin for market discovery — all in a single
workflow.

Users pay $0.001 USDC per signal request via Transfer Skill. The Skill returns a
BULLISH, BEARISH, or NEUTRAL signal with a confidence score, matched Polymarket
markets with YES/NO prices, and a direct link to act on the signal.

Built by AlphaLoop — 2nd Place, OKX Build X Hackathon Season 2.

## Pre-flight Checks

Before using this skill, ensure:

1. The `onchainos` CLI is installed and configured:
   ```bash
   npx skills add okx/onchainos-skills
   export PATH="$HOME/.local/bin:$PATH"
   ```

2. The `polymarket-plugin` is installed:
   ```bash
   npx skills add okx/plugin-store --skill polymarket-plugin
   ```

3. The user has USDC on Polygon for signal fees ($0.001 per request).

4. Verify the AlphaLoop Scout API is reachable:
   ```bash
   curl https://alphaloop.duckdns.org/scout/markets?keyword=bitcoin
   ```
   Expected: JSON list of active Polymarket markets.

## Commands

### Command 1: Discover Markets

Browse active Polymarket markets for any topic. Free — no payment required.

```bash
curl "https://alphaloop.duckdns.org/scout/markets?keyword=<TOPIC>"
```

**When to use**: When the user wants to explore what markets exist on Polymarket
before requesting a paid signal. Use this first to find relevant markets.

**Parameters**:
- `keyword` — any topic e.g. `bitcoin`, `trump`, `fed`, `crypto`, `election`

**Output**: List of active markets with question, YES price, NO price, volume,
and direct Polymarket URL.

**Example**:
```bash
curl "https://alphaloop.duckdns.org/scout/markets?keyword=bitcoin"
```

**Sample output**:
```json
{
  "markets": [
    {
      "id": "12345",
      "question": "Will BTC exceed $100K before June 2026?",
      "yes_price": "0.42",
      "no_price": "0.58",
      "volume": "1250000",
      "url": "https://polymarket.com/event/btc-100k-june-2026"
    }
  ]
}
```

---

### Command 2: Get AI Signal (Paid — $0.001 USDC)

Full workflow: pay fee → fetch news → AI analysis → Polymarket market match.

**Step 1 — Collect signal fee via Transfer Skill:**
```bash
onchainos payment x402-pay \
  --to 0xdec754869Aa921661676e5FfB8589556cBDF3Ec7 \
  --amount 0.001 \
  --token USDC \
  --chain polygon \
  --label "AlphaLoop Scout Signal Fee"
```

**When to use Step 1**: Always before calling the signal endpoint. The tx hash
from this payment is required for Step 2.

**Output of Step 1**: Transaction hash (save this for Step 2).

**Step 2 — Request AI signal from AlphaLoop Scout:**
```bash
curl -X POST https://alphaloop.duckdns.org/scout/signal \
  -H "Content-Type: application/json" \
  -d '{
    "market": "<MARKET_TYPE>",
    "query": "<SEARCH_TOPIC>"
  }'
```

**When to use Step 2**: Immediately after Step 1 succeeds with a tx hash.

**Parameters**:
- `market` — market type: `"BTC-5m"`, `"ETH"`, `"crypto"`, `"politics"`, `"sports"`
- `query` — news search topic: `"bitcoin price"`, `"trump tariffs"`, `"fed rate"`

**Output**: Signal direction, confidence, reasoning, matched markets, action recommendation.

**Example**:
```bash
curl -X POST https://alphaloop.duckdns.org/scout/signal \
  -H "Content-Type: application/json" \
  -d '{"market": "BTC-5m", "query": "bitcoin price"}'
```

**Sample output**:
```json
{
  "market": "BTC-5m",
  "signal": "BEARISH",
  "confidence": 65,
  "reasoning": "Macro selling pressure identified from recent news. Oil price surge reducing risk appetite.",
  "best_market": "Will BTC exceed $95K before May 2026?",
  "polymarket_markets": [
    {
      "question": "Will BTC exceed $95K before May 2026?",
      "yes_price": "0.38",
      "no_price": "0.62",
      "volume": "980000",
      "url": "https://polymarket.com/event/btc-95k-may-2026"
    }
  ],
  "action": "LOW_CONFIDENCE — Monitor market",
  "polymarket_url": "https://polymarket.com/event/btc-95k-may-2026",
  "powered_by": "AlphaLoop Scout + Groq llama-3.1-8b-instant"
}
```

**Step 3 — Check Polymarket market price via Polymarket Plugin:**
```bash
onchainos polymarket get-market --id <MARKET_ID>
```

**When to use Step 3**: After receiving a HIGH_CONFIDENCE signal to verify
current market prices before the user places a bet.

---

### Command 3: Interpret Signal and Guide User

After receiving a signal, present it to the user clearly and guide them to act.

**Signal interpretation table**:

| Signal | Confidence | Recommendation |
|--------|-----------|---------------|
| BULLISH | ≥ 70 | Suggest YES position on matched Polymarket market |
| BEARISH | ≥ 70 | Suggest NO position on matched Polymarket market |
| BULLISH/BEARISH | 50–69 | Present signal but advise caution |
| NEUTRAL | any | No clear signal — advise monitoring |
| any | < 50 | Do not act — insufficient data |

**Always present the user with**:
1. The signal direction and confidence
2. The AI reasoning
3. The matched Polymarket market link
4. Current YES/NO prices
5. A reminder that this is not financial advice

## Examples

### Example 1: Bitcoin Signal Workflow

User says: "Scout the bitcoin market on Polymarket"

1. First, discover relevant markets:
   ```bash
   curl "https://alphaloop.duckdns.org/scout/markets?keyword=bitcoin"
   ```
   Present the markets to the user.

2. Collect the $0.001 USDC signal fee:
   ```bash
   onchainos payment x402-pay \
     --to 0xdec754869Aa921661676e5FfB8589556cBDF3Ec7 \
     --amount 0.001 --token USDC --chain polygon \
     --label "AlphaLoop Scout Signal Fee"
   ```

3. Request the AI signal:
   ```bash
   curl -X POST https://alphaloop.duckdns.org/scout/signal \
     -H "Content-Type: application/json" \
     -d '{"market": "BTC-5m", "query": "bitcoin price"}'
   ```

4. Verify market price via Polymarket Plugin:
   ```bash
   onchainos polymarket get-market --id <MARKET_ID_FROM_SIGNAL>
   ```

5. Present result to user:
   > "AlphaLoop Scout found a BEARISH signal for BTC (65% confidence).
   > Best market: 'Will BTC exceed $95K before May 2026?'
   > Current NO price: $0.62 — meaning the market gives 62% chance BTC stays below $95K.
   > → https://polymarket.com/event/btc-95k-may-2026
   > This is not financial advice. Always do your own research."

### Example 2: Current Events Signal

User says: "What should I bet on Polymarket about the Fed?"

1. Discover Fed-related markets:
   ```bash
   curl "https://alphaloop.duckdns.org/scout/markets?keyword=federal+reserve"
   ```

2. Collect fee and request signal:
   ```bash
   curl -X POST https://alphaloop.duckdns.org/scout/signal \
     -H "Content-Type: application/json" \
     -d '{"market": "macro", "query": "federal reserve interest rate"}'
   ```

3. Present signal with matched Polymarket market.

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| `{"markets": []}` | No Polymarket markets found for keyword | Try a broader keyword e.g. `"crypto"` instead of specific token |
| `"signal": "NEUTRAL", "confidence": 0` | No news found for topic | Try a different query term or check internet connectivity |
| `curl: connection refused` | AlphaLoop API unreachable | Retry after 30 seconds. API at `alphaloop.duckdns.org` |
| Payment tx fails | Insufficient USDC on Polygon | Ask user to bridge USDC to Polygon via `onchainos wallet` |
| `"reasoning": "No news available"` | RSS feeds returned no results | Try query with more common terms e.g. `"BTC"` instead of `"bitcoin price crash"` |

## Security Notices

- This skill collects $0.001 USDC per signal request via Transfer Skill. Always
  confirm the payment address before approving: `0xdec754869Aa921661676e5FfB8589556cBDF3Ec7`
- Signals are AI-generated from public news sources and are for informational
  purposes only. They are NOT financial advice.
- Polymarket is a prediction market platform. All bets carry risk of total loss.
- This skill does NOT automatically place bets. The user must manually act on
  any signal via Polymarket.
- Risk level: standard — requires explicit user confirmation before any payment.

## Skill Routing

- For placing actual Polymarket bets → use `polymarket-plugin` directly
- For crypto price data only → use `onchainos market price`
- For wallet balance checks → use `onchainos portfolio all-balances`
- For DeFi execution on X Layer → use `alphaloop-prime-broker` (https://alphaloop.duckdns.org)
