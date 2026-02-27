"""
Confluence Filter for Arbion Trading Platform.

Consumes TimeframeSignal objects from the MultiTimeframeAnalyzer and computes
an overall confluence score (0-100).  When the score falls below a configurable
threshold the trade is rejected.

Scoring rules
-------------
* All 3 timeframes agree on direction  → 90-100 (strong signal)
* 2 of 3 agree                         → 60-75  (moderate signal)
* No agreement                          → 0-40   (no trade)
"""

import logging
import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Any

from analysis.multi_timeframe import TimeframeSignal

logger = logging.getLogger(__name__)

# Default minimum confluence score required to allow a trade
DEFAULT_CONFLUENCE_THRESHOLD = 65


@dataclass
class ConfluenceResult:
    """Outcome of the confluence filter evaluation."""
    score: int                  # 0-100
    direction: str              # "bullish", "bearish", "neutral"
    should_trade: bool
    reasoning: str
    timeframe_signals: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConfluenceFilter:
    """Evaluates multi-timeframe agreement before allowing trade execution."""

    def __init__(self, threshold: int = None):
        # Allow env-var override → constructor arg → default
        env_val = os.environ.get("CONFLUENCE_THRESHOLD")
        if threshold is not None:
            self.threshold = threshold
        elif env_val is not None:
            self.threshold = int(env_val)
        else:
            self.threshold = DEFAULT_CONFLUENCE_THRESHOLD

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, signals: List[TimeframeSignal]) -> ConfluenceResult:
        """Compute confluence score from a list of TimeframeSignal objects.

        Parameters
        ----------
        signals : list[TimeframeSignal]
            Exactly 3 signals (5m, 1h, 1d) — as returned by
            ``MultiTimeframeAnalyzer.analyze()``.

        Returns
        -------
        ConfluenceResult
        """
        if not signals:
            return ConfluenceResult(
                score=0, direction="neutral", should_trade=False,
                reasoning="No timeframe signals provided.",
                timeframe_signals=[],
            )

        trends = [s.trend for s in signals]
        strengths = [s.strength for s in signals]

        bullish_count = trends.count("bullish")
        bearish_count = trends.count("bearish")

        # --- Determine majority direction ---
        if bullish_count > bearish_count:
            direction = "bullish"
            agree_count = bullish_count
        elif bearish_count > bullish_count:
            direction = "bearish"
            agree_count = bearish_count
        else:
            direction = "neutral"
            agree_count = 0

        # --- Base score from agreement level ---
        if agree_count == 3:
            # All agree → 90-100 range scaled by average strength
            avg_strength = sum(strengths) / len(strengths)
            base_score = 90 + int((avg_strength / 100) * 10)  # 90-100
        elif agree_count == 2:
            # 2 of 3 agree → 60-75 range
            # Identify the two agreeing signals and average their strength
            agreeing_strengths = [
                s.strength for s in signals if s.trend == direction
            ]
            avg_agree = sum(agreeing_strengths) / len(agreeing_strengths) if agreeing_strengths else 50
            base_score = 60 + int((avg_agree / 100) * 15)  # 60-75
        else:
            # No agreement → 0-40 range
            avg_strength = sum(strengths) / len(strengths)
            base_score = int((avg_strength / 100) * 40)  # 0-40

        score = max(0, min(100, base_score))

        # --- Build reasoning string ---
        reasoning_parts = []
        for s in signals:
            reasoning_parts.append(
                f"{s.timeframe}: {s.trend} (strength {s.strength})"
            )
        agreement_desc = (
            "all 3 timeframes agree" if agree_count == 3
            else f"{agree_count} of 3 timeframes agree" if agree_count == 2
            else "no timeframe agreement"
        )
        reasoning_parts.append(
            f"Confluence: {agreement_desc} → direction={direction}, "
            f"score={score}/{self.threshold} threshold"
        )

        should_trade = score >= self.threshold and direction != "neutral"

        if not should_trade:
            if score < self.threshold:
                reasoning_parts.append(
                    f"Trade REJECTED: score {score} below threshold {self.threshold}."
                )
            elif direction == "neutral":
                reasoning_parts.append(
                    "Trade REJECTED: no clear directional bias."
                )
        else:
            reasoning_parts.append(
                f"Trade APPROVED: score {score} meets threshold {self.threshold}."
            )

        return ConfluenceResult(
            score=score,
            direction=direction,
            should_trade=should_trade,
            reasoning=" | ".join(reasoning_parts),
            timeframe_signals=[s.to_dict() for s in signals],
        )
