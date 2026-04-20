from __future__ import annotations

import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from .base_engine import BaseNeuralEngine, NeuralAnalysis
from .engine_factory import NeuralEngineFactory

logger = logging.getLogger(__name__)


class ConsensusNeuralEngine(BaseNeuralEngine):
    """Runs analysis through multiple AI providers and requires consensus."""

    def __init__(self, providers: List[str] = None, consensus_mode: str = "majority"):
        self.engines = []
        providers = providers or ["claude", "openai"]
        for provider_name in providers:
            try:
                self.engines.append(NeuralEngineFactory.create(provider=provider_name))
            except Exception as exc:
                logger.warning("Could not initialize %s engine: %s", provider_name, exc)

        if not self.engines:
            raise ValueError("No AI engines could be initialized")

        self.consensus_mode = consensus_mode

    def _consensus_direction(self, directions: List[str]) -> Optional[str]:
        counts = Counter(directions)
        top, count = counts.most_common(1)[0]
        if self.consensus_mode == "unanimous":
            return top if count == len(directions) else None
        return top if count > len(directions) / 2 else None

    def analyze_trade(self, ticker, market_data, signals, sentiment=None, regime=None) -> NeuralAnalysis:
        results: List[NeuralAnalysis] = []
        with ThreadPoolExecutor(max_workers=len(self.engines)) as executor:
            futures = [
                executor.submit(engine.analyze_trade, ticker, market_data, signals, sentiment, regime)
                for engine in self.engines
            ]
            for future in as_completed(futures):
                results.append(future.result())

        directions = [result.direction for result in results]
        agreed_direction = self._consensus_direction(directions)
        reasoning_map = [f"{result.provider}:{result.reasoning}" for result in results]

        if not agreed_direction:
            logger.info("Neural disagreement for %s: %s", ticker, reasoning_map)
            return NeuralAnalysis(
                direction="NEUTRAL",
                confidence=0.0,
                reasoning=f"Providers disagreed: {' | '.join(reasoning_map)}",
                key_factors=["provider_disagreement"],
                risk_assessment="HIGH",
                suggested_position_size=0.0,
                suggested_sl_pct=None,
                suggested_tp_pct=None,
                market_context="Consensus unavailable",
                contrarian_view="Disagreement across providers",
                raw_response="\n\n".join(r.raw_response for r in results),
                provider="consensus",
                model=",".join(r.model for r in results),
                tokens_used=sum(r.tokens_used for r in results),
                latency_ms=max(r.latency_ms for r in results),
            )

        agreeing = [r for r in results if r.direction == agreed_direction]
        base_conf = sum(r.confidence for r in agreeing) / max(len(agreeing), 1)
        boosted_conf = min(1.0, base_conf * 1.15)
        risk_levels = [r.risk_assessment for r in agreeing]
        merged_risk = sorted(risk_levels, key=lambda x: ["LOW", "MEDIUM", "HIGH", "EXTREME"].index(x) if x in ["LOW", "MEDIUM", "HIGH", "EXTREME"] else 4)[-1]

        return NeuralAnalysis(
            direction=agreed_direction,
            confidence=boosted_conf,
            reasoning="Consensus reached. " + " | ".join(reasoning_map),
            key_factors=list({factor for result in agreeing for factor in result.key_factors})[:5],
            risk_assessment=merged_risk,
            suggested_position_size=min(1.0, sum(r.suggested_position_size for r in agreeing) / max(len(agreeing), 1)),
            suggested_sl_pct=agreeing[0].suggested_sl_pct,
            suggested_tp_pct=agreeing[0].suggested_tp_pct,
            market_context=agreeing[0].market_context,
            contrarian_view=" | ".join(r.contrarian_view for r in agreeing),
            raw_response="\n\n".join(r.raw_response for r in results),
            provider="consensus",
            model=",".join(r.model for r in results),
            tokens_used=sum(r.tokens_used for r in results),
            latency_ms=max(r.latency_ms for r in results),
        )

    def analyze_portfolio(self, positions: List[Dict[str, Any]], market_overview: Dict[str, Any]) -> Dict[str, Any]:
        responses = [engine.analyze_portfolio(positions, market_overview) for engine in self.engines]
        return {"provider_count": len(self.engines), "responses": responses}

    def explain_trade(self, trade_record: Dict[str, Any]) -> str:
        explanations = [engine.explain_trade(trade_record) for engine in self.engines]
        return "\n".join(explanations)

    def generate_market_brief(self, watchlist: List[str], market_data: Dict[str, Any]) -> str:
        briefs = [engine.generate_market_brief(watchlist, market_data) for engine in self.engines]
        return "\n".join(briefs)
