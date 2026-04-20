"""Consensus engine — runs multiple providers in parallel and requires agreement.

Conservative by design:
- Only generates a directional signal when the required consensus is met.
- Disagreement collapses to NEUTRAL with the underlying reasoning preserved.
- Per-provider accuracy can be tracked externally via ``record_outcome``.
"""

from __future__ import annotations

import logging
import statistics
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Deque, Dict, List, Optional

from .base_engine import AIProvider, BaseNeuralEngine, NeuralAnalysis
from .engine_factory import NeuralEngineFactory

logger = logging.getLogger(__name__)


class _AccuracyLedger:
    """In-memory ledger mapping provider -> recent trade outcomes.

    Intentionally lightweight; production deployments should persist outcomes
    to the database (see ``record_outcome`` hook below).
    """

    def __init__(self, maxlen: int = 500):
        self._records: Dict[str, Deque[Dict[str, Any]]] = defaultdict(lambda: deque(maxlen=maxlen))
        self._lock = threading.Lock()

    def record(self, provider: str, analysis: NeuralAnalysis, outcome: str, pnl_pct: Optional[float]) -> None:
        with self._lock:
            self._records[provider].append({
                "ts": time.time(),
                "direction": analysis.direction,
                "confidence": analysis.confidence,
                "outcome": outcome,  # "WIN" | "LOSS" | "SCRATCH"
                "pnl_pct": pnl_pct,
            })

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            out: Dict[str, Any] = {}
            for provider, recs in self._records.items():
                recs_list = list(recs)
                if not recs_list:
                    continue
                wins = sum(1 for r in recs_list if r["outcome"] == "WIN")
                losses = sum(1 for r in recs_list if r["outcome"] == "LOSS")
                total = wins + losses
                avg_conf = statistics.mean(r["confidence"] for r in recs_list) if recs_list else 0.0
                out[provider] = {
                    "trades": len(recs_list),
                    "wins": wins,
                    "losses": losses,
                    "win_rate": round(wins / total, 4) if total else None,
                    "avg_confidence": round(avg_conf, 3),
                }
            return out


accuracy_ledger = _AccuracyLedger()


def record_outcome(provider: str, analysis: NeuralAnalysis, outcome: str, pnl_pct: Optional[float] = None) -> None:
    """Call this after a trade resolves to attribute the outcome to its provider."""
    accuracy_ledger.record(provider, analysis, outcome, pnl_pct)


class ConsensusNeuralEngine(BaseNeuralEngine):
    """Runs analysis across multiple providers and requires agreement."""

    def __init__(
        self,
        providers: Optional[List[str]] = None,
        consensus_mode: str = "unanimous",
        confidence_bonus: float = 1.15,
    ):
        if providers is None:
            providers = []
            import os
            if os.environ.get("ANTHROPIC_API_KEY"):
                providers.append("claude")
            if os.environ.get("OPENAI_API_KEY"):
                providers.append("openai")
            if not providers:
                providers = ["claude", "openai"]  # Let factory raise with a clear error

        self.engines: List[BaseNeuralEngine] = []
        for p in providers:
            try:
                self.engines.append(NeuralEngineFactory.create(provider=p))
            except Exception as e:
                logger.warning("Consensus: could not initialize '%s' engine: %s", p, e)

        if not self.engines:
            raise ValueError("Consensus engine requires at least one working provider")

        if consensus_mode not in ("unanimous", "majority"):
            raise ValueError("consensus_mode must be 'unanimous' or 'majority'")

        self.consensus_mode = consensus_mode
        self.confidence_bonus = float(confidence_bonus)
        self.provider = AIProvider.CONSENSUS
        self.model = "+".join(
            f"{e.provider.value}:{e.model}" for e in self.engines if hasattr(e, "provider")
        )

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
        start = time.time()
        results: List[NeuralAnalysis] = self._run_parallel(
            lambda e: e.analyze_trade(ticker, market_data, signals, sentiment, regime)
        )
        if not results:
            return self._empty_neutral("All providers failed", start)

        return self._merge(results, start)

    def analyze_portfolio(self, positions: List[Dict], market_overview: Dict) -> Dict:
        results = self._run_parallel(
            lambda e: e.analyze_portfolio(positions, market_overview),
            collect_errors=True,
        )
        return {
            "provider_results": results,
            "providers": [e.provider.value for e in self.engines],
            "mode": self.consensus_mode,
        }

    def explain_trade(self, trade_record: Dict) -> str:
        # Use the first available engine — explanations are narrative, not a vote.
        for engine in self.engines:
            try:
                return engine.explain_trade(trade_record)
            except Exception as e:
                logger.warning("Consensus.explain_trade: %s failed: %s", engine.provider.value, e)
        raise RuntimeError("All providers failed to explain trade")

    def generate_market_brief(self, watchlist: List[str], market_data: Dict) -> str:
        for engine in self.engines:
            try:
                return engine.generate_market_brief(watchlist, market_data)
            except Exception as e:
                logger.warning("Consensus.generate_market_brief: %s failed: %s", engine.provider.value, e)
        raise RuntimeError("All providers failed to generate brief")

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _run_parallel(self, fn, collect_errors: bool = False):
        results = []
        with ThreadPoolExecutor(max_workers=len(self.engines)) as pool:
            future_to_engine = {pool.submit(fn, e): e for e in self.engines}
            for fut in as_completed(future_to_engine):
                engine = future_to_engine[fut]
                try:
                    results.append(fut.result())
                except Exception as e:
                    logger.error("Consensus: %s raised: %s", engine.provider.value, e)
                    if collect_errors:
                        results.append({"provider": engine.provider.value, "error": str(e)})
        return results

    def _merge(self, analyses: List[NeuralAnalysis], start: float) -> NeuralAnalysis:
        # Tally direction votes
        votes: Dict[str, List[NeuralAnalysis]] = defaultdict(list)
        for a in analyses:
            votes[a.direction].append(a)

        top_dir, top_group = max(votes.items(), key=lambda kv: len(kv[1]))
        consensus_reached = (
            (self.consensus_mode == "unanimous" and len(top_group) == len(analyses)) or
            (self.consensus_mode == "majority" and len(top_group) > len(analyses) / 2)
        )
        latency_ms = (time.time() - start) * 1000.0
        total_tokens = sum(a.tokens_used for a in analyses)
        total_cost = sum(a.cost_usd for a in analyses)
        raw_joined = "\n\n---\n\n".join(f"[{a.provider}] {a.raw_response}" for a in analyses)
        per_provider = [
            {
                "provider": a.provider,
                "model": a.model,
                "direction": a.direction,
                "confidence": a.confidence,
                "reasoning": a.reasoning,
                "latency_ms": a.latency_ms,
            }
            for a in analyses
        ]

        if not consensus_reached or top_dir == "NEUTRAL":
            summary = "; ".join(f"{a.provider}={a.direction}@{a.confidence:.2f}" for a in analyses)
            logger.info("Consensus: no agreement (%s) — returning NEUTRAL", summary)
            return NeuralAnalysis(
                direction="NEUTRAL",
                confidence=0.0,
                reasoning=f"Providers disagreed: {summary}",
                key_factors=["no_consensus"],
                risk_assessment="HIGH",
                suggested_position_size=0.0,
                suggested_sl_pct=None,
                suggested_tp_pct=None,
                market_context=analyses[0].market_context if analyses else "",
                contrarian_view=" | ".join(a.contrarian_view for a in analyses if a.contrarian_view)[:500],
                raw_response=raw_joined,
                provider=self.provider.value,
                model=self.model,
                tokens_used=total_tokens,
                latency_ms=latency_ms,
                cost_usd=total_cost,
                extra={"mode": self.consensus_mode, "providers": per_provider, "agreed": False},
            )

        avg_conf = statistics.mean(a.confidence for a in top_group)
        boosted = min(1.0, avg_conf * self.confidence_bonus)
        # For sizing, take the smaller of the agreeing providers to stay conservative.
        size = min(a.suggested_position_size for a in top_group)
        # Risk: escalate to the highest risk tier among agreeing providers.
        risk_order = ["LOW", "MEDIUM", "HIGH", "EXTREME"]
        risk = max((a.risk_assessment for a in top_group), key=lambda r: risk_order.index(r) if r in risk_order else 0)

        # Merge suggested SL/TP: use median where present
        sls = [a.suggested_sl_pct for a in top_group if a.suggested_sl_pct is not None]
        tps = [a.suggested_tp_pct for a in top_group if a.suggested_tp_pct is not None]

        leader = max(top_group, key=lambda a: a.confidence)

        return NeuralAnalysis(
            direction=top_dir,
            confidence=round(boosted, 4),
            reasoning=leader.reasoning,
            key_factors=sorted({f for a in top_group for f in a.key_factors})[:6],
            risk_assessment=risk,
            suggested_position_size=round(size, 4),
            suggested_sl_pct=round(statistics.median(sls), 4) if sls else None,
            suggested_tp_pct=round(statistics.median(tps), 4) if tps else None,
            market_context=leader.market_context,
            contrarian_view=" | ".join(a.contrarian_view for a in top_group if a.contrarian_view)[:500],
            raw_response=raw_joined,
            provider=self.provider.value,
            model=self.model,
            tokens_used=total_tokens,
            latency_ms=latency_ms,
            cost_usd=total_cost,
            extra={
                "mode": self.consensus_mode,
                "providers": per_provider,
                "agreed": True,
                "agreeing_providers": [a.provider for a in top_group],
                "bonus_applied": self.confidence_bonus,
            },
        )

    def _empty_neutral(self, reason: str, start: float) -> NeuralAnalysis:
        return NeuralAnalysis(
            direction="NEUTRAL",
            confidence=0.0,
            reasoning=reason,
            key_factors=["all_providers_failed"],
            risk_assessment="EXTREME",
            suggested_position_size=0.0,
            suggested_sl_pct=None,
            suggested_tp_pct=None,
            market_context="",
            contrarian_view="",
            raw_response="",
            provider=self.provider.value,
            model=self.model,
            tokens_used=0,
            latency_ms=(time.time() - start) * 1000.0,
        )
