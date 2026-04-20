from __future__ import annotations

import logging
import os

from .base_engine import AIProvider, BaseNeuralEngine
from .claude_engine import ClaudeNeuralEngine
from .openai_engine import OpenAINeuralEngine

logger = logging.getLogger(__name__)


class NeuralEngineFactory:
    """Factory that creates the appropriate AI engine based on configuration."""

    _engines = {
        AIProvider.CLAUDE: ClaudeNeuralEngine,
        AIProvider.OPENAI: OpenAINeuralEngine,
    }

    @classmethod
    def create(cls, provider: str = None, model: str = None) -> BaseNeuralEngine:
        if provider is None:
            provider = os.environ.get("AI_PROVIDER", "auto")

        if provider == "consensus":
            from .consensus_engine import ConsensusNeuralEngine

            return ConsensusNeuralEngine(consensus_mode=os.environ.get("NEURAL_CONSENSUS_MODE", "unanimous"))

        if provider == "auto":
            if os.environ.get("ANTHROPIC_API_KEY"):
                provider = "claude"
            elif os.environ.get("OPENAI_API_KEY"):
                provider = "openai"
            else:
                raise ValueError("No AI API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.")

        provider_enum = AIProvider(provider.lower())
        engine_class = cls._engines.get(provider_enum)
        if engine_class is None:
            raise ValueError(f"Unknown AI provider: {provider}")

        logger.info("Neural engine initialized: %s (model: %s)", provider_enum.value, model or "default")
        return engine_class(model=model)

    @classmethod
    def register_provider(cls, provider: AIProvider, engine_class):
        cls._engines[provider] = engine_class
