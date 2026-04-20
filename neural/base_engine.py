"""Base classes and shared types for the swappable Neural Engine.

All concrete AI providers (Claude, OpenAI, Consensus, ...) implement
``BaseNeuralEngine`` so the trading logic can call a single unified interface
and have the underlying provider swapped at runtime via configuration.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from enum import Enum


class AIProvider(Enum):
    CLAUDE = "claude"
    OPENAI = "openai"
    CONSENSUS = "consensus"


@dataclass
class NeuralAnalysis:
    """Unified response from any AI provider."""

    direction: str                              # "LONG", "SHORT", "NEUTRAL"
    confidence: float                           # 0.0 to 1.0
    reasoning: str                              # Natural-language rationale
    key_factors: List[str]                      # Top factors driving the call
    risk_assessment: str                        # "LOW" | "MEDIUM" | "HIGH" | "EXTREME"
    suggested_position_size: float              # 0.0 to 1.0 (fraction of max allowed)
    suggested_sl_pct: Optional[float]           # Suggested stop-loss percentage
    suggested_tp_pct: Optional[float]           # Suggested take-profit percentage
    market_context: str                         # Brief market-regime context
    contrarian_view: str                        # What could invalidate the trade
    raw_response: str                           # Full raw AI response for debugging
    provider: str                               # "claude" | "openai" | "consensus"
    model: str                                  # Model identifier
    tokens_used: int                            # Total tokens consumed
    latency_ms: float                           # Response time in milliseconds
    cost_usd: float = 0.0                       # Estimated cost in USD
    cached: bool = False                        # Whether returned from cache
    extra: Dict[str, Any] = field(default_factory=dict)  # Provider-specific extras

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BaseNeuralEngine(ABC):
    """Abstract interface that every AI provider must implement."""

    provider: AIProvider
    model: str

    @abstractmethod
    def analyze_trade(
        self,
        ticker: str,
        market_data: Dict,
        signals: Dict,
        sentiment: Optional[Dict] = None,
        regime: Optional[str] = None,
    ) -> NeuralAnalysis:
        """Return a directional call with confidence, sizing and risk guidance."""

    @abstractmethod
    def analyze_portfolio(
        self,
        positions: List[Dict],
        market_overview: Dict,
    ) -> Dict:
        """Review all open positions and suggest adjustments."""

    @abstractmethod
    def explain_trade(self, trade_record: Dict) -> str:
        """Natural-language post-mortem of a completed trade."""

    @abstractmethod
    def generate_market_brief(
        self,
        watchlist: List[str],
        market_data: Dict,
    ) -> str:
        """Morning briefing covering watchlist tickers and key levels."""

    # Optional extension point that some engines may implement.
    def optimize_strategy(
        self,
        backtest_results: Dict,
        current_params: Dict,
    ) -> Dict:
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement strategy optimization"
        )
