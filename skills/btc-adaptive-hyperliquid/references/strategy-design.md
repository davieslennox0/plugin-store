# Strategy Design

## Purpose

BTC Adaptive Hyperliquid converts the earlier VPS/OKX-style BTC guard logic into a Plugin Store-compatible strategy planner. The execution layer is deliberately removed from the script and delegated to the Hyperliquid Plugin.

## Signal layers

1. **Adaptive market structure**
   - 1h candles
   - 24h swing high/low
   - ATR minimum range enforcement
   - Adaptive breakout and breakdown levels

2. **Entry setups**
   - Breakout long: price above adaptive breakout, positive trend slope, RSI/funding not overheated.
   - Breakdown short: price below adaptive breakdown, negative trend slope, RSI/funding not crowded.
   - Failed-breakout fade short: recent breakout touch followed by rejection.
   - Failed-breakdown fade long: recent breakdown touch followed by reclaim.

3. **Position management**
   - Emergency full close at configured unrealized-loss threshold.
   - Soft-loss partial reduction.
   - ATR-based dynamic stop loss.
   - ATR-based dynamic take profit.
   - Profit-giveback reduction after favorable movement.
   - Overheat reduction when RSI/funding becomes crowded.
   - Controlled scale-in only when the existing position is profitable and trend filters agree.

## Conflict-resolution priority

The engine resolves conflicts in this order:

1. Account/session loss cap
2. Mixed hedge safety
3. External pause/high-risk mode
4. Existing position management
5. New entries
6. No-op/hold

Existing positions are always managed before new entries. This prevents a situation where the planner opens a new position while an existing one requires reduction or emergency exit.

## Risk limits

Default limits are deliberately conservative for public Skill review:

- Dry-run is default.
- Per-trade margin ratio: 0.30.
- Maximum configurable per-trade margin ratio: 0.80.
- Soft unrealized loss threshold: 2% equity.
- Emergency unrealized loss threshold: 4% equity.
- Session realized loss cap: 6% equity.
- Maximum position notional cap: 90% equity × leverage.

## Competition compliance

The strategy plan contains execution hints but no exchange API execution code. The AI agent must execute any live action through Hyperliquid Plugin so the transaction chain remains eligible for Plugin Store DApp Challenge scoring.
