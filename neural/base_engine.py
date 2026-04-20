from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class AIProvider(Enum):
    CLAUDE = "claude"
    OPENAI = "openai"


@dataclass
class NeuralAnalysis:
    """Unified response from any AI provider."""

    direction: str
    confidence: float
    reasoning: str
    key_factors: List[str]
    risk_assessment: str
    suggested_position_size: float
    suggested_sl_pct: Optional[float]
    suggested_tp_pct: Optional[float]
    market_context: str
    contrarian_view: str
    raw_response: str
    provider: str
    model: str
    tokens_used: int
    latency_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BaseNeuralEngine(ABC):
    @abstractmethod
    def analyze_trade(
        self,
        ticker: str,
        market_data: Dict[str, Any],
        signals: Dict[str, Any],
        sentiment: Optional[Dict[str, Any]] = None,
        regime: Optional[str] = None,
    ) -> NeuralAnalysis:
        pass

    @abstractmethod
    def analyze_portfolio(self, positions: List[Dict[str, Any]], market_overview: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def explain_trade(self, trade_record: Dict[str, Any]) -> str:
        pass

    @abstractmethod
    def generate_market_brief(self, watchlist: List[str], market_data: Dict[str, Any]) -> str:
        pass
