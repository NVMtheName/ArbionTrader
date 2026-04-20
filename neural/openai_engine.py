from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .base_engine import AIProvider, BaseNeuralEngine, NeuralAnalysis
from .common import RedisCache, RateLimitQueue, retry_with_backoff, update_usage
from .prompts import (
    TRADING_SYSTEM_PROMPT,
    build_market_brief_prompt,
    build_portfolio_review_prompt,
    build_trade_analysis_prompt,
    build_trade_explanation_prompt,
)

logger = logging.getLogger(__name__)


class OpenAINeuralEngine(BaseNeuralEngine):
    def __init__(self, model: str = None, max_tokens: int = 2048):
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
        self.max_tokens = max_tokens
        self.provider = AIProvider.OPENAI
        self.cache = RedisCache()
        self.queue = RateLimitQueue(max_concurrent=1)

    def _invoke_json(self, user_prompt: str) -> Dict[str, Any]:
        start = time.time()
        request_payload = {
            "provider": self.provider.value,
            "model": self.model,
            "prompt": user_prompt,
        }
        cache_key = self.cache.key(request_payload)
        cached = self.cache.get(cache_key)
        if cached:
            return json.loads(cached)

        def _call():
            return self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": TRADING_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )

        response = retry_with_backoff(lambda: self.queue.run(_call))
        raw_response = response.choices[0].message.content
        parsed = json.loads(raw_response)

        latency = (time.time() - start) * 1000
        input_tokens = getattr(response.usage, "prompt_tokens", 0)
        output_tokens = getattr(response.usage, "completion_tokens", 0)
        cost = update_usage(self.provider.value, input_tokens, output_tokens, latency, self.model)

        envelope = {
            "parsed": parsed,
            "raw": raw_response,
            "latency_ms": latency,
            "tokens_used": input_tokens + output_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
        }
        self.cache.set(cache_key, json.dumps(envelope))
        logger.info("Neural(%s) model=%s tokens=%s cost=$%.6f latency=%.2fms", self.provider.value, self.model, envelope["tokens_used"], cost, latency)
        return envelope

    def _neutral(self, reason: str) -> NeuralAnalysis:
        return NeuralAnalysis(
            direction="NEUTRAL",
            confidence=0.0,
            reasoning=reason,
            key_factors=["engine_failure"],
            risk_assessment="EXTREME",
            suggested_position_size=0.0,
            suggested_sl_pct=None,
            suggested_tp_pct=None,
            market_context="Unable to analyze",
            contrarian_view="System failure; no trade",
            raw_response="",
            provider=self.provider.value,
            model=self.model,
            tokens_used=0,
            latency_ms=0.0,
        )

    def analyze_trade(
        self,
        ticker: str,
        market_data: Dict[str, Any],
        signals: Dict[str, Any],
        sentiment: Optional[Dict[str, Any]] = None,
        regime: Optional[str] = None,
    ) -> NeuralAnalysis:
        user_prompt = build_trade_analysis_prompt(ticker, market_data, signals, sentiment, regime)
        try:
            envelope = self._invoke_json(user_prompt)
            parsed = envelope["parsed"]
            return NeuralAnalysis(
                direction=parsed.get("direction", "NEUTRAL"),
                confidence=float(parsed.get("confidence", 0.0)),
                reasoning=parsed.get("reasoning", "No reasoning provided"),
                key_factors=parsed.get("key_factors", []),
                risk_assessment=parsed.get("risk_assessment", "HIGH"),
                suggested_position_size=float(parsed.get("suggested_position_size", 0.0)),
                suggested_sl_pct=parsed.get("suggested_sl_pct"),
                suggested_tp_pct=parsed.get("suggested_tp_pct"),
                market_context=parsed.get("market_context", "Unknown"),
                contrarian_view=parsed.get("contrarian_view", "Unknown"),
                raw_response=envelope["raw"],
                provider=self.provider.value,
                model=self.model,
                tokens_used=int(envelope["tokens_used"]),
                latency_ms=float(envelope["latency_ms"]),
            )
        except json.JSONDecodeError as exc:
            logger.error("OpenAI returned invalid JSON: %s", exc)
            return self._neutral(f"AI response parse error: {exc}")
        except Exception as exc:
            logger.error("OpenAI API error: %s", exc)
            return self._neutral(f"OpenAI API error: {exc}")

    def analyze_portfolio(self, positions: List[Dict[str, Any]], market_overview: Dict[str, Any]) -> Dict[str, Any]:
        try:
            prompt = build_portfolio_review_prompt(positions, market_overview)
            return self._invoke_json(prompt)["parsed"]
        except Exception as exc:
            logger.error("OpenAI portfolio analysis failed: %s", exc)
            return {"error": str(exc), "overall_risk": "EXTREME"}

    def explain_trade(self, trade_record: Dict[str, Any]) -> str:
        try:
            prompt = build_trade_explanation_prompt(trade_record)
            parsed = self._invoke_json(prompt)["parsed"]
            return parsed.get("lesson") or parsed.get("what_happened", "No explanation available")
        except Exception as exc:
            logger.error("OpenAI trade explanation failed: %s", exc)
            return f"Unable to explain trade: {exc}"

    def generate_market_brief(self, watchlist: List[str], market_data: Dict[str, Any]) -> str:
        try:
            prompt = build_market_brief_prompt(watchlist, market_data)
            parsed = self._invoke_json(prompt)["parsed"]
            return json.dumps(parsed)
        except Exception as exc:
            logger.error("OpenAI market brief failed: %s", exc)
            return json.dumps({"error": str(exc)})
