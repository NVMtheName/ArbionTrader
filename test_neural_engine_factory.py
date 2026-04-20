"""Unit tests for ``neural.engine_factory.NeuralEngineFactory``.

These tests stub out the concrete engine classes so they don't require real API
keys or network calls. They lock in the factory's resolution order:

    explicit arg > AI_PROVIDER env > auto-detect from API keys > fail
"""

from __future__ import annotations

import importlib
import os
import sys
from typing import Any, Dict, List, Optional

import pytest

# Ensure the engine SDKs (anthropic / openai) get importable stubs even in CI
# environments where they may not be installed yet. Real installs win.
def _stub_module(name: str, attrs: Dict[str, Any]) -> None:
    if name in sys.modules:
        return
    mod = type(sys)(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod


class _StubAnthropicClient:
    def __init__(self, *args, **kwargs):
        pass

    class messages:  # noqa: N801 - mirror SDK shape
        @staticmethod
        def create(*args, **kwargs):
            raise RuntimeError("stub anthropic should never be called in factory tests")


class _StubOpenAIClient:
    def __init__(self, *args, **kwargs):
        pass

    class chat:
        class completions:
            @staticmethod
            def create(*args, **kwargs):
                raise RuntimeError("stub openai should never be called in factory tests")


_stub_module("anthropic", {"Anthropic": _StubAnthropicClient})
_stub_module("openai", {"OpenAI": _StubOpenAIClient})

# Now safe to import the factory.
from neural.base_engine import AIProvider, BaseNeuralEngine, NeuralAnalysis  # noqa: E402
from neural.engine_factory import NeuralEngineFactory  # noqa: E402


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #

class _FakeEngine(BaseNeuralEngine):
    """Minimal engine used to verify factory wiring without any network I/O."""

    def __init__(self, model: Optional[str] = None, provider: AIProvider = AIProvider.CLAUDE):
        self.provider = provider
        self.model = model or f"fake-{provider.value}"

    def analyze_trade(self, *args, **kwargs) -> NeuralAnalysis:  # pragma: no cover
        raise NotImplementedError

    def analyze_portfolio(self, *args, **kwargs) -> Dict:  # pragma: no cover
        raise NotImplementedError

    def explain_trade(self, *args, **kwargs) -> str:  # pragma: no cover
        raise NotImplementedError

    def generate_market_brief(self, *args, **kwargs) -> str:  # pragma: no cover
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def _isolate_factory_state():
    """Snapshot and restore factory class state around every test."""
    saved_engines = dict(NeuralEngineFactory._engines)
    saved_default = NeuralEngineFactory._default_instance
    saved_config = dict(NeuralEngineFactory._default_config)

    # Re-register engines as fakes that won't talk to any provider.
    NeuralEngineFactory._engines[AIProvider.CLAUDE] = lambda model=None: _FakeEngine(model, AIProvider.CLAUDE)
    NeuralEngineFactory._engines[AIProvider.OPENAI] = lambda model=None: _FakeEngine(model, AIProvider.OPENAI)
    NeuralEngineFactory._default_instance = None
    NeuralEngineFactory._default_config = {"provider": None, "model": None}

    yield

    NeuralEngineFactory._engines = saved_engines
    NeuralEngineFactory._default_instance = saved_default
    NeuralEngineFactory._default_config = saved_config


@pytest.fixture
def clean_env(monkeypatch):
    """Remove any provider-affecting env vars so each test starts from zero."""
    for var in ("AI_PROVIDER", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


# --------------------------------------------------------------------------- #
# Resolution order
# --------------------------------------------------------------------------- #

def test_create_explicit_provider_wins_over_env(clean_env):
    clean_env.setenv("AI_PROVIDER", "openai")
    engine = NeuralEngineFactory.create(provider="claude")
    assert engine.provider == AIProvider.CLAUDE


def test_create_uses_env_var_when_no_explicit_provider(clean_env):
    clean_env.setenv("AI_PROVIDER", "openai")
    engine = NeuralEngineFactory.create()
    assert engine.provider == AIProvider.OPENAI


def test_create_auto_prefers_claude_when_both_keys_present(clean_env):
    clean_env.setenv("AI_PROVIDER", "auto")
    clean_env.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    clean_env.setenv("OPENAI_API_KEY", "sk-oai-test")
    engine = NeuralEngineFactory.create()
    assert engine.provider == AIProvider.CLAUDE


def test_create_auto_falls_back_to_openai_when_only_openai_key(clean_env):
    clean_env.setenv("AI_PROVIDER", "auto")
    clean_env.setenv("OPENAI_API_KEY", "sk-oai-test")
    engine = NeuralEngineFactory.create()
    assert engine.provider == AIProvider.OPENAI


def test_create_auto_raises_when_no_keys_present(clean_env):
    clean_env.setenv("AI_PROVIDER", "auto")
    with pytest.raises(ValueError, match="No AI API key"):
        NeuralEngineFactory.create()


def test_create_default_env_is_auto_when_unset(clean_env):
    clean_env.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    engine = NeuralEngineFactory.create()
    assert engine.provider == AIProvider.CLAUDE


def test_create_unknown_provider_raises(clean_env):
    with pytest.raises(ValueError, match="Unknown AI provider"):
        NeuralEngineFactory.create(provider="gemini")


def test_create_passes_model_to_engine(clean_env):
    engine = NeuralEngineFactory.create(provider="claude", model="my-tuned-model")
    assert engine.model == "my-tuned-model"


# --------------------------------------------------------------------------- #
# Default instance + reconfiguration
# --------------------------------------------------------------------------- #

def test_get_default_caches_single_instance(clean_env):
    clean_env.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    a = NeuralEngineFactory.get_default()
    b = NeuralEngineFactory.get_default()
    assert a is b


def test_reconfigure_default_swaps_provider(clean_env):
    clean_env.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    clean_env.setenv("OPENAI_API_KEY", "sk-oai-test")
    first = NeuralEngineFactory.get_default()
    assert first.provider == AIProvider.CLAUDE

    new_engine = NeuralEngineFactory.reconfigure_default(provider="openai")
    assert new_engine.provider == AIProvider.OPENAI
    assert NeuralEngineFactory.get_default() is new_engine


def test_reconfigure_default_records_configured_provider(clean_env):
    clean_env.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    NeuralEngineFactory.reconfigure_default(provider="claude", model="claude-opus-4-7")
    config = NeuralEngineFactory.current_config()
    assert config["configured_provider"] == "claude"
    assert config["configured_model"] == "claude-opus-4-7"
    assert config["provider"] == "claude"


def test_current_config_reports_none_when_no_default_yet(clean_env):
    config = NeuralEngineFactory.current_config()
    assert config["provider"] is None
    assert config["model"] is None


# --------------------------------------------------------------------------- #
# Extension point
# --------------------------------------------------------------------------- #

def test_register_provider_adds_new_engine_class(clean_env):
    calls: List[Optional[str]] = []

    class _GeminiEngine(_FakeEngine):
        def __init__(self, model=None):
            calls.append(model)
            super().__init__(model=model, provider=AIProvider.CLAUDE)

    # Reuse CLAUDE enum as a stand-in to avoid mutating AIProvider for the test.
    NeuralEngineFactory.register_provider(AIProvider.CLAUDE, _GeminiEngine)
    engine = NeuralEngineFactory.create(provider="claude", model="gemini-2.5")
    assert isinstance(engine, _GeminiEngine)
    assert calls == ["gemini-2.5"]
