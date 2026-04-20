"""Anthropic Claude implementation of the Neural Engine."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

from .base_engine import AIProvider, BaseNeuralEngine, NeuralAnalysis
from ._common import (
    CallRecord,
    cache_get,
    cache_set,
    call_with_retry,
    estimate_cost_usd,
    extract_json,
    usage_tracker,
)
from .prompts import (
    TRADING_SYSTEM_PROMPT,
    build_market_brief_prompt,
    build_portfolio_review_prompt,
    build_strategy_optimization_prompt,
    build_trade_analysis_prompt,
    build_trade_explanation_prompt,
)

logger = logging.getLogger(__name__)


# Retryable error classes — fall back to bare Exception if anthropic changes.
try:
    from anthropic import APIError, APIConnectionError, APIStatusError, RateLimitError  # type: ignore
    _RETRYABLE = (APIError, APIConnectionError, APIStatusError, RateLimitError)
except Exception:  # pragma: no cover - defensive
    _RETRYABLE = (Exception,)


class ClaudeNeuralEngine(BaseNeuralEngine):
    """Claude-backed trading analyst."""

    def __init__(self, model: Optional[str] = None, max_tokens: int = 2048):
        self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model or os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
        self.max_tokens = max_tokens
        self.provider = AIProvider.CLAUDE
        self.cache_ttl = int(os.environ.get("NEURAL_CACHE_TTL", "300"))

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _call(self, system: str, user: str) -> Dict[str, Any]:
        """Invoke Claude with retry; return raw_response, tokens, latency."""
        start = time.time()

        def _do():
            return self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )

        message = call_with_retry(_do, retries=3, base_delay=1.0, retryable_exceptions=_RETRYABLE)
        latency_ms = (time.time() - start) * 1000.0

        parts = [getattr(b, "text", "") for b in message.content if getattr(b, "type", "text") == "text"]
        raw_response = "".join(parts) or (message.content[0].text if message.content else "")
        input_tokens = getattr(message.usage, "input_tokens", 0)
        output_tokens = getattr(message.usage, "output_tokens", 0)
        return {
            "raw_response": raw_response,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "tokens_used": input_tokens + output_tokens,
            "latency_ms": latency_ms,
        }

    def _record(self, kind: str, result: Dict[str, Any], success: bool, cached: bool, error: Optional[str] = None) -> float:
        cost = estimate_cost_usd(
            self.model, result.get("input_tokens", 0), result.get("output_tokens", 0)
        ) if not cached else 0.0
        usage_tracker.record(CallRecord(
            ts=time.time(),
            provider=self.provider.value,
            model=self.model,
            kind=kind,
            tokens=result.get("tokens_used", 0),
            latency_ms=result.get("latency_ms", 0.0),
            cost_usd=cost,
            cached=cached,
            success=success,
            error=error,
        ))
        return cost

    # ------------------------------------------------------------------ #
    # BaseNeuralEngine implementation
    # ------------------------------------------------------------------ #

    def analyze_trade(
        self,
        ticker: str,
        market_data: Dict,
        signals: Dict,
        sentiment: Optional[Dict] = None,
        regime: Optional[str] = None,
    ) -> NeuralAnalysis:
        user_prompt = build_trade_analysis_prompt(ticker, market_data, signals, sentiment, regime)
        cache_payload = {"t": ticker, "m": market_data, "s": signals, "se": sentiment, "r": regime}

        cached_raw = cache_get(self.provider.value, self.model, "trade", cache_payload)
        if cached_raw:
            try:
                parsed = json.loads(cached_raw)
                result = {"raw_response": cached_raw, "tokens_used": 0, "latency_ms": 0.0,
                          "input_tokens": 0, "output_tokens": 0}
                self._record("trade", result, success=True, cached=True)
                return self._to_analysis(parsed, cached_raw, result, cached=True)
            except Exception:
                pass  # Fall through to fresh call

        try:
            result = self._call(TRADING_SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            logger.error("Claude analyze_trade API error: %s", e)
            self._record("trade", {"tokens_used": 0, "latency_ms": 0.0}, success=False, cached=False, error=str(e))
            return self._error_analysis(f"Claude API error: {e}", raw="", tokens=0, latency=0.0)

        raw = result["raw_response"]
        try:
            parsed = extract_json(raw)
        except Exception as e:
            logger.error("Claude returned invalid JSON: %s", e)
            self._record("trade", result, success=False, cached=False, error=f"json: {e}")
            return self._error_analysis(
                f"AI response parse error: {e}",
                raw=raw,
                tokens=result["tokens_used"],
                latency=result["latency_ms"],
            )

        cost = self._record("trade", result, success=True, cached=False)
        cache_set(self.provider.value, self.model, "trade", cache_payload, raw, ttl=self.cache_ttl)
        analysis = self._to_analysis(parsed, raw, result, cached=False)
        analysis.cost_usd = cost
        return analysis

    def analyze_portfolio(self, positions: List[Dict], market_overview: Dict) -> Dict:
        user_prompt = build_portfolio_review_prompt(positions, market_overview)
        cache_payload = {"p": positions, "m": market_overview}

        cached_raw = cache_get(self.provider.value, self.model, "portfolio", cache_payload)
        if cached_raw:
            try:
                parsed = json.loads(cached_raw)
                self._record("portfolio", {"tokens_used": 0, "latency_ms": 0.0}, success=True, cached=True)
                return {**parsed, "_meta": {"cached": True, "provider": self.provider.value, "model": self.model}}
            except Exception:
                pass

        try:
            result = self._call(TRADING_SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            logger.error("Claude analyze_portfolio API error: %s", e)
            self._record("portfolio", {"tokens_used": 0, "latency_ms": 0.0}, success=False, cached=False, error=str(e))
            raise

        raw = result["raw_response"]
        try:
            parsed = extract_json(raw)
        except Exception as e:
            logger.error("Claude portfolio review invalid JSON: %s", e)
            self._record("portfolio", result, success=False, cached=False, error=f"json: {e}")
            raise ValueError(f"Claude portfolio review returned invalid JSON: {e}")

        cost = self._record("portfolio", result, success=True, cached=False)
        cache_set(self.provider.value, self.model, "portfolio", cache_payload, raw, ttl=self.cache_ttl)
        return {
            **parsed,
            "_meta": {
                "cached": False,
                "provider": self.provider.value,
                "model": self.model,
                "tokens_used": result["tokens_used"],
                "latency_ms": result["latency_ms"],
                "cost_usd": cost,
            },
        }

    def explain_trade(self, trade_record: Dict) -> str:
        user_prompt = build_trade_explanation_prompt(trade_record)
        cache_payload = {"tr": trade_record}

        cached_raw = cache_get(self.provider.value, self.model, "explain", cache_payload)
        if cached_raw:
            self._record("explain", {"tokens_used": 0, "latency_ms": 0.0}, success=True, cached=True)
            return cached_raw

        try:
            result = self._call(TRADING_SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            logger.error("Claude explain_trade API error: %s", e)
            self._record("explain", {"tokens_used": 0, "latency_ms": 0.0}, success=False, cached=False, error=str(e))
            raise

        self._record("explain", result, success=True, cached=False)
        cache_set(self.provider.value, self.model, "explain", cache_payload, result["raw_response"], ttl=self.cache_ttl)
        return result["raw_response"]

    def generate_market_brief(self, watchlist: List[str], market_data: Dict) -> str:
        user_prompt = build_market_brief_prompt(watchlist, market_data)
        cache_payload = {"w": watchlist, "m": market_data}

        cached_raw = cache_get(self.provider.value, self.model, "brief", cache_payload)
        if cached_raw:
            self._record("brief", {"tokens_used": 0, "latency_ms": 0.0}, success=True, cached=True)
            return cached_raw

        try:
            result = self._call(TRADING_SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            logger.error("Claude generate_market_brief API error: %s", e)
            self._record("brief", {"tokens_used": 0, "latency_ms": 0.0}, success=False, cached=False, error=str(e))
            raise

        self._record("brief", result, success=True, cached=False)
        cache_set(self.provider.value, self.model, "brief", cache_payload, result["raw_response"], ttl=self.cache_ttl)
        return result["raw_response"]

    def optimize_strategy(self, backtest_results: Dict, current_params: Dict) -> Dict:
        user_prompt = build_strategy_optimization_prompt(backtest_results, current_params)
        try:
            result = self._call(TRADING_SYSTEM_PROMPT, user_prompt)
        except Exception as e:
            logger.error("Claude optimize_strategy API error: %s", e)
            self._record("optimize", {"tokens_used": 0, "latency_ms": 0.0}, success=False, cached=False, error=str(e))
            raise

        try:
            parsed = extract_json(result["raw_response"])
        except Exception as e:
            self._record("optimize", result, success=False, cached=False, error=f"json: {e}")
            raise ValueError(f"Claude strategy optimization returned invalid JSON: {e}")

        cost = self._record("optimize", result, success=True, cached=False)
        return {
            **parsed,
            "_meta": {
                "provider": self.provider.value,
                "model": self.model,
                "tokens_used": result["tokens_used"],
                "latency_ms": result["latency_ms"],
                "cost_usd": cost,
            },
        }

    # ------------------------------------------------------------------ #
    # Response mapping
    # ------------------------------------------------------------------ #

    def _to_analysis(
        self,
        parsed: Dict[str, Any],
        raw: str,
        result: Dict[str, Any],
        cached: bool,
    ) -> NeuralAnalysis:
        return NeuralAnalysis(
            direction=parsed.get("direction", "NEUTRAL"),
            confidence=float(parsed.get("confidence", 0.0)),
            reasoning=parsed.get("reasoning", ""),
            key_factors=list(parsed.get("key_factors", [])),
            risk_assessment=parsed.get("risk_assessment", "HIGH"),
            suggested_position_size=float(parsed.get("suggested_position_size", 0.0)),
            suggested_sl_pct=parsed.get("suggested_sl_pct"),
            suggested_tp_pct=parsed.get("suggested_tp_pct"),
            market_context=parsed.get("market_context", ""),
            contrarian_view=parsed.get("contrarian_view", ""),
            raw_response=raw,
            provider=self.provider.value,
            model=self.model,
            tokens_used=result.get("tokens_used", 0),
            latency_ms=result.get("latency_ms", 0.0),
            cached=cached,
        )

    def _error_analysis(self, reason: str, raw: str, tokens: int, latency: float) -> NeuralAnalysis:
        # Safe default on any failure: never trade on bad data.
        return NeuralAnalysis(
            direction="NEUTRAL",
            confidence=0.0,
            reasoning=reason,
            key_factors=["parse_error"],
            risk_assessment="EXTREME",
            suggested_position_size=0.0,
            suggested_sl_pct=None,
            suggested_tp_pct=None,
            market_context="Unable to analyze",
            contrarian_view="System error",
            raw_response=raw,
            provider=self.provider.value,
            model=self.model,
            tokens_used=tokens,
            latency_ms=latency,
        )
