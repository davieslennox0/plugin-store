#!/usr/bin/env python3
"""
BTC Adaptive Hyperliquid Strategy Skill - decision engine.

This script is intentionally non-custodial and non-executing:
- It NEVER handles private keys or seed phrases.
- It NEVER submits orders to Hyperliquid or any exchange.
- It outputs a structured action plan that an AI agent must execute via the
  Hyperliquid Plugin / Onchain OS Agentic Wallet flow after user confirmation.

The implementation is dependency-free (Python stdlib only) so Plugin Store
reviewers can inspect and run it easily.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BINANCE_FAPI = "https://fapi.binance.com"
VERSION = "1.0.0"


# ----------------------------- utilities -----------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def load_json_arg(value: Optional[str], default: Any = None) -> Any:
    """Load JSON from an inline string or @file path."""
    if value is None:
        return default
    if value.startswith("@"):
        return json.loads(Path(value[1:]).read_text(encoding="utf-8"))
    return json.loads(value)


def read_json(path: str | Path, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def http_json(url: str, timeout: int = 8) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "btc-adaptive-hyperliquid-skill/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ----------------------------- data models -----------------------------

@dataclass
class Candle:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class MarketSnapshot:
    symbol: str
    price: float
    funding_rate: float
    candles_1h: List[Candle]
    source: str = "binance-futures-public"
    ts: str = ""

    def to_jsonable(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "funding_rate": self.funding_rate,
            "source": self.source,
            "ts": self.ts or now_iso(),
            "candles_1h": [asdict(c) for c in self.candles_1h],
        }


@dataclass
class AccountState:
    equity: float = 0.0
    available: float = 0.0
    session_realized_pnl: float = 0.0
    daily_realized_pnl: float = 0.0


@dataclass
class PositionState:
    side: str = "flat"  # flat | long | short | mixed | unknown
    size: float = 0.0
    entry_price: float = 0.0
    notional_usd: float = 0.0
    unrealized_pnl: float = 0.0
    leverage: float = 1.0
    scaleins: int = 0


# ----------------------------- indicators -----------------------------

def true_ranges(candles: List[Candle]) -> List[float]:
    if len(candles) < 2:
        return []
    out: List[float] = []
    prev_close = candles[0].close
    for c in candles[1:]:
        out.append(max(c.high - c.low, abs(c.high - prev_close), abs(c.low - prev_close)))
        prev_close = c.close
    return out


def atr(candles: List[Candle], period: int = 14) -> Optional[float]:
    trs = true_ranges(candles)
    if len(trs) < max(3, period // 2):
        return None
    sample = trs[-period:]
    return sum(sample) / len(sample)


def rsi(candles: List[Candle], period: int = 14) -> Optional[float]:
    if len(candles) < period + 1:
        return None
    closes = [c.close for c in candles]
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    seed = deltas[-period:]
    gains = sum(max(d, 0.0) for d in seed) / period
    losses = sum(abs(min(d, 0.0)) for d in seed) / period
    if losses == 0:
        return 100.0
    rs = gains / losses
    return 100.0 - 100.0 / (1.0 + rs)


def trend_slope(candles: List[Candle], lookback: int = 12) -> float:
    if len(candles) < 3:
        return 0.0
    closes = [c.close for c in candles[-lookback:]]
    n = len(closes)
    xs = list(range(n))
    xbar = sum(xs) / n
    ybar = sum(closes) / n
    denom = sum((x - xbar) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    return sum((xs[i] - xbar) * (closes[i] - ybar) for i in range(n)) / denom


def swing_levels(candles: List[Candle], lookback: int = 24) -> Tuple[float, float]:
    if not candles:
        return 0.0, 0.0
    sample = candles[-lookback:]
    return max(c.high for c in sample), min(c.low for c in sample)


# ----------------------------- normalization -----------------------------

def normalize_account(raw: Dict[str, Any]) -> AccountState:
    if not raw:
        return AccountState()
    # Accept several common formats so agents can pass Hyperliquid Plugin output directly.
    equity = first_float(raw, ["equity", "accountValue", "totalEquity", "totalEq", "marginSummary.accountValue"])
    available = first_float(raw, ["available", "availableBalance", "withdrawable", "freeCollateral", "marginSummary.withdrawable"])
    session_pnl = first_float(raw, ["session_realized_pnl", "sessionRealizedPnl", "realizedPnl"], 0.0)
    daily_pnl = first_float(raw, ["daily_realized_pnl", "dailyRealizedPnl", "dayPnl"], 0.0)
    if available <= 0 and equity > 0:
        available = equity
    return AccountState(equity=equity, available=available, session_realized_pnl=session_pnl, daily_realized_pnl=daily_pnl)


def normalize_position(raw: Dict[str, Any]) -> PositionState:
    if not raw:
        return PositionState()
    if isinstance(raw, list):
        raw = {"positions": raw}
    if "positions" in raw and isinstance(raw["positions"], list):
        return normalize_position_list(raw["positions"])

    side = str(raw.get("side") or raw.get("direction") or raw.get("positionSide") or "").lower()
    size = first_float(raw, ["size", "szi", "qty", "position", "pos"], 0.0)
    if side not in ("long", "short", "flat"):
        if size > 0:
            side = "long"
        elif size < 0:
            side = "short"
            size = abs(size)
        else:
            side = "flat"
    entry = first_float(raw, ["entry_price", "entryPx", "entryPrice", "avgPx", "averageEntryPrice"], 0.0)
    notional = first_float(raw, ["notional_usd", "notional", "positionValue", "value"], 0.0)
    pnl = first_float(raw, ["unrealized_pnl", "unrealizedPnl", "upl", "uPnl"], 0.0)
    leverage = first_float(raw, ["leverage", "lev"], 1.0) or 1.0
    scaleins = int(first_float(raw, ["scaleins", "scale_ins"], 0.0))
    return PositionState(side=side, size=abs(size), entry_price=entry, notional_usd=abs(notional), unrealized_pnl=pnl, leverage=leverage, scaleins=scaleins)


def normalize_position_list(items: List[Dict[str, Any]]) -> PositionState:
    active: List[PositionState] = []
    for item in items:
        ps = normalize_position(item)
        if ps.side in ("long", "short") and ps.size > 0:
            active.append(ps)
    if not active:
        return PositionState()
    sides = {p.side for p in active}
    if len(sides) > 1:
        return PositionState(side="mixed", notional_usd=sum(p.notional_usd for p in active), unrealized_pnl=sum(p.unrealized_pnl for p in active))
    p = active[0]
    if len(active) == 1:
        return p
    total_size = sum(x.size for x in active)
    weighted_entry = sum(x.entry_price * x.size for x in active) / total_size if total_size else 0.0
    return PositionState(
        side=p.side,
        size=total_size,
        entry_price=weighted_entry,
        notional_usd=sum(x.notional_usd for x in active),
        unrealized_pnl=sum(x.unrealized_pnl for x in active),
        leverage=max(x.leverage for x in active),
        scaleins=max(x.scaleins for x in active),
    )


def first_float(raw: Dict[str, Any], keys: List[str], default: float = 0.0) -> float:
    for key in keys:
        cur: Any = raw
        ok = True
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok and cur is not None:
            try:
                return float(cur)
            except (TypeError, ValueError):
                continue
    return default


# ----------------------------- market source -----------------------------

def fetch_binance_market(symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 72) -> MarketSnapshot:
    params = urllib.parse.urlencode({"symbol": symbol})
    premium = http_json(f"{BINANCE_FAPI}/fapi/v1/premiumIndex?{params}")
    price = float(premium.get("markPrice") or premium.get("indexPrice") or 0.0)
    funding = float(premium.get("lastFundingRate") or 0.0)
    kparams = urllib.parse.urlencode({"symbol": symbol, "interval": interval, "limit": limit})
    raw_klines = http_json(f"{BINANCE_FAPI}/fapi/v1/klines?{kparams}")
    candles = [
        Candle(
            ts=int(k[0]),
            open=float(k[1]),
            high=float(k[2]),
            low=float(k[3]),
            close=float(k[4]),
            volume=float(k[5]),
        )
        for k in raw_klines
    ]
    if not price and candles:
        price = candles[-1].close
    return MarketSnapshot(symbol=symbol, price=price, funding_rate=funding, candles_1h=candles, ts=now_iso())


def normalize_market(raw: Dict[str, Any]) -> MarketSnapshot:
    candles_raw = raw.get("candles_1h") or raw.get("candles") or []
    candles: List[Candle] = []
    for c in candles_raw:
        if isinstance(c, dict):
            candles.append(Candle(
                ts=int(c.get("ts") or c.get("time") or 0),
                open=float(c.get("open") or c.get("o") or 0.0),
                high=float(c.get("high") or c.get("h") or 0.0),
                low=float(c.get("low") or c.get("l") or 0.0),
                close=float(c.get("close") or c.get("c") or 0.0),
                volume=float(c.get("volume") or c.get("v") or 0.0),
            ))
        elif isinstance(c, list) and len(c) >= 5:
            candles.append(Candle(ts=int(c[0]), open=float(c[1]), high=float(c[2]), low=float(c[3]), close=float(c[4])))
    price = float(raw.get("price") or raw.get("markPrice") or (candles[-1].close if candles else 0.0))
    funding = float(raw.get("funding_rate") or raw.get("fundingRate") or raw.get("lastFundingRate") or 0.0)
    return MarketSnapshot(symbol=str(raw.get("symbol") or "BTC"), price=price, funding_rate=funding, candles_1h=candles, source=str(raw.get("source") or "provided"), ts=str(raw.get("ts") or now_iso()))


# ----------------------------- strategy engine -----------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "BTC",
    "market_symbol": "BTCUSDT",
    "dry_run_default": True,
    "risk": {
        "leverage": 5,
        "per_trade_ratio": 0.30,
        "per_trade_ratio_max": 0.80,
        "per_session_equity_loss_pct": 0.06,
        "soft_loss_pct": 0.02,
        "emergency_loss_pct": 0.04,
        "max_position_notional_pct": 0.90,
        "min_available_usd": 10.0,
    },
    "adaptive": {
        "enabled": True,
        "lookback_hours": 24,
        "min_range_usd": 1200.0,
        "atr_period": 14,
        "atr_stop_mult": 1.25,
        "atr_tp_mult": 2.40,
        "breakout_buffer_atr": 0.10,
        "breakout_buffer_min": 50.0,
        "hold_seconds_min": 300,
        "hold_seconds_max": 900,
        "funding_high": 0.0003,
        "rsi_overbought": 75.0,
        "rsi_oversold": 25.0,
        "fade_drop_atr": 0.45,
        "fade_sl_atr": 1.00,
        "profit_lock_pct": 0.45,
        "allow_scale_in": True,
        "adaptive_add_ratio": 0.25,
        "adaptive_reduce_ratio": 0.50,
        "max_scaleins": 1,
        "new_entry_pause_sec_after_reduce": 1800,
    },
    "news_protection": {
        "enabled": True,
        "high_risk_default_action": "halt_new_entries",
    },
}


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = json.loads(json.dumps(base))
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def compute_levels(config: Dict[str, Any], market: MarketSnapshot) -> Dict[str, Any]:
    candles = market.candles_1h
    aconf = config["adaptive"]
    lookback = int(aconf.get("lookback_hours", 24))
    cur_atr = atr(candles, int(aconf.get("atr_period", 14))) or max(market.price * 0.006, 300.0)
    swing_hi, swing_lo = swing_levels(candles, lookback)
    if not swing_hi or not swing_lo:
        swing_hi = market.price + cur_atr
        swing_lo = market.price - cur_atr
    min_range = max(float(aconf.get("min_range_usd", 1200.0)), cur_atr * 2.5)
    raw_range = swing_hi - swing_lo
    if raw_range < min_range:
        mid = (swing_hi + swing_lo) / 2.0
        swing_hi = mid + min_range / 2.0
        swing_lo = mid - min_range / 2.0
    buffer = max(float(aconf.get("breakout_buffer_min", 50.0)), cur_atr * float(aconf.get("breakout_buffer_atr", 0.10)))
    breakout = float(config.get("breakout_up") or config.get("BREAKOUT_UP") or (swing_hi + buffer))
    breakdown = float(config.get("breakdown_dn") or config.get("BREAKDOWN_DN") or (swing_lo - buffer))
    if breakout - breakdown < min_range:
        mid = (breakout + breakdown) / 2.0
        breakout = mid + min_range / 2.0
        breakdown = mid - min_range / 2.0
    hard_stop = float(config.get("sl_hard") or config.get("SL_HARD") or (breakdown - max(600.0, cur_atr * 1.2)))
    hard_stop = min(hard_stop, breakdown - 600.0)
    tp_long = breakout + cur_atr * float(aconf.get("atr_tp_mult", 2.4))
    sl_long = max(hard_stop, breakout - cur_atr * float(aconf.get("atr_stop_mult", 1.25)))
    tp_short = breakdown - cur_atr * float(aconf.get("atr_tp_mult", 2.4))
    sl_short = breakdown + cur_atr * float(aconf.get("atr_stop_mult", 1.25))
    hold_seconds = int(clamp(
        max(float(aconf.get("hold_seconds_min", 300)), cur_atr / max(market.price, 1) * 50000),
        float(aconf.get("hold_seconds_min", 300)),
        float(aconf.get("hold_seconds_max", 900)),
    ))
    return {
        "atr_1h": round(cur_atr, 4),
        "swing_high": round(swing_hi, 4),
        "swing_low": round(swing_lo, 4),
        "min_range": round(min_range, 4),
        "breakout_up": round(breakout, 4),
        "breakdown_dn": round(breakdown, 4),
        "sl_hard": round(hard_stop, 4),
        "tp_long": round(tp_long, 4),
        "sl_long": round(sl_long, 4),
        "tp_short": round(tp_short, 4),
        "sl_short": round(sl_short, 4),
        "hold_seconds": hold_seconds,
    }


def action_plan(config: Dict[str, Any], account: AccountState, position: PositionState, market: MarketSnapshot, state: Dict[str, Any], risk_mode: str = "normal") -> Dict[str, Any]:
    levels = compute_levels(config, market)
    candles = market.candles_1h
    cur_rsi = rsi(candles, 14)
    slope = trend_slope(candles, 12)
    funding = market.funding_rate
    price = market.price
    aconf = config["adaptive"]
    risk = config["risk"]
    dry_run = bool(config.get("dry_run_default", True))

    per_trade_ratio = clamp(float(risk.get("per_trade_ratio", 0.30)), 0.0, float(risk.get("per_trade_ratio_max", 0.80)))
    leverage = max(1.0, float(risk.get("leverage", 5)))
    available = max(0.0, account.available)
    equity = max(account.equity, available, 0.0)
    max_position_notional = equity * float(risk.get("max_position_notional_pct", 0.90)) * leverage
    proposed_margin = min(available * per_trade_ratio, available * float(risk.get("per_trade_ratio_max", 0.80)))
    proposed_notional = proposed_margin * leverage
    proposed_notional = min(proposed_notional, max_position_notional)

    diagnostics: List[str] = []
    reasons: List[str] = []
    warnings: List[str] = []
    state_patch: Dict[str, Any] = {}

    if equity <= 0:
        return make_plan("noop", "no_equity_or_account_data", dry_run, reasons=["No account equity was provided; refuse to trade."], warnings=["Pass account state from Hyperliquid Plugin before execution."], levels=levels, market=market, account=account, position=position)

    if position.side == "mixed":
        return make_plan("close_all", "mixed_hedge_position_detected", dry_run, fraction=1.0, reasons=["Both long and short exposure were detected; strategy cannot safely manage mixed hedge positions."], warnings=["Use reduce-only close through Hyperliquid Plugin after user confirmation."], levels=levels, market=market, account=account, position=position)

    session_loss_limit = -equity * float(risk.get("per_session_equity_loss_pct", 0.06))
    if account.session_realized_pnl <= session_loss_limit or account.daily_realized_pnl <= session_loss_limit:
        return make_plan("halt_new_entries", "session_loss_limit_reached", dry_run, ttl_sec=86400, reasons=["Session/daily realized loss exceeded configured loss cap."], levels=levels, market=market, account=account, position=position)

    if risk_mode in ("pause", "news-high", "halt"):
        if position.side in ("long", "short") and position.unrealized_pnl < 0:
            return make_plan("reduce", "risk_mode_pause_reduce_losing_position", dry_run, fraction=float(aconf.get("adaptive_reduce_ratio", 0.5)), reasons=["Risk mode requests no new entries and current position is losing."], levels=levels, market=market, account=account, position=position)
        return make_plan("halt_new_entries", "risk_mode_pause", dry_run, ttl_sec=7200, reasons=["Risk mode is pause/high-risk; no new entries."], levels=levels, market=market, account=account, position=position)

    if proposed_margin < float(risk.get("min_available_usd", 10.0)) and position.side == "flat":
        warnings.append("Available balance is below minimum margin threshold; new entries disabled.")

    # Persist peak favorable movement for profit lock.
    peak_key = "peak_favor_move_usd"
    prev_peak = float(state.get(peak_key, 0.0) or 0.0)
    favor_move = 0.0
    if position.side == "long" and position.entry_price:
        favor_move = price - position.entry_price
    elif position.side == "short" and position.entry_price:
        favor_move = position.entry_price - price
    peak = max(prev_peak, favor_move)
    state_patch[peak_key] = round(peak, 4)

    # Existing position management comes before any new entry.
    if position.side in ("long", "short"):
        return manage_position(config, account, position, market, levels, cur_rsi, slope, state, state_patch, dry_run)

    # Flat: evaluate new entries.
    if proposed_notional <= 0:
        return make_plan("noop", "insufficient_budget", dry_run, reasons=["No open position and proposed notional is zero."], warnings=warnings, levels=levels, market=market, account=account, position=position)

    if cur_rsi is not None:
        diagnostics.append(f"RSI14={cur_rsi:.1f}")
    diagnostics.append(f"slope_12h={slope:.2f}")
    diagnostics.append(f"funding={funding:+.6f}")

    overbought = cur_rsi is not None and cur_rsi >= float(aconf.get("rsi_overbought", 75.0))
    oversold = cur_rsi is not None and cur_rsi <= float(aconf.get("rsi_oversold", 25.0))
    funding_hot_long = funding > float(aconf.get("funding_high", 0.0003))
    funding_hot_short = funding < -float(aconf.get("funding_high", 0.0003))

    last = candles[-1] if candles else None
    prev_high = max((c.high for c in candles[-3:]), default=price)
    prev_low = min((c.low for c in candles[-3:]), default=price)
    fade_drop = max(float(aconf.get("fade_drop_atr", 0.45)) * levels["atr_1h"], 250.0)

    if price > levels["breakout_up"] and slope > 0 and not overbought and not funding_hot_long:
        reasons = [
            f"Price {price:.2f} is above adaptive breakout {levels['breakout_up']:.2f}.",
            "12-hour close slope is positive.",
            "RSI/funding filters do not show long-side overheating.",
        ]
        return make_plan("open_long", "adaptive_breakout_long", dry_run, notional_usd=proposed_notional, leverage=leverage, take_profit=levels["tp_long"], stop_loss=levels["sl_long"], reasons=reasons + diagnostics, levels=levels, market=market, account=account, position=position, state_patch=state_patch)

    if price < levels["breakdown_dn"] and slope < 0 and not oversold and not funding_hot_short:
        reasons = [
            f"Price {price:.2f} is below adaptive breakdown {levels['breakdown_dn']:.2f}.",
            "12-hour close slope is negative.",
            "RSI/funding filters do not show short-side crowding.",
        ]
        return make_plan("open_short", "adaptive_breakdown_short", dry_run, notional_usd=proposed_notional, leverage=leverage, take_profit=levels["tp_short"], stop_loss=levels["sl_short"], reasons=reasons + diagnostics, levels=levels, market=market, account=account, position=position, state_patch=state_patch)

    if prev_high >= levels["breakout_up"] and price < levels["breakout_up"] - fade_drop and not oversold:
        reasons = [
            "Recent candles touched/cleared breakout but price fell back below the fade threshold.",
            "Fade-short setup: failed breakout / rejection.",
        ]
        return make_plan("open_short", "failed_breakout_fade_short", dry_run, notional_usd=proposed_notional * 0.5, leverage=leverage, take_profit=price - levels["atr_1h"] * 1.8, stop_loss=price + max(levels["atr_1h"], 500.0), reasons=reasons + diagnostics, levels=levels, market=market, account=account, position=position, state_patch=state_patch)

    if prev_low <= levels["breakdown_dn"] and price > levels["breakdown_dn"] + fade_drop and not overbought:
        reasons = [
            "Recent candles touched/cleared breakdown but price reclaimed the fade threshold.",
            "Fade-long setup: failed breakdown / reclaim.",
        ]
        return make_plan("open_long", "failed_breakdown_fade_long", dry_run, notional_usd=proposed_notional * 0.5, leverage=leverage, take_profit=price + levels["atr_1h"] * 1.8, stop_loss=price - max(levels["atr_1h"], 500.0), reasons=reasons + diagnostics, levels=levels, market=market, account=account, position=position, state_patch=state_patch)

    return make_plan("noop", "no_clean_setup", dry_run, reasons=["No clean breakout, breakdown, or fade setup after filters."] + diagnostics, warnings=warnings, levels=levels, market=market, account=account, position=position, state_patch=state_patch)


def manage_position(config: Dict[str, Any], account: AccountState, position: PositionState, market: MarketSnapshot, levels: Dict[str, Any], cur_rsi: Optional[float], slope: float, state: Dict[str, Any], state_patch: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    aconf = config["adaptive"]
    risk = config["risk"]
    price = market.price
    equity = max(account.equity, account.available, 1.0)
    side = position.side
    sign = 1 if side == "long" else -1
    favor_move = (price - position.entry_price) * sign if position.entry_price else 0.0
    peak = max(float(state.get("peak_favor_move_usd", 0.0) or 0.0), favor_move)
    state_patch["peak_favor_move_usd"] = round(peak, 4)

    soft_loss = equity * float(risk.get("soft_loss_pct", 0.02))
    emergency_loss = equity * float(risk.get("emergency_loss_pct", 0.04))
    reduce_ratio = float(aconf.get("adaptive_reduce_ratio", 0.5))
    funding = market.funding_rate
    funding_high = float(aconf.get("funding_high", 0.0003))
    overbought = cur_rsi is not None and cur_rsi >= float(aconf.get("rsi_overbought", 75.0))
    oversold = cur_rsi is not None and cur_rsi <= float(aconf.get("rsi_oversold", 25.0))

    reasons = [f"Managing existing {side} position.", f"favor_move_usd={favor_move:.2f}", f"peak_favor_move_usd={peak:.2f}", f"unrealized_pnl={position.unrealized_pnl:.2f}"]
    if cur_rsi is not None:
        reasons.append(f"RSI14={cur_rsi:.1f}")
    reasons.append(f"funding={funding:+.6f}")

    # Emergency exits first.
    if position.unrealized_pnl <= -emergency_loss:
        return make_plan("close_all", "adaptive_emergency_loss", dry_run, fraction=1.0, reasons=reasons + ["Unrealized loss exceeded emergency loss cap."], levels=levels, market=market, account=account, position=position, state_patch={**state_patch, "pause_new_entries_until": int(time.time()) + 3600})

    if side == "long" and price <= levels["sl_long"]:
        return make_plan("close_all", "long_dynamic_stop_loss", dry_run, fraction=1.0, reasons=reasons + [f"Price {price:.2f} <= dynamic long stop {levels['sl_long']:.2f}."], levels=levels, market=market, account=account, position=position, state_patch={**state_patch, "pause_new_entries_until": int(time.time()) + 3600})

    if side == "short" and price >= levels["sl_short"]:
        return make_plan("close_all", "short_dynamic_stop_loss", dry_run, fraction=1.0, reasons=reasons + [f"Price {price:.2f} >= dynamic short stop {levels['sl_short']:.2f}."], levels=levels, market=market, account=account, position=position, state_patch={**state_patch, "pause_new_entries_until": int(time.time()) + 3600})

    # Soft loss reduction.
    if position.unrealized_pnl <= -soft_loss:
        return make_plan("reduce", "adaptive_soft_loss_reduce", dry_run, fraction=reduce_ratio, reasons=reasons + ["Unrealized loss exceeded soft loss threshold; reduce exposure instead of waiting for full stop."], levels=levels, market=market, account=account, position=position, state_patch={**state_patch, "pause_new_entries_until": int(time.time()) + int(aconf.get("new_entry_pause_sec_after_reduce", 1800))})

    # Profit lock: once peak is meaningful, reduce if giveback is too large.
    lock_pct = float(aconf.get("profit_lock_pct", 0.45))
    if peak >= max(levels["atr_1h"] * 1.2, 600.0):
        giveback = peak - max(favor_move, 0.0)
        if giveback >= peak * lock_pct:
            return make_plan("reduce", "adaptive_profit_giveback_lock", dry_run, fraction=reduce_ratio, reasons=reasons + [f"Profit giveback {giveback:.2f} exceeds {lock_pct:.0%} of peak favorable move."], levels=levels, market=market, account=account, position=position, state_patch={**state_patch, "pause_new_entries_until": int(time.time()) + int(aconf.get("new_entry_pause_sec_after_reduce", 1800))})

    # Target / overheating reductions.
    if side == "long":
        if price >= levels["tp_long"]:
            return make_plan("reduce", "long_dynamic_take_profit", dry_run, fraction=reduce_ratio, reasons=reasons + [f"Price reached dynamic long take profit {levels['tp_long']:.2f}."], levels=levels, market=market, account=account, position=position, state_patch=state_patch)
        if favor_move > 0 and (overbought or funding > funding_high):
            return make_plan("reduce", "long_overheat_reduce", dry_run, fraction=reduce_ratio, reasons=reasons + ["Long is profitable but RSI/funding indicates overheating."], levels=levels, market=market, account=account, position=position, state_patch=state_patch)
    else:
        if price <= levels["tp_short"]:
            return make_plan("reduce", "short_dynamic_take_profit", dry_run, fraction=reduce_ratio, reasons=reasons + [f"Price reached dynamic short take profit {levels['tp_short']:.2f}."], levels=levels, market=market, account=account, position=position, state_patch=state_patch)
        if favor_move > 0 and (oversold or funding < -funding_high):
            return make_plan("reduce", "short_overheat_reduce", dry_run, fraction=reduce_ratio, reasons=reasons + ["Short is profitable but RSI/funding indicates crowded downside."], levels=levels, market=market, account=account, position=position, state_patch=state_patch)

    # Controlled scale-in only for profitable positions and trend confirmation.
    if bool(aconf.get("allow_scale_in", True)) and position.scaleins < int(aconf.get("max_scaleins", 1)) and favor_move >= levels["atr_1h"] * 1.2:
        if side == "long" and slope > 0 and not overbought and funding <= funding_high:
            notional = account.available * float(aconf.get("adaptive_add_ratio", 0.25)) * float(risk.get("leverage", 5))
            return make_plan("scale_in", "long_profitable_trend_scale_in", dry_run, notional_usd=notional, leverage=float(risk.get("leverage", 5)), take_profit=levels["tp_long"], stop_loss=max(position.entry_price, levels["sl_long"]), reasons=reasons + ["Existing long is profitable, slope remains positive, and filters are not overheated."], levels=levels, market=market, account=account, position=position, state_patch={**state_patch, "scaleins": position.scaleins + 1})
        if side == "short" and slope < 0 and not oversold and funding >= -funding_high:
            notional = account.available * float(aconf.get("adaptive_add_ratio", 0.25)) * float(risk.get("leverage", 5))
            return make_plan("scale_in", "short_profitable_trend_scale_in", dry_run, notional_usd=notional, leverage=float(risk.get("leverage", 5)), take_profit=levels["tp_short"], stop_loss=min(position.entry_price, levels["sl_short"]), reasons=reasons + ["Existing short is profitable, slope remains negative, and filters are not crowded."], levels=levels, market=market, account=account, position=position, state_patch={**state_patch, "scaleins": position.scaleins + 1})

    return make_plan("hold", "position_within_risk_bounds", dry_run, reasons=reasons + ["No reduction, exit, or scale-in condition is active."], levels=levels, market=market, account=account, position=position, state_patch=state_patch)


def make_plan(action: str, reason_code: str, dry_run: bool, *, fraction: Optional[float] = None, notional_usd: Optional[float] = None, leverage: Optional[float] = None, take_profit: Optional[float] = None, stop_loss: Optional[float] = None, ttl_sec: Optional[int] = None, reasons: Optional[List[str]] = None, warnings: Optional[List[str]] = None, levels: Optional[Dict[str, Any]] = None, market: Optional[MarketSnapshot] = None, account: Optional[AccountState] = None, position: Optional[PositionState] = None, state_patch: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    plan = {
        "schema": "btc-adaptive-hyperliquid.plan.v1",
        "generated_at": now_iso(),
        "engine_version": VERSION,
        "dry_run": bool(dry_run),
        "must_execute_via": "Hyperliquid Plugin / Onchain OS Agentic Wallet",
        "action": action,
        "reason_code": reason_code,
        "confidence": confidence_for(action, reason_code),
        "parameters": {},
        "risk_controls": {
            "requires_user_confirmation": True,
            "reduce_only_required": action in ("reduce", "close_all"),
            "script_submits_orders": False,
            "no_sybil_or_volume_padding": True,
        },
        "reasons": reasons or [],
        "warnings": warnings or [],
        "levels": levels or {},
        "market": market.to_jsonable() if market else {},
        "account_summary": asdict(account) if account else {},
        "position_summary": asdict(position) if position else {},
        "state_patch": state_patch or {},
        "hyperliquid_plugin_execution_hint": execution_hint(action),
    }
    params = plan["parameters"]
    if fraction is not None:
        params["fraction"] = round(float(fraction), 6)
    if notional_usd is not None:
        params["notional_usd"] = round(max(0.0, float(notional_usd)), 2)
    if leverage is not None:
        params["leverage"] = round(float(leverage), 3)
    if take_profit is not None:
        params["take_profit"] = round(float(take_profit), 4)
    if stop_loss is not None:
        params["stop_loss"] = round(float(stop_loss), 4)
    if ttl_sec is not None:
        params["ttl_sec"] = int(ttl_sec)
    return plan


def confidence_for(action: str, reason_code: str) -> str:
    if action in ("close_all", "reduce") and ("loss" in reason_code or "stop" in reason_code or "mixed" in reason_code):
        return "high"
    if action in ("open_long", "open_short", "scale_in"):
        return "medium"
    if action == "noop":
        return "high"
    return "medium"


def execution_hint(action: str) -> List[str]:
    if action == "open_long":
        return ["Use Hyperliquid Plugin to open/increase a BTC-PERP long for parameters.notional_usd.", "Place/attach protective stop-loss and take-profit if supported by the Hyperliquid Plugin; otherwise set a monitored risk order through the plugin flow."]
    if action == "open_short":
        return ["Use Hyperliquid Plugin to open/increase a BTC-PERP short for parameters.notional_usd.", "Place/attach protective stop-loss and take-profit if supported by the Hyperliquid Plugin; otherwise set a monitored risk order through the plugin flow."]
    if action == "scale_in":
        return ["Use Hyperliquid Plugin to increase the existing profitable BTC-PERP position by parameters.notional_usd only after user confirmation.", "Do not scale in if position data has changed or if resulting exposure exceeds max caps."]
    if action == "reduce":
        return ["Use Hyperliquid Plugin reduce-only close for parameters.fraction of the current BTC-PERP position."]
    if action == "close_all":
        return ["Use Hyperliquid Plugin reduce-only close for 100% of the current BTC-PERP position."]
    if action == "halt_new_entries":
        return ["Do not open new BTC-PERP positions until TTL expires; continue monitoring existing positions."]
    if action == "hold":
        return ["No execution required; continue monitoring and keep existing risk controls in place."]
    return ["No execution required."]


# ----------------------------- CLI -----------------------------

def cmd_validate_config(args: argparse.Namespace) -> int:
    cfg = deep_merge(DEFAULT_CONFIG, read_json(args.config, {}))
    errors: List[str] = []
    if not cfg.get("dry_run_default", True):
        errors.append("dry_run_default should be true for Plugin Store review safety.")
    if float(cfg["risk"].get("per_trade_ratio_max", 1.0)) > 0.80:
        errors.append("per_trade_ratio_max must not exceed 0.80 in this submission.")
    if float(cfg["risk"].get("soft_loss_pct", 0.0)) <= 0:
        errors.append("soft_loss_pct must be positive.")
    if float(cfg["risk"].get("emergency_loss_pct", 0.0)) <= float(cfg["risk"].get("soft_loss_pct", 0.0)):
        errors.append("emergency_loss_pct must exceed soft_loss_pct.")
    print(json.dumps({"ok": not errors, "errors": errors, "config": cfg}, indent=2, ensure_ascii=False))
    return 1 if errors else 0


def cmd_plan(args: argparse.Namespace) -> int:
    cfg = deep_merge(DEFAULT_CONFIG, read_json(args.config, {}))
    account = normalize_account(load_json_arg(args.account_json, {}))
    position = normalize_position(load_json_arg(args.position_json, {}))
    state = read_json(args.state, {}) if args.state else {}
    if args.market_json:
        market = normalize_market(load_json_arg(args.market_json, {}))
    elif args.fetch_market:
        market = fetch_binance_market(cfg.get("market_symbol", "BTCUSDT"), args.interval, args.limit)
    else:
        print(json.dumps({"error": "market required: pass --market-json or --fetch-market"}, indent=2), file=sys.stderr)
        return 2

    if args.dry_run is not None:
        cfg["dry_run_default"] = args.dry_run

    plan = action_plan(cfg, account, position, market, state, args.risk_mode)
    if args.write_state and args.state:
        merged_state = {**state, **plan.get("state_patch", {})}
        write_json(args.state, merged_state)
    if args.output == "text":
        print(render_text(plan))
    else:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


def render_text(plan: Dict[str, Any]) -> str:
    params = plan.get("parameters", {})
    lines = [
        f"Action: {plan.get('action')} ({plan.get('reason_code')})",
        f"Dry-run: {plan.get('dry_run')}",
        f"Execute via: {plan.get('must_execute_via')}",
        f"Parameters: {json.dumps(params, ensure_ascii=False)}",
        "Reasons:",
    ]
    lines += [f"- {r}" for r in plan.get("reasons", [])]
    if plan.get("warnings"):
        lines.append("Warnings:")
        lines += [f"- {w}" for w in plan.get("warnings", [])]
    lines.append("Execution hint:")
    lines += [f"- {h}" for h in plan.get("hyperliquid_plugin_execution_hint", [])]
    return "\n".join(lines)


def cmd_demo(args: argparse.Namespace) -> int:
    demo_market = {
        "symbol": "BTC",
        "price": 78550,
        "funding_rate": 0.00012,
        "candles_1h": synthetic_candles(),
        "source": "synthetic-demo",
    }
    demo_account = {"equity": 1000, "available": 950, "session_realized_pnl": 0}
    demo_position = {"side": "flat", "size": 0}
    ns = argparse.Namespace(
        config=args.config,
        account_json=json.dumps(demo_account),
        position_json=json.dumps(demo_position),
        state=None,
        market_json=json.dumps(demo_market),
        fetch_market=False,
        interval="1h",
        limit=72,
        dry_run=True,
        risk_mode="normal",
        write_state=False,
        output=args.output,
    )
    return cmd_plan(ns)


def synthetic_candles() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    base = 76000.0
    for i in range(72):
        drift = i * 35
        wave = math.sin(i / 5) * 350
        close = base + drift + wave
        out.append({"ts": int(time.time() - (72 - i) * 3600) * 1000, "open": close - 80, "high": close + 220, "low": close - 260, "close": close, "volume": 1000 + i})
    return out


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BTC Adaptive Hyperliquid decision engine (plan-only, no order execution).")
    parser.add_argument("--version", action="version", version=VERSION)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="Generate a JSON trading action plan.")
    p.add_argument("--config", default="config/default.json", help="Path to config JSON.")
    p.add_argument("--state", default=None, help="Path to runtime state JSON.")
    p.add_argument("--account-json", default=None, help="Inline JSON or @file from Hyperliquid Plugin account output.")
    p.add_argument("--position-json", default=None, help="Inline JSON or @file from Hyperliquid Plugin position output.")
    p.add_argument("--market-json", default=None, help="Inline JSON or @file market snapshot.")
    p.add_argument("--fetch-market", action="store_true", help="Fetch public Binance futures BTCUSDT 1h candles/mark/funding.")
    p.add_argument("--interval", default="1h", help="Binance kline interval for --fetch-market.")
    p.add_argument("--limit", type=int, default=72, help="Number of candles for --fetch-market.")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=None, help="Force dry-run true.")
    p.add_argument("--live-plan", dest="dry_run", action="store_false", help="Allow a live execution plan; still does not execute orders.")
    p.add_argument("--risk-mode", default="normal", choices=["normal", "conservative", "pause", "news-high", "halt"], help="External risk override.")
    p.add_argument("--write-state", action="store_true", help="Write state_patch back to --state.")
    p.add_argument("--output", default="json", choices=["json", "text"])
    p.set_defaults(func=cmd_plan)

    v = sub.add_parser("validate-config", help="Validate config for safety review.")
    v.add_argument("--config", default="config/default.json")
    v.set_defaults(func=cmd_validate_config)

    d = sub.add_parser("demo", help="Run a deterministic synthetic dry-run example.")
    d.add_argument("--config", default="config/default.json")
    d.add_argument("--output", default="json", choices=["json", "text"])
    d.set_defaults(func=cmd_demo)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except urllib.error.URLError as exc:
        print(json.dumps({"error": "network_error", "detail": str(exc)}, indent=2), file=sys.stderr)
        return 3
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": "json_decode_error", "detail": str(exc)}, indent=2), file=sys.stderr)
        return 4
    except Exception as exc:
        print(json.dumps({"error": "unexpected_error", "detail": str(exc)}, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
