#!/usr/bin/env python3
"""
Macro Intelligence Skill v1.0 — Unified Macro Intelligence Feed
Merges perception layers from RWA Alpha + TG Intel.
Reads news from 3 sources (NewsNow, Polymarket, Telegram),
classifies macro events, scores sentiment, exposes signals via HTTP API.
No trading logic — intelligence only.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import threading
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

import config as C

# ═══════════════════════════════════════════════════════════════════════
#  GLOBAL STATE
# ═══════════════════════════════════════════════════════════════════════
_state_lock = threading.Lock()

_signals: list[dict] = []               # Unified signal list
_dedup_hashes: dict[str, float] = {}    # hash -> timestamp
_reputation: dict[str, dict] = {}       # sender_id -> {score, last_ts, hits}
_polymarket: list[dict] = []            # Latest Polymarket data
_source_status: dict[str, float] = {}   # source -> last_success_ts
_fear_greed: dict = {}                  # Latest Fear & Greed Index
_fred_indicators: dict = {}             # Latest FRED macro indicators
_opennews_ws_alive = False              # True while WebSocket is connected
_price_tickers: dict = {}               # Latest price tickers {symbol: {price, change_pct, label}}
_stats = {
    "messages_processed": 0,
    "signals_produced": 0,
    "start_ts": 0,
    "news_fetches": 0,
    "tg_messages": 0,
    "llm_calls": 0,
}

# Compiled regex caches
_macro_regex: dict[str, list[re.Pattern]] = {}
_noise_regex: list[re.Pattern] = []

_BASE_DIR = Path(__file__).parent
_STATE_DIR = _BASE_DIR / C.STATE_DIR

# ═══════════════════════════════════════════════════════════════════════
#  LOGGING & PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════
def _log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)

def _save_state():
    _STATE_DIR.mkdir(exist_ok=True)
    try:
        with _state_lock:
            data = {
                "signals": _signals[-C.MAX_SIGNALS_KEPT:],
                "dedup_hashes": _dedup_hashes,
                "reputation": _reputation,
                "polymarket": _polymarket,
                "stats": _stats,
                "source_status": _source_status,
                "finnhub_last_id": _finnhub_last_id,
            }
        with open(_STATE_DIR / "state.json", "w") as f:
            json.dump(data, f, default=str)
    except Exception as e:
        _log(f"save_state error: {e}", "WARN")

def _load_state():
    global _signals, _dedup_hashes, _reputation, _polymarket, _stats, _source_status, _finnhub_last_id
    p = _STATE_DIR / "state.json"
    if not p.exists():
        return
    try:
        with open(p) as f:
            data = json.load(f)
        with _state_lock:
            _signals = data.get("signals", [])
            _dedup_hashes = data.get("dedup_hashes", {})
            _reputation = data.get("reputation", {})
            _polymarket = data.get("polymarket", [])
            saved_stats = data.get("stats", {})
            for k in _stats:
                if k in saved_stats:
                    _stats[k] = saved_stats[k]
            _source_status = data.get("source_status", {})
            _finnhub_last_id = data.get("finnhub_last_id", 0)
        _log(f"Loaded state: {len(_signals)} signals, {len(_reputation)} senders")
    except Exception as e:
        _log(f"load_state error: {e}", "WARN")

# ═══════════════════════════════════════════════════════════════════════
#  HTTP HELPER
# ═══════════════════════════════════════════════════════════════════════
def _http_get_json(url: str, timeout: int = 10) -> dict | list:
    try:
        req = Request(url, headers={"User-Agent": "MacroNews/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return {}

# ═══════════════════════════════════════════════════════════════════════
#  NEWS FETCHERS
# ═══════════════════════════════════════════════════════════════════════
def fetch_news_headlines() -> list[dict]:
    """Fetch latest headlines from NewsNow sources."""
    all_items = []
    for source in C.NEWS_SOURCES:
        data = _http_get_json(f"{C.NEWSNOW_BASE}?id={source}", timeout=8)
        items = data.get("items", data.get("data", [])) if isinstance(data, dict) else []
        for item in items[:15]:
            title = item.get("title", item.get("name", ""))
            if title:
                all_items.append({
                    "title": title,
                    "url": item.get("url", item.get("link", "")),
                    "source": source,
                    "ts": item.get("pubDate", item.get("time", "")),
                })
    return all_items

def fetch_polymarket_signals() -> list[dict]:
    """Fetch Polymarket prediction market data via events endpoint with keyword filtering."""
    _MACRO_KEYWORDS_PM = [
        "fed", "rate cut", "interest rate", "cpi", "inflation", "gdp",
        "tariff", "recession", "gold", "oil", "treasury", "fomc",
        "employment", "job", "bitcoin", "crypto", "economy", "china",
    ]
    results = []
    seen_questions = set()
    # Paginate through events to find macro-relevant ones
    for offset in (0, 100, 200):
        url = f"{C.POLYMARKET_BASE.replace('/markets', '/events')}?active=true&closed=false&limit=100&offset={offset}"
        data = _http_get_json(url, timeout=8)
        if not isinstance(data, list):
            continue
        for event in data:
            title = (event.get("title", "") or "").lower()
            if not any(kw in title for kw in _MACRO_KEYWORDS_PM):
                continue
            for m in event.get("markets", []):
                if not isinstance(m, dict):
                    continue
                question = m.get("question", m.get("title", ""))
                if not question or question in seen_questions:
                    continue
                seen_questions.add(question)
                prices = m.get("outcomePrices", "")
                prob = 0.5
                if isinstance(prices, str):
                    try:
                        prices = json.loads(prices)
                    except Exception:
                        prices = []
                if isinstance(prices, list) and prices:
                    try:
                        prob = float(prices[0])
                    except (ValueError, IndexError):
                        pass
                results.append({
                    "question": question,
                    "probability": prob,
                    "category": event.get("slug", ""),
                    "volume": m.get("volume", 0),
                })
    return results

def fetch_fear_greed() -> dict:
    """Fetch Crypto Fear & Greed Index from alternative.me."""
    data = _http_get_json("https://api.alternative.me/fng/?limit=7", timeout=8)
    if not isinstance(data, dict) or "data" not in data:
        return {}
    entries = data["data"]
    if not entries:
        return {}
    current = entries[0]
    history = [{"value": int(e.get("value", 0)),
                "label": e.get("value_classification", ""),
                "ts": int(e.get("timestamp", 0))} for e in entries]
    return {
        "value": int(current.get("value", 0)),
        "label": current.get("value_classification", ""),
        "ts": int(current.get("timestamp", 0)),
        "history": history,
    }

# ═══════════════════════════════════════════════════════════════════════
#  FINNHUB NEWS FETCHER
# ═══════════════════════════════════════════════════════════════════════
_finnhub_last_id: int = 0  # Track last seen article ID to avoid re-processing

def fetch_finnhub_news() -> list[dict]:
    """Fetch market news from Finnhub. Uses minId for incremental fetching."""
    global _finnhub_last_id
    if not C.FINNHUB_API_KEY:
        return []
    all_articles = []
    for cat in C.FINNHUB_CATEGORIES:
        url = f"{C.FINNHUB_BASE}/news?category={cat}&token={C.FINNHUB_API_KEY}"
        if _finnhub_last_id:
            url += f"&minId={_finnhub_last_id}"
        data = _http_get_json(url, timeout=10)
        if not isinstance(data, list):
            continue
        for item in data:
            article_id = item.get("id", 0)
            if article_id and article_id > _finnhub_last_id:
                _finnhub_last_id = article_id
            headline = item.get("headline", "")
            if headline:
                all_articles.append({
                    "title": headline,
                    "source": item.get("source", "finnhub"),
                    "url": item.get("url", ""),
                    "ts": item.get("datetime", 0),
                })
    return all_articles

# ═══════════════════════════════════════════════════════════════════════
#  FRED MACRO INDICATORS FETCHER
# ═══════════════════════════════════════════════════════════════════════
# Thresholds for significant change detection (emit signals)
_FRED_CHANGE_THRESHOLDS = {
    "FEDFUNDS": 0.10,   # 10 bps change in Fed Funds Rate
    "CPIAUCSL": 0.3,    # 0.3% CPI change
    "GDP":      0.5,    # 0.5% GDP change
    "UNRATE":   0.2,    # 0.2% unemployment change
    "T10Y2Y":   0.15,   # 15 bps spread change
    "DGS10":    0.15,   # 15 bps yield change
}

def fetch_fred_indicators() -> dict:
    """Fetch latest macro indicators from FRED. Returns dict of series data with change detection."""
    if not C.FRED_API_KEY:
        return {}
    results = {}
    for series_id, label in C.FRED_SERIES.items():
        url = (f"{C.FRED_BASE}/series/observations"
               f"?series_id={series_id}&api_key={C.FRED_API_KEY}"
               f"&file_type=json&limit=2&sort_order=desc")
        data = _http_get_json(url, timeout=10)
        if not isinstance(data, dict):
            continue
        obs = data.get("observations", [])
        if not obs:
            continue
        try:
            current_val = float(obs[0].get("value", "0"))
        except (ValueError, TypeError):
            continue
        current_date = obs[0].get("date", "")
        prev_val = None
        change = None
        if len(obs) > 1:
            try:
                prev_val = float(obs[1].get("value", "0"))
                change = round(current_val - prev_val, 4)
            except (ValueError, TypeError):
                pass
        results[series_id] = {
            "value": current_val,
            "date": current_date,
            "label": label,
            "prev_value": prev_val,
            "change": change,
        }
    return results

# ═══════════════════════════════════════════════════════════════════════
#  6551.io OPENNEWS REST FALLBACK
# ═══════════════════════════════════════════════════════════════════════
def fetch_opennews_rest() -> list[dict]:
    """Fallback: fetch high-score news via 6551.io REST API."""
    if not C.OPENNEWS_TOKEN:
        return []
    url = f"{C.OPENNEWS_API_BASE}/open/free_hot?category=news"
    data = _http_get_json(url, timeout=10)
    if not isinstance(data, dict):
        return []
    items = data.get("data", data.get("items", []))
    if not isinstance(items, list):
        return []
    results = []
    for item in items:
        score = item.get("aiRating", {}).get("score", 0) if isinstance(item.get("aiRating"), dict) else 0
        if score < C.OPENNEWS_MIN_SCORE:
            continue
        text = (item.get("enSummary") or item.get("summary") or
                item.get("title") or item.get("text", ""))
        if not text:
            continue
        results.append({
            "text": text,
            "source": item.get("newsType", "opennews"),
            "score": score,
            "signal": item.get("aiRating", {}).get("signal", "neutral") if isinstance(item.get("aiRating"), dict) else "neutral",
        })
    return results

# ═══════════════════════════════════════════════════════════════════════
#  PRICE TICKER FETCHER
# ═══════════════════════════════════════════════════════════════════════
def fetch_price_tickers() -> dict:
    """Fetch live prices for dashboard ticker bar.
    Finnhub for stocks/ETFs (SPY, GLD, SLV), CoinGecko for crypto (BTC, ETH).
    """
    results = {}

    # Finnhub stock/ETF quotes
    if C.FINNHUB_API_KEY:
        for symbol, label in C.FINNHUB_PRICE_SYMBOLS.items():
            data = _http_get_json(
                f"{C.FINNHUB_BASE}/quote?symbol={symbol}&token={C.FINNHUB_API_KEY}",
                timeout=5,
            )
            if isinstance(data, dict) and data.get("c"):
                price = data["c"]           # Current price
                prev_close = data.get("pc", price)  # Previous close
                change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
                results[symbol] = {
                    "price": price,
                    "change_pct": round(change_pct, 2),
                    "label": label,
                }

    # CoinGecko crypto quotes (free, no key)
    cg_data = _http_get_json(
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true",
        timeout=5,
    )
    if isinstance(cg_data, dict):
        if "bitcoin" in cg_data:
            results["BTC"] = {
                "price": cg_data["bitcoin"].get("usd", 0),
                "change_pct": round(cg_data["bitcoin"].get("usd_24h_change", 0), 2),
                "label": "BTC",
            }
        if "ethereum" in cg_data:
            results["ETH"] = {
                "price": cg_data["ethereum"].get("usd", 0),
                "change_pct": round(cg_data["ethereum"].get("usd_24h_change", 0), 2),
                "label": "ETH",
            }

    return results

# ═══════════════════════════════════════════════════════════════════════
#  NOISE FILTER (Telegram only)
# ═══════════════════════════════════════════════════════════════════════
def _count_emoji(text: str) -> int:
    # Count chars in common emoji ranges
    count = 0
    for ch in text:
        cp = ord(ch)
        if (0x1F600 <= cp <= 0x1F64F or 0x1F300 <= cp <= 0x1F5FF or
            0x1F680 <= cp <= 0x1F6FF or 0x1F900 <= cp <= 0x1F9FF or
            0x2600 <= cp <= 0x26FF or 0x2700 <= cp <= 0x27BF or
            0xFE00 <= cp <= 0xFE0F or 0x200D == cp):
            count += 1
    return count

def _is_noise(text: str, sender_id: str = "", sender_name: str = "",
              is_reply: bool = False, is_forward_from_bot: bool = False,
              is_deep_reply: bool = False) -> bool:
    """Return True if message should be dropped as noise."""
    # VIP bypass
    if sender_name in C.VIP_SENDERS or sender_id in C.VIP_SENDERS:
        return False

    stripped = text.strip()

    # Min length
    if len(stripped) < C.NOISE_MIN_LENGTH:
        return True

    # Bot forward
    if C.NOISE_SKIP_BOT_FORWARDS and is_forward_from_bot:
        return True

    # Deep reply
    if C.NOISE_SKIP_DEEP_REPLIES and is_deep_reply:
        return True

    # Emoji ratio
    emoji_count = _count_emoji(stripped)
    if len(stripped) > 0 and emoji_count / len(stripped) > C.NOISE_MAX_EMOJI_RATIO:
        return True

    # Pattern match
    for pat in _noise_regex:
        if pat.search(stripped):
            return True

    return False

# ═══════════════════════════════════════════════════════════════════════
#  DEDUP (cross-source, MD5 hash, time window)
# ═══════════════════════════════════════════════════════════════════════
def _dedup_hash(text: str) -> str:
    n = C.DEDUP_SIMILARITY_CHARS
    snippet = re.sub(r'\s+', ' ', text[:n].lower().strip())
    return hashlib.md5(snippet.encode()).hexdigest()[:12]

def _is_duplicate(text: str) -> bool:
    h = _dedup_hash(text)
    now = time.time()
    window = C.DEDUP_WINDOW_HOURS * 3600
    with _state_lock:
        # Clean old hashes
        expired = [k for k, ts in _dedup_hashes.items() if now - ts > window]
        for k in expired:
            del _dedup_hashes[k]
        if h in _dedup_hashes:
            return True
        _dedup_hashes[h] = now
    return False

# ═══════════════════════════════════════════════════════════════════════
#  3-LAYER CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════
def _match_macro_keywords(text: str) -> tuple[str, float] | None:
    """Layer 1: Regex keyword match. Returns (event_type, confidence) or None."""
    text_lower = text.lower()
    for event_type, patterns in _macro_regex.items():
        for pat in patterns:
            if pat.search(text_lower) or pat.search(text):
                return (event_type, 0.85)
    return None

def _match_classifier_rules(text: str) -> dict | None:
    """Layer 1b: TG-style classifier rules. Returns matched rule dict or None."""
    text_lower = text.lower()
    for rule in C.CLASSIFIER_RULES:
        # Check keywords_any (at least one must match)
        any_match = False
        for kw in rule["keywords_any"]:
            if kw.lower() in text_lower:
                any_match = True
                break
        if not any_match:
            continue
        # Check keywords_not (none must match)
        not_match = False
        for kw in rule.get("keywords_not", []):
            if kw.lower() in text_lower:
                not_match = True
                break
        if not_match:
            continue
        return rule
    return None

def _llm_classify(text: str, source_type: str) -> dict | None:
    """Layer 2/3: LLM classification using Haiku. Returns signal dict or None."""
    if not C.LLM_ENABLED:
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    # Pre-screen: check if text has any relevant keywords
    text_lower = text.lower()
    has_keyword = False
    for kw in C.LLM_PRESCREEN_KEYWORDS:
        if kw.startswith(r"\$"):
            if re.search(kw, text):
                has_keyword = True
                break
        elif kw.lower() in text_lower:
            has_keyword = True
            break
    if not has_keyword:
        return None

    event_types = list(C.MACRO_PLAYBOOK.keys())
    prompt = f"""Classify this {source_type} message into a macro event type.

Event types: {', '.join(event_types)}

If the message matches an event type, respond with JSON:
{{"event_type": "...", "direction": "bullish|bearish|neutral", "confidence": 0.0-1.0}}

If not relevant to macro/crypto, respond: {{"event_type": "none"}}

Message: {text[:500]}"""

    try:
        import urllib.request
        body = json.dumps({
            "model": C.LLM_MODEL,
            "max_tokens": C.LLM_MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with _state_lock:
            _stats["llm_calls"] += 1
        with urllib.request.urlopen(req, timeout=C.LLM_TIMEOUT_SEC) as resp:
            result = json.loads(resp.read().decode())
        content = result.get("content", [{}])[0].get("text", "")
        # Extract JSON from response
        match = re.search(r'\{[^}]+\}', content)
        if not match:
            return None
        data = json.loads(match.group())
        if data.get("event_type", "none") == "none":
            return None
        confidence = float(data.get("confidence", 0.5))
        if confidence < C.LLM_CONFIDENCE_BAND[0]:
            return None
        return {
            "event_type": data["event_type"],
            "direction": data.get("direction", "neutral"),
            "confidence": confidence,
            "classify_method": "llm_confirm" if confidence >= C.LLM_CONFIDENCE_BAND[1] else "llm_discover",
        }
    except Exception as e:
        _log(f"LLM classify error: {e}", "WARN")
        return None

def classify_text(text: str, source_type: str) -> dict:
    """Unified 3-layer classification. Returns classification result."""
    # Layer 1a: Macro keyword regex
    kw_match = _match_macro_keywords(text)
    if kw_match:
        event_type, confidence = kw_match
        playbook = C.MACRO_PLAYBOOK.get(event_type, {})
        return {
            "event_type": event_type,
            "direction": playbook.get("direction", "neutral"),
            "magnitude": playbook.get("magnitude", 0.5),
            "urgency": playbook.get("urgency", 0.5),
            "affects": playbook.get("affects", []),
            "classify_method": "keyword",
        }

    # Layer 1b: Classifier rules (TG-style)
    rule = _match_classifier_rules(text)
    if rule:
        return {
            "event_type": rule["event_type"],
            "direction": rule["direction"],
            "magnitude": rule["magnitude"],
            "urgency": C.MACRO_PLAYBOOK.get(rule["event_type"], {}).get("urgency", 0.5),
            "affects": rule["affects"],
            "classify_method": "keyword",
        }

    # Layer 2/3: LLM classification
    llm_result = _llm_classify(text, source_type)
    if llm_result:
        event_type = llm_result["event_type"]
        playbook = C.MACRO_PLAYBOOK.get(event_type, {})
        return {
            "event_type": event_type,
            "direction": llm_result.get("direction", playbook.get("direction", "neutral")),
            "magnitude": playbook.get("magnitude", 0.5),
            "urgency": playbook.get("urgency", 0.5),
            "affects": playbook.get("affects", []),
            "classify_method": llm_result["classify_method"],
        }

    return {
        "event_type": "unclassified",
        "direction": "neutral",
        "magnitude": 0.0,
        "urgency": 0.0,
        "affects": [],
        "classify_method": "none",
    }

# ═══════════════════════════════════════════════════════════════════════
#  LLM INSIGHT GENERATOR
# ═══════════════════════════════════════════════════════════════════════
def _generate_insight(headline: str, event_type: str, direction: str,
                      affects: list[str]) -> str:
    """Call Haiku to produce a 2-3 sentence insight explaining what the headline
    means for specific asset classes. Returns insight text or empty string."""
    if not C.LLM_INSIGHT_ENABLED:
        return ""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""

    affects_str = ", ".join(affects) if affects else "broad crypto market"
    prompt = (
        f"You are a macro analyst. Given this headline and its classification, "
        f"write 2-3 concise sentences explaining:\n"
        f"1) The key takeaway from this event\n"
        f"2) How it is likely to affect specific assets or sectors "
        f"({affects_str})\n\n"
        f"Headline: {headline[:400]}\n"
        f"Event type: {event_type}\n"
        f"Direction: {direction}\n\n"
        f"Be specific about which assets benefit or suffer and why. "
        f"No preamble — start directly with the analysis."
    )

    try:
        import urllib.request
        body = json.dumps({
            "model": C.LLM_MODEL,
            "max_tokens": C.LLM_INSIGHT_MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        with _state_lock:
            _stats["llm_calls"] += 1
        with urllib.request.urlopen(req, timeout=C.LLM_INSIGHT_TIMEOUT_SEC) as resp:
            result = json.loads(resp.read().decode())
        content = result.get("content", [{}])[0].get("text", "")
        return content.strip()
    except Exception as e:
        _log(f"Insight generation error: {e}", "WARN")
        return ""

# ═══════════════════════════════════════════════════════════════════════
#  SENTIMENT SCORING
# ═══════════════════════════════════════════════════════════════════════
def _score_sentiment(text: str) -> float:
    """Score sentiment from -1.0 to +1.0 using weighted lexicon."""
    words = re.findall(r'[\w\u4e00-\u9fff]+', text.lower())
    total_weight = 0.0
    word_count = 0
    for w in words:
        if w in C.POSITIVE_WORDS:
            total_weight += C.POSITIVE_WORDS[w]
            word_count += 1
        elif w in C.NEGATIVE_WORDS:
            total_weight += C.NEGATIVE_WORDS[w]
            word_count += 1
    if word_count == 0:
        return 0.0
    return max(-1.0, min(1.0, total_weight / word_count))

# ═══════════════════════════════════════════════════════════════════════
#  TOKEN EXTRACTION
# ═══════════════════════════════════════════════════════════════════════
def _extract_tokens(text: str) -> list[str]:
    """Extract ticker symbols from text."""
    dollar_tickers = re.findall(r'\$([A-Za-z]{2,10})', text)
    caps_tickers = re.findall(r'\b([A-Z]{3,5})\b', text)
    all_tickers = set(t.upper() for t in dollar_tickers)
    all_tickers.update(t for t in caps_tickers if t not in C.TICKER_NOISE_WORDS)
    return sorted(all_tickers)

# ═══════════════════════════════════════════════════════════════════════
#  REPUTATION SYSTEM
# ═══════════════════════════════════════════════════════════════════════
def _update_sender_rep(sender_id: str, event_type: str):
    """Update sender reputation based on signal quality."""
    if not C.REPUTATION_ENABLED or not sender_id:
        return
    with _state_lock:
        if sender_id not in _reputation:
            _reputation[sender_id] = {"score": 0.0, "last_ts": time.time(), "hits": 0}

        rep = _reputation[sender_id]
        now = time.time()

        # Time decay
        days_elapsed = (now - rep["last_ts"]) / 86400
        if days_elapsed > 0 and C.REPUTATION_DECAY_DAYS > 0:
            decay = 1.0 - (min(days_elapsed, C.REPUTATION_DECAY_DAYS) / C.REPUTATION_DECAY_DAYS) * 0.1
            rep["score"] *= max(0.0, decay)

        # Boost/penalty
        if event_type in ("alpha_call", "whale_buy", "whale_sell"):
            rep["score"] += C.REPUTATION_BOOST_ALPHA
        elif event_type == "unclassified":
            rep["score"] += C.REPUTATION_PENALTY_NOISE
        else:
            rep["score"] += C.REPUTATION_BOOST_NEWS

        rep["score"] = max(C.REPUTATION_MIN_SCORE, min(C.REPUTATION_MAX_SCORE, rep["score"]))
        rep["last_ts"] = now
        rep["hits"] = rep.get("hits", 0) + 1

def _get_sender_rep(sender_id: str) -> float:
    with _state_lock:
        return _reputation.get(sender_id, {}).get("score", 0.0)

def _decay_reputations():
    """Periodic decay of all reputations."""
    if not C.REPUTATION_ENABLED:
        return
    now = time.time()
    with _state_lock:
        for sid, rep in _reputation.items():
            days = (now - rep["last_ts"]) / 86400
            if days > C.REPUTATION_DECAY_DAYS:
                rep["score"] *= 0.5

# ═══════════════════════════════════════════════════════════════════════
#  UNIFIED PIPELINE — single entry point for all sources
# ═══════════════════════════════════════════════════════════════════════
def process_signal(text: str, source_type: str, source_name: str,
                   sender: str = "", group_category: str = "",
                   is_reply: bool = False, is_forward_from_bot: bool = False,
                   is_deep_reply: bool = False) -> dict | None:
    """
    Unified signal processing pipeline.
    source_type: "newsnow" | "polymarket" | "telegram"
    Returns UnifiedSignal dict or None if filtered.
    """
    with _state_lock:
        _stats["messages_processed"] += 1

    # 1. Noise filter (TG only)
    if source_type == "telegram":
        if _is_noise(text, sender, sender, is_reply, is_forward_from_bot, is_deep_reply):
            _update_sender_rep(sender, "unclassified")
            return None

    # 2. Dedup (cross-source)
    if _is_duplicate(text):
        return None

    # 3. Classify
    classification = classify_text(text, source_type)
    if classification["event_type"] == "unclassified" and classification["magnitude"] == 0.0:
        # For TG, still count unclassified; for news, skip
        if source_type != "telegram":
            return None
        # For TG, keep if it passed noise filter (might be useful context)
        # but don't emit as a signal
        _update_sender_rep(sender, "unclassified")
        return None

    # 4. Sentiment
    sentiment = _score_sentiment(text)

    # 5. Token extraction
    tokens = _extract_tokens(text)

    # 6. Reputation
    sender_rep = 0.0
    if sender:
        _update_sender_rep(sender, classification["event_type"])
        sender_rep = _get_sender_rep(sender)
        # High-rep senders get magnitude boost
        if sender_rep >= C.REPUTATION_HIGH_SIGNAL:
            classification["magnitude"] = min(1.0, classification["magnitude"] * 1.3)

    # 7. Generate AI insight (for classified signals only)
    insight = ""
    if classification["event_type"] != "unclassified":
        insight = _generate_insight(
            text, classification["event_type"],
            classification["direction"],
            classification.get("affects", []),
        )

    # 8. Build signal
    now = time.time()
    signal = {
        "ts": int(now),
        "ts_human": datetime.now().strftime("%m-%d %H:%M:%S"),
        "source_type": source_type,
        "source_name": source_name,
        "event_type": classification["event_type"],
        "direction": classification["direction"],
        "magnitude": round(classification["magnitude"], 2),
        "urgency": round(classification.get("urgency", 0.5), 2),
        "affects": classification.get("affects", []),
        "tokens": tokens,
        "sentiment": round(sentiment, 3),
        "text": text[:400],
        "insight": insight,
        "sender": sender or source_name,
        "sender_rep": round(sender_rep, 2),
        "classify_method": classification["classify_method"],
        "group_category": group_category or ("http_news" if source_type == "newsnow" else source_type),
    }

    # 8. Store
    with _state_lock:
        _signals.append(signal)
        if len(_signals) > C.MAX_SIGNALS_KEPT:
            _signals[:] = _signals[-C.MAX_SIGNALS_KEPT:]
        _stats["signals_produced"] += 1
        _source_status[source_name] = now

    _log(f"SIGNAL [{source_type}] {classification['event_type']} "
         f"{classification['direction']} mag={classification['magnitude']:.2f} "
         f"from={source_name} method={classification['classify_method']}")

    return signal

# ═══════════════════════════════════════════════════════════════════════
#  NEWS COLLECTOR THREAD
# ═══════════════════════════════════════════════════════════════════════
def _news_collector_loop():
    """Background thread: polls NewsNow + Polymarket + Finnhub + FRED + OpenNews REST on intervals."""
    global _polymarket, _fear_greed, _fred_indicators, _price_tickers
    _log("NewsNow + Polymarket + Finnhub + FRED collector started")
    news_last = 0
    poly_last = 0
    fng_last = 0
    finnhub_last = 0
    fred_last = 0
    opennews_rest_last = 0
    prices_last = 0

    while True:
        try:
            now = time.time()

            # NewsNow headlines
            if now - news_last >= C.NEWS_POLL_SEC:
                news_last = now
                headlines = fetch_news_headlines()
                with _state_lock:
                    _stats["news_fetches"] += 1
                for h in headlines:
                    process_signal(
                        text=h["title"],
                        source_type="newsnow",
                        source_name=h["source"],
                        group_category="http_news",
                    )
                if headlines:
                    _log(f"NewsNow: fetched {len(headlines)} headlines")

            # Polymarket
            if now - poly_last >= C.POLYMARKET_POLL_SEC:
                poly_last = now
                markets = fetch_polymarket_signals()
                if markets:
                    with _state_lock:
                        _polymarket = markets
                        _source_status["polymarket"] = now
                    # Group markets by event category — emit ONE signal per group
                    by_cat: dict[str, list] = {}
                    for m in markets:
                        cat = m.get("category", "") or "other"
                        by_cat.setdefault(cat, []).append(m)
                    for cat, cat_markets in by_cat.items():
                        # Pick the most notable market (highest prob divergence from 50%)
                        best = max(cat_markets, key=lambda x: abs(x.get("probability", 0.5) - 0.5))
                        prob = best.get("probability", 0.5)
                        q = best.get("question", "")
                        if abs(prob - 0.5) < 0.15:
                            continue  # Skip near-50/50 markets
                        n_related = len(cat_markets)
                        summary = f"{q} — currently at {prob:.0%} probability"
                        if n_related > 1:
                            summary += f". {n_related} related prediction markets tracking this event."
                        process_signal(
                            text=summary,
                            source_type="polymarket",
                            source_name="polymarket",
                            group_category="polymarket",
                        )
                    _log(f"Polymarket: fetched {len(markets)} markets in {len(by_cat)} groups")

            # Fear & Greed Index (every 5 min — updates daily but cheap to poll)
            if now - fng_last >= 300:
                fng_last = now
                fng = fetch_fear_greed()
                if fng:
                    with _state_lock:
                        _fear_greed = fng
                    _log(f"Fear & Greed: {fng['value']} ({fng['label']})")

            # Price tickers (every 60s)
            if now - prices_last >= C.PRICE_TICKER_POLL_SEC:
                prices_last = now
                tickers = fetch_price_tickers()
                if tickers:
                    with _state_lock:
                        _price_tickers = tickers
                    parts = [f"{v['label']}=${v['price']:,.1f}" for v in tickers.values()]
                    _log(f"Prices: {', '.join(parts)}")

            # Finnhub market news
            if C.FINNHUB_ENABLED and C.FINNHUB_API_KEY and now - finnhub_last >= C.FINNHUB_POLL_SEC:
                finnhub_last = now
                articles = fetch_finnhub_news()
                for a in articles:
                    process_signal(
                        text=a["title"],
                        source_type="finnhub",
                        source_name=a.get("source", "finnhub"),
                        group_category="http_news",
                    )
                if articles:
                    _log(f"Finnhub: fetched {len(articles)} articles")

            # FRED macro indicators
            if C.FRED_ENABLED and C.FRED_API_KEY and now - fred_last >= C.FRED_POLL_SEC:
                fred_last = now
                indicators = fetch_fred_indicators()
                if indicators:
                    with _state_lock:
                        _fred_indicators = indicators
                        _source_status["fred"] = now
                    _log(f"FRED: updated {len(indicators)} indicators")
                    # Significant change detection — emit signals
                    for series_id, data in indicators.items():
                        if data["change"] is not None:
                            threshold = _FRED_CHANGE_THRESHOLDS.get(series_id, 0.2)
                            if abs(data["change"]) >= threshold:
                                process_signal(
                                    text=f"FRED {data['label']}: {data['value']} (prev: {data['prev_value']}, change: {data['change']:+.2f})",
                                    source_type="fred",
                                    source_name="fred",
                                    group_category="macro_data",
                                )

            # 6551.io OpenNews REST fallback (only if WebSocket is down)
            if (C.OPENNEWS_ENABLED and C.OPENNEWS_TOKEN
                    and not _opennews_ws_alive
                    and now - opennews_rest_last >= C.OPENNEWS_POLL_SEC):
                opennews_rest_last = now
                articles = fetch_opennews_rest()
                for a in articles:
                    process_signal(
                        text=a["text"],
                        source_type="opennews",
                        source_name=a.get("source", "opennews"),
                        group_category="opennews",
                    )
                if articles:
                    _log(f"OpenNews REST fallback: fetched {len(articles)} articles")

            # Periodic save + reputation decay
            _save_state()
            _decay_reputations()

        except Exception as e:
            _log(f"News collector error: {e}", "ERROR")
            traceback.print_exc()

        time.sleep(10)

# ═══════════════════════════════════════════════════════════════════════
#  TELEGRAM COLLECTOR (Telethon)
# ═══════════════════════════════════════════════════════════════════════
_telethon_available = False
try:
    from telethon import TelegramClient, events
    from telethon.tl.types import User, Channel, Chat
    _telethon_available = True
except ImportError:
    pass

def _build_group_map() -> dict:
    """Build identifier -> category mapping from config."""
    gmap = {}
    for category, identifiers in C.GROUPS.items():
        for ident in identifiers:
            gmap[ident] = category
    for category, identifiers in C.CHANNELS.items():
        for ident in identifiers:
            gmap[ident] = category
    return gmap

async def _telethon_monitor():
    """Async Telethon event loop — runs in a dedicated thread."""
    api_id = C.TELETHON_API_ID or int(os.environ.get("TG_API_ID", "0"))
    api_hash = C.TELETHON_API_HASH or os.environ.get("TG_API_HASH", "")
    if not api_id or not api_hash:
        _log("Telethon: no API credentials — Telegram monitoring disabled", "WARN")
        return

    session_path = str(_BASE_DIR / C.SESSION_NAME)
    client = TelegramClient(session_path, api_id, api_hash)
    await client.start()
    _log("Telethon: connected")

    group_map = _build_group_map()
    resolved_chats = []
    chat_categories = {}

    for identifier, category in group_map.items():
        try:
            entity = await client.get_entity(identifier)
            eid = entity.id
            resolved_chats.append(eid)
            chat_name = getattr(entity, 'title', getattr(entity, 'username', str(eid)))
            chat_categories[eid] = (category, chat_name)
            _log(f"Telethon: resolved {identifier} → {chat_name} ({category})")
        except Exception as e:
            _log(f"Telethon: failed to resolve {identifier}: {e}", "WARN")

    if not resolved_chats:
        _log("Telethon: no chats resolved — monitoring disabled", "WARN")
        await client.disconnect()
        return

    @client.on(events.NewMessage(chats=resolved_chats))
    async def _on_message(event):
        text = event.text or ""
        if not text.strip():
            return

        with _state_lock:
            _stats["tg_messages"] += 1

        # Extract sender info
        sender = await event.get_sender()
        sender_id = str(getattr(sender, 'id', ''))
        sender_name = ""
        is_bot = False
        if isinstance(sender, User):
            sender_name = sender.username or f"{sender.first_name or ''} {sender.last_name or ''}".strip()
            is_bot = sender.bot or False
        elif hasattr(sender, 'title'):
            sender_name = sender.title

        # Reply/forward info
        is_reply = event.is_reply
        is_forward_from_bot = False
        is_deep_reply = False
        if event.forward and hasattr(event.forward, 'sender') and event.forward.sender:
            is_forward_from_bot = getattr(event.forward.sender, 'bot', False)
        if is_reply:
            try:
                reply_msg = await event.get_reply_message()
                if reply_msg and reply_msg.is_reply:
                    is_deep_reply = True
            except Exception:
                pass

        # Chat category
        chat_id = event.chat_id
        category, chat_name = chat_categories.get(chat_id, ("general", "unknown"))

        process_signal(
            text=text,
            source_type="telegram",
            source_name=chat_name,
            sender=sender_name or sender_id,
            group_category=category,
            is_reply=is_reply,
            is_forward_from_bot=is_forward_from_bot,
            is_deep_reply=is_deep_reply,
        )

    _log(f"Telethon: monitoring {len(resolved_chats)} chats")
    await client.run_until_disconnected()

def _start_telethon_thread():
    """Start Telethon in a dedicated thread with its own event loop."""
    import asyncio
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_telethon_monitor())
        except Exception as e:
            _log(f"Telethon thread error: {e}", "ERROR")
            traceback.print_exc()
    t = threading.Thread(target=_run, daemon=True, name="telethon")
    t.start()
    return t

# ═══════════════════════════════════════════════════════════════════════
#  6551.io OPENNEWS WEBSOCKET COLLECTOR
# ═══════════════════════════════════════════════════════════════════════
async def _opennews_monitor():
    """WebSocket listener for 6551.io OpenNews — runs in dedicated thread."""
    global _opennews_ws_alive
    import asyncio
    try:
        import websockets
    except ImportError:
        _log("OpenNews: websockets not installed — run: pip install websockets", "WARN")
        return

    backoff_secs = [5, 10, 30, 60]
    attempt = 0

    while True:
        ws_url = f"{C.OPENNEWS_WSS_URL}?token={C.OPENNEWS_TOKEN}"
        try:
            async with websockets.connect(ws_url, ping_interval=30, ping_timeout=10) as ws:
                _opennews_ws_alive = True
                attempt = 0
                _log("OpenNews: WebSocket connected")

                # Subscribe to news updates
                engine_filter = {et: [] for et in C.OPENNEWS_ENGINE_TYPES}
                subscribe_msg = json.dumps({
                    "method": "news.subscribe",
                    "params": {"engineTypes": engine_filter, "hasCoin": False},
                })
                await ws.send(subscribe_msg)
                _log(f"OpenNews: subscribed to {C.OPENNEWS_ENGINE_TYPES}")

                # Pending articles waiting for AI rating
                pending: dict[str, dict] = {}  # news_id -> article data

                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        continue

                    method = msg.get("method", "")

                    if method == "news.update":
                        # New article arrived
                        params = msg.get("params", {})
                        news_id = str(params.get("id", params.get("newsId", "")))
                        text = params.get("text", params.get("title", ""))
                        news_type = params.get("newsType", "opennews")
                        engine_type = params.get("engineType", "")
                        link = params.get("link", "")

                        if text and news_id:
                            pending[news_id] = {
                                "text": text,
                                "newsType": news_type,
                                "engineType": engine_type,
                                "link": link,
                                "coins": params.get("coins", []),
                            }
                            # Evict old pending entries (keep last 200)
                            if len(pending) > 200:
                                oldest = list(pending.keys())[:100]
                                for k in oldest:
                                    del pending[k]

                    elif method == "news.ai_update":
                        # AI rating for a previously received article
                        params = msg.get("params", {})
                        news_id = str(params.get("id", params.get("newsId", "")))
                        ai_rating = params.get("aiRating", {})
                        score = ai_rating.get("score", 0)
                        signal = ai_rating.get("signal", "neutral")
                        en_summary = ai_rating.get("enSummary", "")

                        article = pending.pop(news_id, None)
                        if article and score >= C.OPENNEWS_MIN_SCORE:
                            display_text = en_summary or article["text"]
                            with _state_lock:
                                _source_status["opennews_ws"] = time.time()
                            process_signal(
                                text=display_text,
                                source_type="opennews",
                                source_name=article["newsType"],
                                group_category="opennews",
                            )
                            _log(f"OpenNews WS: score={score} signal={signal} src={article['newsType']}")

        except Exception as e:
            _opennews_ws_alive = False
            delay = backoff_secs[min(attempt, len(backoff_secs) - 1)]
            _log(f"OpenNews WS disconnected: {e} — reconnecting in {delay}s", "WARN")
            attempt += 1
            await asyncio.sleep(delay)


def _start_opennews_thread():
    """Start 6551.io WebSocket in a dedicated thread."""
    import asyncio
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_opennews_monitor())
        except Exception as e:
            _log(f"OpenNews thread error: {e}", "ERROR")
            traceback.print_exc()
    t = threading.Thread(target=_run, daemon=True, name="opennews_ws")
    t.start()
    return t

# ═══════════════════════════════════════════════════════════════════════
#  PUBLIC API — query functions
# ═══════════════════════════════════════════════════════════════════════
def get_latest_signals(hours: float = 6, affects: str = "", direction: str = "",
                       min_mag: float = 0.0, limit: int = 50) -> list[dict]:
    """Get filtered signals."""
    cutoff = time.time() - hours * 3600
    with _state_lock:
        results = []
        for s in reversed(_signals):
            if s["ts"] < cutoff:
                break
            if affects and affects not in s.get("affects", []):
                continue
            if direction and s.get("direction") != direction:
                continue
            if s.get("magnitude", 0) < min_mag:
                continue
            results.append(s)
            if len(results) >= limit:
                break
    return results

def get_sentiment(hours: float = 6) -> dict:
    """Get aggregate sentiment over time window."""
    cutoff = time.time() - hours * 3600
    sentiments = []
    with _state_lock:
        for s in reversed(_signals):
            if s["ts"] < cutoff:
                break
            sentiments.append(s.get("sentiment", 0))
    if not sentiments:
        return {"sentiment": 0.0, "regime": "neutral", "count": 0}
    avg = sum(sentiments) / len(sentiments)
    regime = "bullish" if avg > 0.15 else ("bearish" if avg < -0.15 else "neutral")
    return {"sentiment": round(avg, 3), "regime": regime, "count": len(sentiments)}

def get_regime(hours: float = 6) -> dict:
    """Get market regime based on recent signals."""
    s = get_sentiment(hours)
    return {"regime": s["regime"], "sentiment": s["sentiment"]}

def get_event_counts(hours: float = 6) -> dict:
    """Count event types in time window."""
    cutoff = time.time() - hours * 3600
    counts = defaultdict(int)
    with _state_lock:
        for s in reversed(_signals):
            if s["ts"] < cutoff:
                break
            counts[s["event_type"]] += 1
    return dict(counts)

def get_polymarket() -> list[dict]:
    with _state_lock:
        return list(_polymarket)

def get_signals_summary(hours: float = 6) -> dict:
    """All-in-one summary for downstream skills."""
    sigs = get_latest_signals(hours=hours, limit=100)
    sent = get_sentiment(hours)
    events = get_event_counts(hours)
    return {
        "sentiment": sent["sentiment"],
        "regime": sent["regime"],
        "signal_count": len(sigs),
        "event_counts": events,
        "top_events": sorted(events.items(), key=lambda x: -x[1])[:5],
        "polymarket": get_polymarket(),
        "latest_signals": sigs[:10],
    }

def get_top_senders(limit: int = 10) -> list[dict]:
    """Reputation leaderboard."""
    with _state_lock:
        items = [(sid, r["score"], r.get("hits", 0)) for sid, r in _reputation.items()]
    items.sort(key=lambda x: -x[1])
    return [{"sender": s, "score": round(sc, 2), "hits": h}
            for s, sc, h in items[:limit]]

def get_source_breakdown() -> dict:
    """Active sources with last-seen timestamps."""
    with _state_lock:
        return {k: {"last_seen": int(v), "ago_sec": int(time.time() - v)}
                for k, v in _source_status.items()}

# ═══════════════════════════════════════════════════════════════════════
#  DASHBOARD HTTP SERVER
# ═══════════════════════════════════════════════════════════════════════
def _dashboard_api_data() -> dict:
    """Full dashboard state."""
    now = time.time()
    sent = get_sentiment(6)
    with _state_lock:
        recent = list(reversed(_signals[-50:]))
        stats_copy = dict(_stats)
        sources = dict(_source_status)
    return {
        "ts": int(now),
        "uptime_sec": int(now - stats_copy.get("start_ts", now)),
        "regime": sent["regime"],
        "sentiment": sent["sentiment"],
        "signals": recent,
        "stats": stats_copy,
        "polymarket": get_polymarket(),
        "event_counts": get_event_counts(6),
        "top_senders": get_top_senders(10),
        "source_status": {k: {"last_seen": int(v), "ago_sec": int(now - v)}
                          for k, v in sources.items()},
        "telethon_active": _telethon_available,
        "fear_greed": _fear_greed,
        "fred_indicators": _fred_indicators,
        "price_tickers": _price_tickers,
    }

class _DashboardHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress HTTP logs

    def _json_response(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        def _p(key, default):
            return params.get(key, [default])[0]

        if path == "/" or path == "/index.html":
            html_path = _BASE_DIR / "dashboard.html"
            if html_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(html_path.read_bytes())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"dashboard.html not found")
            return

        if path == "/api/state":
            self._json_response(_dashboard_api_data())
        elif path == "/api/signals":
            sigs = get_latest_signals(
                hours=float(_p("hours", "6")),
                affects=_p("affects", ""),
                direction=_p("direction", ""),
                min_mag=float(_p("min_mag", "0")),
                limit=int(_p("limit", "50")),
            )
            self._json_response(sigs)
        elif path == "/api/sentiment":
            self._json_response(get_sentiment(float(_p("hours", "6"))))
        elif path == "/api/regime":
            self._json_response(get_regime(float(_p("hours", "6"))))
        elif path == "/api/polymarket":
            self._json_response(get_polymarket())
        elif path == "/api/fng":
            self._json_response(_fear_greed)
        elif path == "/api/fred":
            with _state_lock:
                self._json_response(dict(_fred_indicators))
        elif path == "/api/prices":
            with _state_lock:
                self._json_response(dict(_price_tickers))
        elif path == "/api/senders":
            self._json_response(get_top_senders(int(_p("limit", "10"))))
        elif path == "/api/events":
            self._json_response(get_event_counts(float(_p("hours", "6"))))
        elif path == "/api/summary":
            self._json_response(get_signals_summary(float(_p("hours", "6"))))
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

# ═══════════════════════════════════════════════════════════════════════
#  SETUP MODE — list Telegram groups
# ═══════════════════════════════════════════════════════════════════════
async def _setup_mode():
    """Interactive: list all Telegram groups/channels for config."""
    api_id = C.TELETHON_API_ID or int(os.environ.get("TG_API_ID", "0"))
    api_hash = C.TELETHON_API_HASH or os.environ.get("TG_API_HASH", "")
    if not api_id or not api_hash:
        print("Set TELETHON_API_ID and TELETHON_API_HASH in config.py first.")
        return

    client = TelegramClient(str(_BASE_DIR / C.SESSION_NAME), api_id, api_hash)
    await client.start()
    print("\nYour Telegram Groups & Channels:\n")
    print(f"{'Type':<10} {'ID':<20} {'Title'}")
    print("-" * 60)

    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if isinstance(entity, (Channel, Chat)):
            dtype = "channel" if getattr(entity, 'broadcast', False) else "group"
            print(f"{dtype:<10} {entity.id:<20} {dialog.name}")

    await client.disconnect()
    print("\nAdd IDs or usernames to config.py GROUPS/CHANNELS dicts.")

# ═══════════════════════════════════════════════════════════════════════
#  COMPILE REGEX CACHES
# ═══════════════════════════════════════════════════════════════════════
def _compile_patterns():
    """Pre-compile all regex patterns for performance."""
    global _macro_regex, _noise_regex
    for event_type, patterns in C.MACRO_KEYWORDS.items():
        _macro_regex[event_type] = [re.compile(p) for p in patterns]
    _noise_regex = [re.compile(p, re.IGNORECASE) for p in C.NOISE_SKIP_PATTERNS]

# ═══════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════
def main():
    # Setup mode
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        if not _telethon_available:
            print("Install telethon first: pip install telethon")
            return
        import asyncio
        asyncio.run(_setup_mode())
        return

    _compile_patterns()
    _load_state()
    _stats["start_ts"] = time.time()

    _log("=" * 50)
    _log("Macro Intelligence Skill v1.0 — Intelligence Feed")
    _log(f"Dashboard: http://localhost:{C.DASHBOARD_PORT}")
    _log(f"Telethon: {'available' if _telethon_available else 'NOT installed'}")
    _log(f"OpenNews: {'enabled' if C.OPENNEWS_ENABLED and C.OPENNEWS_TOKEN else 'disabled'}")
    _log(f"Finnhub:  {'enabled' if C.FINNHUB_ENABLED and C.FINNHUB_API_KEY else 'disabled'}")
    _log(f"FRED:     {'enabled' if C.FRED_ENABLED and C.FRED_API_KEY else 'disabled'}")
    _log("=" * 50)

    # Start news collector thread
    news_thread = threading.Thread(target=_news_collector_loop, daemon=True, name="news_collector")
    news_thread.start()

    # Start Telegram collector (if available)
    if _telethon_available:
        _start_telethon_thread()
    else:
        _log("Telethon not installed — run: pip install telethon", "WARN")

    # Start 6551.io OpenNews WebSocket (if configured)
    if C.OPENNEWS_ENABLED and C.OPENNEWS_TOKEN:
        _start_opennews_thread()
        _log("OpenNews: WebSocket thread started")
    else:
        _log("OpenNews: disabled (no OPENNEWS_TOKEN)", "WARN")

    # Start HTTP dashboard
    server = HTTPServer(("0.0.0.0", C.DASHBOARD_PORT), _DashboardHandler)
    _log(f"HTTP server listening on :{C.DASHBOARD_PORT}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log("Shutting down...")
        _save_state()
        server.shutdown()

if __name__ == "__main__":
    main()
