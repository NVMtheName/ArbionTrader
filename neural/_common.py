"""Shared helpers for Neural Engine implementations.

Keeps retry, Redis-backed caching, cost estimation and usage metrics in one
place so provider engines stay focused on prompt assembly and response parsing.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cost table (USD per 1M tokens). Prices are approximate and provider-quoted;
# override at deploy time with env vars if pricing changes.
# ---------------------------------------------------------------------------

_DEFAULT_PRICES: Dict[str, Tuple[float, float]] = {
    # Anthropic
    "claude-opus-4-7":        (15.00, 75.00),
    "claude-opus-4-6":        (15.00, 75.00),
    "claude-opus-4":          (15.00, 75.00),
    "claude-sonnet-4-6":      (3.00, 15.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-sonnet-4":        (3.00, 15.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-haiku-4-5":       (0.80, 4.00),
    # OpenAI
    "gpt-4o":                 (2.50, 10.00),
    "gpt-4o-mini":            (0.15, 0.60),
    "gpt-4-turbo":            (10.00, 30.00),
    "gpt-4":                  (30.00, 60.00),
    "o1":                     (15.00, 60.00),
    "o1-mini":                (3.00, 12.00),
    "o3-mini":                (1.10, 4.40),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Rough cost estimate in USD for a single API call."""
    prices = _DEFAULT_PRICES.get(model)
    if prices is None:
        # Unknown model — try prefix match (e.g. "gpt-4o-2024-08-06" -> "gpt-4o")
        for key, val in _DEFAULT_PRICES.items():
            if model.startswith(key):
                prices = val
                break
    if prices is None:
        return 0.0
    in_rate, out_rate = prices
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000.0


# ---------------------------------------------------------------------------
# Redis cache (optional — degrades gracefully if Redis is unavailable)
# ---------------------------------------------------------------------------

_redis_client = None
_redis_lock = threading.Lock()


def _get_redis():
    """Lazy-initialise a shared Redis client. Returns None on failure."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    with _redis_lock:
        if _redis_client is not None:
            return _redis_client
        try:
            import redis  # type: ignore
            url = os.environ.get("NEURAL_CACHE_REDIS_URL") or os.environ.get(
                "REDIS_URL", "redis://localhost:6379/3"
            )
            client = redis.Redis.from_url(url, socket_connect_timeout=1.0, socket_timeout=1.0)
            client.ping()
            _redis_client = client
            logger.info("Neural cache: connected to Redis at %s", url)
        except Exception as e:
            logger.warning("Neural cache: Redis unavailable (%s), caching disabled", e)
            _redis_client = False  # Sentinel: tried and failed
    return _redis_client if _redis_client is not False else None


def _cache_key(provider: str, model: str, kind: str, payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    digest = hashlib.sha256(blob).hexdigest()[:24]
    return f"neural:{provider}:{model}:{kind}:{digest}"


def cache_get(provider: str, model: str, kind: str, payload: Any) -> Optional[str]:
    client = _get_redis()
    if client is None:
        return None
    try:
        raw = client.get(_cache_key(provider, model, kind, payload))
        if raw is None:
            return None
        return raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    except Exception as e:
        logger.debug("Neural cache get failed: %s", e)
        return None


def cache_set(
    provider: str,
    model: str,
    kind: str,
    payload: Any,
    value: str,
    ttl: int = 300,
) -> None:
    client = _get_redis()
    if client is None:
        return
    try:
        client.setex(_cache_key(provider, model, kind, payload), ttl, value)
    except Exception as e:
        logger.debug("Neural cache set failed: %s", e)


# ---------------------------------------------------------------------------
# Retry with exponential backoff
# ---------------------------------------------------------------------------

def call_with_retry(
    fn: Callable[[], Any],
    *,
    retries: int = 3,
    base_delay: float = 1.0,
    retryable_exceptions: Tuple[type, ...] = (Exception,),
) -> Any:
    """Invoke ``fn()`` with exponential-backoff retries on retryable errors."""
    attempt = 0
    while True:
        try:
            return fn()
        except retryable_exceptions as e:
            attempt += 1
            if attempt > retries:
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "Neural API call failed (attempt %d/%d): %s — retrying in %.1fs",
                attempt, retries, e, delay,
            )
            time.sleep(delay)


# ---------------------------------------------------------------------------
# Usage metrics — in-memory rolling stats per provider
# ---------------------------------------------------------------------------

@dataclass
class CallRecord:
    ts: float
    provider: str
    model: str
    kind: str
    tokens: int
    latency_ms: float
    cost_usd: float
    cached: bool
    success: bool
    error: Optional[str] = None


class UsageTracker:
    """Thread-safe rolling usage tracker (bounded deque per provider)."""

    def __init__(self, maxlen: int = 500):
        self._records: Deque[CallRecord] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def record(self, rec: CallRecord) -> None:
        with self._lock:
            self._records.append(rec)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            records = list(self._records)
        by_provider: Dict[str, Dict[str, Any]] = {}
        for r in records:
            slot = by_provider.setdefault(
                r.provider,
                {"calls": 0, "tokens": 0, "cost_usd": 0.0, "errors": 0, "latency_ms_sum": 0.0, "cached_hits": 0},
            )
            slot["calls"] += 1
            slot["tokens"] += r.tokens
            slot["cost_usd"] += r.cost_usd
            slot["latency_ms_sum"] += r.latency_ms
            if r.cached:
                slot["cached_hits"] += 1
            if not r.success:
                slot["errors"] += 1
        for slot in by_provider.values():
            calls = slot["calls"] or 1
            slot["avg_latency_ms"] = round(slot["latency_ms_sum"] / calls, 1)
            slot["cost_usd"] = round(slot["cost_usd"], 6)
            del slot["latency_ms_sum"]
        return {"providers": by_provider, "total_calls": len(records)}

    def recent(self, limit: int = 50) -> list:
        with self._lock:
            return [
                {
                    "ts": r.ts,
                    "provider": r.provider,
                    "model": r.model,
                    "kind": r.kind,
                    "tokens": r.tokens,
                    "latency_ms": r.latency_ms,
                    "cost_usd": r.cost_usd,
                    "cached": r.cached,
                    "success": r.success,
                    "error": r.error,
                }
                for r in list(self._records)[-limit:]
            ]


usage_tracker = UsageTracker()


# ---------------------------------------------------------------------------
# JSON extraction — strips code fences that some providers emit despite asks
# ---------------------------------------------------------------------------

def extract_json(text: str) -> Dict[str, Any]:
    """Best-effort JSON parse that tolerates markdown fencing and stray prose."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        # Trim optional language tag on first line
        newline = stripped.find("\n")
        if newline != -1 and not stripped[:newline].lstrip().startswith("{"):
            stripped = stripped[newline + 1 :]
        stripped = stripped.strip().rstrip("`").strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        # Fallback: grab the outermost {...} block
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(stripped[start : end + 1])
        raise
