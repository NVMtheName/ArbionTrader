from __future__ import annotations

import os

from flask import Blueprint, jsonify, request

from app import db
from models import NeuralAnalysisLog, NeuralProviderStats
from .common import usage_snapshot
from .engine_factory import NeuralEngineFactory

neural_bp = Blueprint("neural", __name__)

_runtime_config = {
    "provider": os.environ.get("AI_PROVIDER", "auto"),
    "model": None,
    "consensus_mode": os.environ.get("NEURAL_CONSENSUS_MODE", "unanimous"),
}


def _masked(value: str) -> str:
    if not value:
        return "missing"
    if len(value) < 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


@neural_bp.route("/api/neural/status", methods=["GET"])
def neural_status():
    return jsonify(
        {
            "provider": _runtime_config["provider"],
            "model": _runtime_config["model"],
            "consensus_mode": _runtime_config["consensus_mode"],
            "api_keys": {
                "anthropic": _masked(os.environ.get("ANTHROPIC_API_KEY", "")),
                "openai": _masked(os.environ.get("OPENAI_API_KEY", "")),
            },
        }
    )


@neural_bp.route("/api/neural/analyze/<ticker>", methods=["GET"])
def neural_analyze(ticker: str):
    provider = request.args.get("provider") or _runtime_config["provider"]
    model = request.args.get("model") or _runtime_config["model"]
    engine = NeuralEngineFactory.create(provider=provider, model=model)
    analysis = engine.analyze_trade(
        ticker=ticker,
        market_data={"asset_class": request.args.get("asset_class", "EQUITY"), "current_price": request.args.get("price", "unknown")},
        signals={"note": "manual neural test endpoint"},
        sentiment=None,
        regime=request.args.get("regime", "UNKNOWN"),
    )

    log = NeuralAnalysisLog(
        provider=analysis.provider,
        model=analysis.model,
        ticker=ticker,
        direction=analysis.direction,
        confidence=analysis.confidence,
        reasoning=analysis.reasoning,
        tokens_used=analysis.tokens_used,
        latency_ms=analysis.latency_ms,
    )
    db.session.add(log)

    stats = NeuralProviderStats.query.filter_by(provider=analysis.provider).first()
    if not stats:
        stats = NeuralProviderStats(provider=analysis.provider)
        db.session.add(stats)
    stats.register(confidence=analysis.confidence, disagreement=(analysis.provider == "consensus" and analysis.direction == "NEUTRAL"))
    db.session.commit()

    return jsonify({"analysis": analysis.to_dict(), "log_id": log.id})


@neural_bp.route("/api/neural/config", methods=["POST"])
def neural_config():
    payload = request.get_json(silent=True) or {}
    _runtime_config["provider"] = payload.get("provider", _runtime_config["provider"])
    _runtime_config["model"] = payload.get("model", _runtime_config["model"])
    _runtime_config["consensus_mode"] = payload.get("consensus_mode", _runtime_config["consensus_mode"])

    if _runtime_config["provider"]:
        os.environ["AI_PROVIDER"] = _runtime_config["provider"]
    if _runtime_config["model"]:
        os.environ["CLAUDE_MODEL"] = _runtime_config["model"]
        os.environ["OPENAI_MODEL"] = _runtime_config["model"]
    os.environ["NEURAL_CONSENSUS_MODE"] = _runtime_config["consensus_mode"]

    return jsonify({"success": True, "config": _runtime_config})


@neural_bp.route("/api/neural/usage", methods=["GET"])
def neural_usage():
    return jsonify({"usage": usage_snapshot()})


@neural_bp.route("/api/neural/accuracy", methods=["GET"])
def neural_accuracy():
    stats = NeuralProviderStats.query.order_by(NeuralProviderStats.provider.asc()).all()
    return jsonify({"providers": [s.to_dict() for s in stats]})


@neural_bp.route("/api/neural/history", methods=["GET"])
def neural_history():
    rows = NeuralAnalysisLog.query.order_by(NeuralAnalysisLog.created_at.desc()).limit(50).all()
    return jsonify({"history": [row.to_dict() for row in rows]})
