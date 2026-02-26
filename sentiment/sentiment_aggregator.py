"""
Sentiment Aggregator - Weighted multi-source aggregation with momentum tracking.
Combines Finnhub, Alpha Vantage (news) and Reddit scores with configurable weights,
computes 4-hour sentiment momentum, and emits SentimentSignal dataclasses.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class SentimentSignal:
    """Unified sentiment signal consumed by the ML pipeline and API."""
    ticker: str
    score: float            # -1.0 (bearish) to 1.0 (bullish)
    momentum: float         # change in score over last 4 hours
    confidence: float       # 0.0 to 1.0
    timestamp: str          # ISO-8601
    sources_count: int


class SentimentAggregator:
    """Aggregates per-source sentiment into a single weighted signal per ticker."""

    # Source weights (must sum to 1.0 when all sources present)
    SOURCE_WEIGHTS = {
        "finnhub": 0.25,       # News — split between Finnhub & Alpha Vantage
        "alphavantage": 0.25,  # News
        "reddit": 0.30,        # Social / Reddit
        "twitter": 0.20,       # X/Twitter placeholder
    }

    # How far back to look for momentum calculation
    MOMENTUM_WINDOW_HOURS = 4

    def __init__(self):
        # Redis for historical score storage (momentum calculation)
        self._redis = None
        try:
            from app import cache
            self._redis = cache
        except Exception:
            logger.warning("Redis unavailable for sentiment aggregator; momentum will default to 0")

        # In-memory fallback for momentum history
        self._history: Dict[str, List[Dict]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def aggregate(self, analysis: Dict[str, Any]) -> SentimentSignal:
        """Aggregate a raw analysis dict (from SentimentEngine.analyze_ticker)
        into a single SentimentSignal.

        ``analysis`` is expected to have:
            - ticker: str
            - sources: {"finnhub": [...], "alphavantage": [...], "reddit": [...]}
            - sources_count: int
            - timestamp: str
        """
        ticker = analysis.get("ticker", "")
        sources = analysis.get("sources", {})

        # Compute weighted score across sources
        weighted_score, total_weight, total_confidence = self._weighted_average(sources)

        # Compute momentum
        momentum = self._compute_momentum(ticker, weighted_score)

        # Store current score for future momentum calculations
        self._store_score(ticker, weighted_score)

        return SentimentSignal(
            ticker=ticker,
            score=round(max(-1.0, min(1.0, weighted_score)), 4),
            momentum=round(max(-1.0, min(1.0, momentum)), 4),
            confidence=round(min(1.0, total_confidence), 4),
            timestamp=datetime.utcnow().isoformat(),
            sources_count=analysis.get("sources_count", 0),
        )

    def aggregate_batch(self, analyses: Dict[str, Dict]) -> Dict[str, SentimentSignal]:
        """Aggregate multiple tickers. Input: {ticker: analysis_dict}."""
        signals = {}
        for ticker, analysis in analyses.items():
            signals[ticker] = self.aggregate(analysis)
        return signals

    def get_trending(self, signals: Dict[str, SentimentSignal], top_n: int = 10) -> List[SentimentSignal]:
        """Return top-N tickers sorted by absolute momentum (most momentum first)."""
        sorted_signals = sorted(
            signals.values(),
            key=lambda s: abs(s.momentum),
            reverse=True,
        )
        return sorted_signals[:top_n]

    # ------------------------------------------------------------------
    # Weighted average
    # ------------------------------------------------------------------
    def _weighted_average(self, sources: Dict[str, List[Dict]]):
        """Compute weighted-average score across all present sources.

        Returns (weighted_score, total_weight, avg_confidence).
        """
        weighted_sum = 0.0
        total_weight = 0.0
        all_confidences: List[float] = []

        for source_name, items in sources.items():
            if not items:
                continue
            weight = self.SOURCE_WEIGHTS.get(source_name, 0.1)
            # Average score within this source
            source_scores = [i["score"] for i in items if "score" in i]
            source_confs = [i["confidence"] for i in items if "confidence" in i]
            if not source_scores:
                continue

            avg_score = sum(source_scores) / len(source_scores)
            avg_conf = sum(source_confs) / len(source_confs) if source_confs else 0.5

            weighted_sum += avg_score * weight
            total_weight += weight
            all_confidences.append(avg_conf)

        if total_weight > 0:
            normalised_score = weighted_sum / total_weight
        else:
            normalised_score = 0.0

        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

        return normalised_score, total_weight, avg_confidence

    # ------------------------------------------------------------------
    # Momentum (is sentiment improving or declining over 4 hours?)
    # ------------------------------------------------------------------
    def _compute_momentum(self, ticker: str, current_score: float) -> float:
        """Compute score delta over the momentum window."""
        history = self._load_history(ticker)
        if not history:
            return 0.0

        cutoff = datetime.utcnow() - timedelta(hours=self.MOMENTUM_WINDOW_HOURS)
        older_scores = [
            h["score"] for h in history
            if datetime.fromisoformat(h["timestamp"]) <= cutoff
        ]

        if not older_scores:
            # Not enough history yet; use earliest available
            oldest = history[0]["score"] if history else current_score
            return current_score - oldest

        avg_old = sum(older_scores) / len(older_scores)
        return current_score - avg_old

    def _store_score(self, ticker: str, score: float) -> None:
        """Persist a timestamped score for momentum tracking."""
        entry = {"score": score, "timestamp": datetime.utcnow().isoformat()}
        cache_key = f"arbion_sentiment_history_{ticker}"

        # Try Redis first
        if self._redis is not None:
            try:
                history = self._redis.get(cache_key) or []
                history.append(entry)
                # Keep only last 24 hours
                cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
                history = [h for h in history if h["timestamp"] >= cutoff]
                self._redis.set(cache_key, history, timeout=86400)
                return
            except Exception as e:
                logger.debug(f"Redis history write error: {e}")

        # Fallback to in-memory
        if ticker not in self._history:
            self._history[ticker] = []
        self._history[ticker].append(entry)
        # Prune old entries
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        self._history[ticker] = [h for h in self._history[ticker] if h["timestamp"] >= cutoff]

    def _load_history(self, ticker: str) -> List[Dict]:
        """Load historical scores for a ticker."""
        cache_key = f"arbion_sentiment_history_{ticker}"

        if self._redis is not None:
            try:
                history = self._redis.get(cache_key)
                if history:
                    return history
            except Exception as e:
                logger.debug(f"Redis history read error: {e}")

        return self._history.get(ticker, [])
