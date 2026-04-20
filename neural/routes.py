"""Flask blueprint exposing the swappable Neural Engine over HTTP."""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from typing import Any, Deque, Dict

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from .base_engine import NeuralAnalysis
from .consensus_engine import accuracy_ledger, record_outcome
from .engine_factory import NeuralEngineFactory
from ._common import usage_tracker

logger = logging.getLogger(__name__)

neural_bp = Blueprint("neural", __name__, url_prefix="/api/neural")

# Providers that may be recorded against the accuracy ledger. Bounding this
# prevents unbounded ledger growth from arbitrary user-supplied strings.
_KNOWN_PROVIDERS = frozenset({"claude", "openai", "consensus"})


# In-memory history of the most recent analyses (bounded)
_HISTORY_MAX = 50
_history: Deque[Dict[str, Any]] = deque(maxlen=_HISTORY_MAX)


def _require_admin():
    """Return a (response, status) tuple if the current user is not an admin."""
    if not getattr(current_user, "is_authenticated", False) or not current_user.is_admin():
        return jsonify({"error": "admin privileges required"}), 403
    return None


def _mask_key(env_var: str) -> str:
    value = os.environ.get(env_var)
    if not value:
        return "not-set"
    if len(value) < 12:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #

@neural_bp.route("/status", methods=["GET"])
@login_required
def status():
    config = NeuralEngineFactory.current_config()
    return jsonify({
        "active_provider": config["provider"],
        "active_model": config["model"],
        "configured_provider": config["configured_provider"] or os.environ.get("AI_PROVIDER", "auto"),
        "configured_model": config["configured_model"],
        "api_keys": {
            "anthropic": _mask_key("ANTHROPIC_API_KEY"),
            "openai": _mask_key("OPENAI_API_KEY"),
        },
        "defaults": {
            "claude_model": os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
            "openai_model": os.environ.get("OPENAI_MODEL", "gpt-4o"),
            "cache_ttl_seconds": int(os.environ.get("NEURAL_CACHE_TTL", "300")),
        },
        "neural_engine_enabled": os.environ.get("NEURAL_ENGINE_ENABLED", "false").lower() == "true",
    })


# --------------------------------------------------------------------------- #
# Ad-hoc analysis for testing
# --------------------------------------------------------------------------- #

@neural_bp.route("/analyze/<ticker>", methods=["GET", "POST"])
@login_required
def analyze(ticker: str):
    """Run a neural analysis on a single ticker. Accepts JSON payload in POST."""
    payload = request.get_json(silent=True) or {}
    market_data = payload.get("market_data", {})
    signals = payload.get("signals", {})
    sentiment = payload.get("sentiment")
    regime = payload.get("regime")

    try:
        engine = NeuralEngineFactory.get_default()
    except Exception as e:
        return jsonify({"error": f"Engine unavailable: {e}"}), 503

    start = time.time()
    try:
        analysis = engine.analyze_trade(
            ticker=ticker,
            market_data=market_data,
            signals=signals,
            sentiment=sentiment,
            regime=regime,
        )
    except Exception as e:
        logger.exception("Neural analyze failed for %s", ticker)
        return jsonify({"error": str(e)}), 500

    record = analysis.to_dict()
    record["ticker"] = ticker
    record["_request_ms"] = round((time.time() - start) * 1000.0, 1)
    _history.append({"ts": time.time(), "ticker": ticker, "analysis": record})
    return jsonify(record)


# --------------------------------------------------------------------------- #
# Runtime configuration
# --------------------------------------------------------------------------- #

@neural_bp.route("/config", methods=["POST"])
@login_required
def config():
    """Swap provider / model at runtime. Body: {provider, model, consensus_mode?}.

    Admin-only: this endpoint mutates a process-wide default that affects every
    user's trade analyses, so a non-admin caller must not be able to flip it.
    """
    denied = _require_admin()
    if denied is not None:
        return denied

    body = request.get_json(silent=True) or {}
    provider = body.get("provider")
    model = body.get("model")

    if provider not in (None, "claude", "openai", "consensus", "auto"):
        return jsonify({"error": f"Unknown provider: {provider}"}), 400

    try:
        engine = NeuralEngineFactory.reconfigure_default(provider=provider, model=model)
    except Exception as e:
        logger.exception("Neural reconfigure failed")
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "ok": True,
        "provider": engine.provider.value if hasattr(engine.provider, "value") else str(engine.provider),
        "model": engine.model,
    })


# --------------------------------------------------------------------------- #
# Usage, accuracy, history
# --------------------------------------------------------------------------- #

@neural_bp.route("/usage", methods=["GET"])
@login_required
def usage():
    return jsonify(usage_tracker.snapshot())


@neural_bp.route("/accuracy", methods=["GET"])
@login_required
def accuracy():
    return jsonify({"providers": accuracy_ledger.stats()})


@neural_bp.route("/accuracy/record", methods=["POST"])
@login_required
def accuracy_record():
    """Attribute a settled trade's outcome to the provider that suggested it."""
    body = request.get_json(silent=True) or {}
    provider = body.get("provider")
    outcome = body.get("outcome")
    pnl_pct = body.get("pnl_pct")
    analysis = body.get("analysis")
    if not provider or outcome not in ("WIN", "LOSS", "SCRATCH") or not analysis:
        return jsonify({"error": "provider, outcome in {WIN,LOSS,SCRATCH}, and analysis required"}), 400

    # Constrain provider to a known set so callers can't expand the in-memory
    # ledger keyspace arbitrarily.
    if provider not in _KNOWN_PROVIDERS:
        return jsonify({"error": f"provider must be one of {sorted(_KNOWN_PROVIDERS)}"}), 400

    try:
        na = NeuralAnalysis(**{k: v for k, v in analysis.items() if k in NeuralAnalysis.__dataclass_fields__})
    except Exception as e:
        return jsonify({"error": f"invalid analysis: {e}"}), 400

    # The supplied provider must agree with the analysis's recorded provider —
    # otherwise a caller could attribute outcomes to the wrong engine.
    if na.provider and na.provider != provider:
        return jsonify({"error": "provider does not match analysis.provider"}), 400

    record_outcome(provider, na, outcome, pnl_pct)
    return jsonify({"ok": True})


@neural_bp.route("/history", methods=["GET"])
@login_required
def history():
    return jsonify({"count": len(_history), "items": list(_history)})
