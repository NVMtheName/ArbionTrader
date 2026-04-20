"""Factory for selecting an AI provider at runtime.

Resolution order:
1. Explicit ``provider`` argument
2. ``AI_PROVIDER`` environment variable
3. Auto-detect based on available API keys (prefer Claude)
4. Fail loudly if no key is set
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Dict, Optional, Type

from .base_engine import AIProvider, BaseNeuralEngine
from .claude_engine import ClaudeNeuralEngine
from .openai_engine import OpenAINeuralEngine

logger = logging.getLogger(__name__)


class NeuralEngineFactory:
    """Creates the configured AI engine on demand."""

    _engines: Dict[AIProvider, Type[BaseNeuralEngine]] = {
        AIProvider.CLAUDE: ClaudeNeuralEngine,
        AIProvider.OPENAI: OpenAINeuralEngine,
    }

    _default_instance: Optional[BaseNeuralEngine] = None
    _default_config: Dict[str, Optional[str]] = {"provider": None, "model": None}
    _lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    @classmethod
    def create(
        cls,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> BaseNeuralEngine:
        if provider is None:
            provider = os.environ.get("AI_PROVIDER", "auto")

        provider_value = (provider or "auto").lower()

        if provider_value == "consensus":
            # Imported lazily to avoid a circular import at module load time.
            from .consensus_engine import ConsensusNeuralEngine
            logger.info("Neural engine initialized: consensus (sub-providers auto-detected)")
            return ConsensusNeuralEngine()

        if provider_value == "auto":
            if os.environ.get("ANTHROPIC_API_KEY"):
                provider_value = "claude"
            elif os.environ.get("OPENAI_API_KEY"):
                provider_value = "openai"
            else:
                raise ValueError(
                    "No AI API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY, "
                    "or configure AI_PROVIDER explicitly."
                )

        try:
            provider_enum = AIProvider(provider_value)
        except ValueError as e:
            raise ValueError(f"Unknown AI provider: {provider}") from e

        engine_class = cls._engines.get(provider_enum)
        if engine_class is None:
            raise ValueError(f"No engine registered for provider: {provider_enum.value}")

        logger.info("Neural engine initialized: %s (model: %s)", provider_enum.value, model or "default")
        return engine_class(model=model)

    @classmethod
    def register_provider(cls, provider: AIProvider, engine_class: Type[BaseNeuralEngine]) -> None:
        """Register a custom AI provider (for Gemini, Llama, etc.)."""
        cls._engines[provider] = engine_class

    # ------------------------------------------------------------------ #
    # Default instance (shared across the app)
    # ------------------------------------------------------------------ #

    @classmethod
    def get_default(cls) -> BaseNeuralEngine:
        """Return the process-wide default engine, creating it on first use."""
        if cls._default_instance is not None:
            return cls._default_instance
        with cls._lock:
            if cls._default_instance is None:
                cls._default_instance = cls.create(
                    provider=cls._default_config["provider"],
                    model=cls._default_config["model"],
                )
        return cls._default_instance

    @classmethod
    def reconfigure_default(
        cls,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> BaseNeuralEngine:
        """Swap the default engine at runtime (e.g. from an admin endpoint)."""
        with cls._lock:
            cls._default_config = {"provider": provider, "model": model}
            cls._default_instance = cls.create(provider=provider, model=model)
        return cls._default_instance

    @classmethod
    def current_config(cls) -> Dict[str, Optional[str]]:
        engine = cls._default_instance
        return {
            "provider": getattr(engine.provider, "value", None) if engine else None,
            "model": getattr(engine, "model", None) if engine else None,
            "configured_provider": cls._default_config.get("provider"),
            "configured_model": cls._default_config.get("model"),
        }
