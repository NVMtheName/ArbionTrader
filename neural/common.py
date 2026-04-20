from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from collections import defaultdict
from typing import Any, Dict, Optional

import redis

logger = logging.getLogger(__name__)

USAGE_STATE: Dict[str, Dict[str, float]] = defaultdict(lambda: {
    "calls": 0,
    "tokens": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "cost_usd": 0.0,
    "total_latency_ms": 0.0,
})


def model_prices() -> Dict[str, Dict[str, float]]:
    return {
        "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
        "claude-opus-4-6": {"input": 15.0, "output": 75.0},
        "gpt-4o": {"input": 5.0, "output": 15.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "o1": {"input": 15.0, "output": 60.0},
    }


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    prices = model_prices().get(model, {"input": 10.0, "output": 30.0})
    return ((input_tokens / 1_000_000) * prices["input"]) + ((output_tokens / 1_000_000) * prices["output"])


def update_usage(provider: str, input_tokens: int, output_tokens: int, latency_ms: float, model: str) -> float:
    cost = estimate_cost_usd(model, input_tokens, output_tokens)
    state = USAGE_STATE[provider]
    state["calls"] += 1
    state["tokens"] += input_tokens + output_tokens
    state["input_tokens"] += input_tokens
    state["output_tokens"] += output_tokens
    state["cost_usd"] += cost
    state["total_latency_ms"] += latency_ms
    return cost


def usage_snapshot() -> Dict[str, Dict[str, float]]:
    out = {}
    for provider, state in USAGE_STATE.items():
        calls = max(int(state["calls"]), 1)
        out[provider] = {
            **state,
            "avg_latency_ms": state["total_latency_ms"] / calls,
        }
    return out


class RedisCache:
    def __init__(self):
        self.ttl = int(os.environ.get("NEURAL_CACHE_TTL", "300"))
        self.client = None
        try:
            self.client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/1"))
            self.client.ping()
        except Exception as exc:
            logger.warning("Neural Redis cache unavailable: %s", exc)
            self.client = None

    def key(self, payload: Dict[str, Any]) -> str:
        stable = json.dumps(payload, sort_keys=True, default=str)
        return f"neural:{hashlib.sha256(stable.encode('utf-8')).hexdigest()}"

    def get(self, key: str) -> Optional[str]:
        if not self.client:
            return None
        value = self.client.get(key)
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value

    def set(self, key: str, value: str) -> None:
        if not self.client:
            return
        self.client.setex(key, self.ttl, value)


class RateLimitQueue:
    """Simple in-process queue by serializing provider calls with a semaphore."""

    def __init__(self, max_concurrent: int = 1):
        self._sem = threading.BoundedSemaphore(max_concurrent)

    def run(self, fn, *args, **kwargs):
        with self._sem:
            return fn(*args, **kwargs)


def retry_with_backoff(func, retries: int = None):
    retries = retries or int(os.environ.get("NEURAL_MAX_RETRIES", "3"))
    delays = [1, 2, 4]
    last_exc = None
    for attempt in range(retries):
        try:
            return func()
        except Exception as exc:
            last_exc = exc
            transient = any(k in str(exc).lower() for k in ["timeout", "rate", "429", "temporar", "connection"])
            if attempt >= retries - 1 or not transient:
                raise
            time.sleep(delays[min(attempt, len(delays) - 1)])
    raise last_exc
