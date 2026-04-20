"""Swappable AI Neural Engine for Arbion.

Usage anywhere in the codebase:

    from neural import NeuralEngineFactory

    engine = NeuralEngineFactory.create()              # auto-detect provider
    engine = NeuralEngineFactory.create(provider="claude")
    engine = NeuralEngineFactory.create(provider="openai", model="gpt-4o")
    engine = NeuralEngineFactory.create(provider="consensus")  # run both

    analysis = engine.analyze_trade(
        ticker="BTCUSD",
        market_data={...},
        signals={...},
    )
    print(analysis.direction, analysis.confidence, analysis.reasoning)

The HTTP blueprint is exposed as ``neural.routes.neural_bp`` and is mounted at
``/api/neural`` in ``app.py``.
"""

from .base_engine import AIProvider, BaseNeuralEngine, NeuralAnalysis
from .engine_factory import NeuralEngineFactory

__all__ = [
    "AIProvider",
    "BaseNeuralEngine",
    "NeuralAnalysis",
    "NeuralEngineFactory",
]
