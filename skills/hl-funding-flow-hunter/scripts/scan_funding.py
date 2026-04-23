#!/usr/bin/env python3
"""Read-only Hyperliquid funding and flow scanner.

This script never signs, submits, or prepares orders. It only reads public
market data from https://api.hyperliquid.xyz/info and returns ranked candidates
for the hl-funding-flow-hunter skill to review with the user.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
import urllib.request
from typing import Any


API_URL = "https://api.hyperliquid.xyz/info"


def post_info(payload: dict[str, Any], timeout: float) -> Any:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "hl-funding-flow-hunter/1.0.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def log_score(value: float, scale: float, cap: float) -> float:
    if value <= 0:
        return 0.0
    return min(math.log10(value + 1) / scale * cap, cap)


def risk_flags(funding: float, volume_24h: float, open_interest: float, mark_px: float, prev_day_px: float) -> list[str]:
    flags: list[str] = []
    if abs(funding) < 0.000025:
        flags.append("funding_signal_weak")
    if volume_24h < 5_000_000:
        flags.append("low_24h_volume")
    if open_interest < 1_000_000:
        flags.append("low_open_interest")
    if mark_px > 0 and prev_day_px > 0:
        day_move = abs(mark_px - prev_day_px) / prev_day_px
        if day_move > 0.12:
            flags.append("high_24h_price_move")
    return flags


def score_candidate(funding: float, volume_24h: float, open_interest: float, premium: float) -> float:
    funding_bps = abs(funding) * 10_000
    funding_component = min(funding_bps / 1.5 * 40, 40)
    volume_component = log_score(volume_24h, 9.0, 25)
    oi_component = log_score(open_interest, 8.0, 25)
    premium_penalty = min(abs(premium) * 10_000 / 5, 10)
    return round(max(funding_component + volume_component + oi_component - premium_penalty, 0), 2)


def build_candidates(data: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    if not isinstance(data, list) or len(data) != 2:
        raise ValueError("Unexpected Hyperliquid metaAndAssetCtxs response shape")

    meta, contexts = data
    universe = meta.get("universe", []) if isinstance(meta, dict) else []
    if not isinstance(universe, list) or not isinstance(contexts, list):
        raise ValueError("Unexpected Hyperliquid universe or asset context shape")

    rows: list[dict[str, Any]] = []
    for index, asset in enumerate(universe):
        if not isinstance(asset, dict) or index >= len(contexts) or not isinstance(contexts[index], dict):
            continue

        ctx = contexts[index]
        coin = str(asset.get("name", "")).strip()
        if not coin:
            continue

        funding = as_float(ctx.get("funding"))
        volume_24h = as_float(ctx.get("dayNtlVlm"))
        open_interest = as_float(ctx.get("openInterest"))
        premium = as_float(ctx.get("premium"))
        mark_px = as_float(ctx.get("markPx"))
        prev_day_px = as_float(ctx.get("prevDayPx"))

        if volume_24h < args.min_volume or open_interest < args.min_oi:
            continue
        if abs(funding) < args.min_abs_funding:
            continue

        flags = risk_flags(funding, volume_24h, open_interest, mark_px, prev_day_px)
        side = "sell" if funding > 0 else "buy"
        score = score_candidate(funding, volume_24h, open_interest, premium)
        annualized = funding * 24 * 365

        rows.append(
            {
                "coin": coin,
                "suggested_side": side,
                "funding": funding,
                "funding_annualized_estimate": round(annualized, 6),
                "premium": premium,
                "mark_price": mark_px,
                "previous_day_price": prev_day_px,
                "volume_24h": volume_24h,
                "open_interest": open_interest,
                "max_leverage": asset.get("maxLeverage"),
                "score": score,
                "risk_flags": flags,
                "notes": build_notes(funding, flags),
            }
        )

    rows.sort(key=lambda item: (item["score"], abs(item["funding"]), item["volume_24h"]), reverse=True)
    return rows[: args.top]


def build_notes(funding: float, flags: list[str]) -> str:
    direction = "positive funding favors short exposure" if funding > 0 else "negative funding favors long exposure"
    if flags:
        return f"{direction}; review risk flags before any order"
    return f"{direction}; liquidity filters passed"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan Hyperliquid perp markets for funding and flow candidates.")
    parser.add_argument("--top", type=int, default=5, help="Number of candidates to return.")
    parser.add_argument("--min-volume", type=float, default=5_000_000, help="Minimum 24h notional volume.")
    parser.add_argument("--min-oi", type=float, default=1_000_000, help="Minimum open interest.")
    parser.add_argument("--min-abs-funding", type=float, default=0.00001, help="Minimum absolute hourly funding rate.")
    parser.add_argument("--timeout", type=float, default=10.0, help="HTTP timeout in seconds.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.top < 1:
        raise SystemExit("--top must be at least 1")

    try:
        data = post_info({"type": "metaAndAssetCtxs"}, args.timeout)
        candidates = build_candidates(data, args)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(json.dumps({"error": "hyperliquid_api_unavailable", "details": str(exc)}, indent=2), file=sys.stderr)
        return 2
    except (json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"error": "unexpected_hyperliquid_response", "details": str(exc)}, indent=2), file=sys.stderr)
        return 3

    result = {
        "source": API_URL,
        "strategy_id": "hl-funding-flow-hunter",
        "trade_execution": "read_only_scan_no_orders_submitted",
        "candidates": candidates,
        "execution_reminder": {
            "open": "Use hyperliquid order with --dry-run first, then --confirm only after user approval.",
            "close": "Use hyperliquid close with --strategy-id hl-funding-flow-hunter and explicit confirmation.",
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
