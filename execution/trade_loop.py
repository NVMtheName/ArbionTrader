"""Trade-loop neural integration helper.

This module demonstrates where to call the provider-agnostic neural engine in an
execution loop after signal/confluence checks pass.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from neural import NeuralEngineFactory

logger = logging.getLogger(__name__)


def apply_neural_veto(
    *,
    config: Dict[str, Any],
    ticker: str,
    latest_data: Dict[str, Any],
    signal_payload: Dict[str, Any],
    sentiment_payload: Optional[Dict[str, Any]],
    regime: Optional[str],
    position_size: float,
) -> Dict[str, Any]:
    """Run neural confirmation and return decision payload for the trade loop."""
    if not config.get("NEURAL_ENGINE_ENABLED", False):
        return {"allowed": True, "position_size": position_size, "neural_analysis": None}

    engine = NeuralEngineFactory.create(provider=config.get("AI_PROVIDER"), model=config.get("AI_MODEL"))
    analysis = engine.analyze_trade(
        ticker=ticker,
        market_data=latest_data,
        signals=signal_payload,
        sentiment=sentiment_payload,
        regime=regime,
    )

    min_conf = float(config.get("NEURAL_CONFIDENCE_THRESHOLD", 0.4))
    if analysis.direction == "NEUTRAL" or analysis.confidence < min_conf:
        logger.info("Neural engine vetoed %s: %s", ticker, analysis.reasoning)
        return {
            "allowed": False,
            "position_size": 0.0,
            "reason": f"Neural engine vetoed: {analysis.reasoning}",
            "neural_analysis": analysis.to_dict(),
        }

    return {
        "allowed": True,
        "position_size": position_size * analysis.suggested_position_size,
        "neural_analysis": analysis.to_dict(),
    }
