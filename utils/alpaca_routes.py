"""Flask routes for Alpaca US API support.

Covers Alpaca API reference families from Authentication API through Broker API
using authenticated convenience endpoints plus a controlled generic proxy.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from flask import Blueprint, Response, jsonify, request
from flask_login import login_required

from utils.alpaca_api import AlpacaAPIClient

alpaca_bp = Blueprint("alpaca", __name__, url_prefix="/api/alpaca")

ALPACA_REFERENCE_URL = "https://docs.alpaca.markets/us/reference/api-references"

SUPPORTED_DOMAINS = {
    "auth": "Authentication API",
    "trading": "Trading API",
    "market_data": "Market Data API",
    "market-data": "Market Data API",
    "broker": "Broker API",
}

REFERENCE_COVERAGE = {
    "auth": ["issue tokens", "OAuth/client-credentials authentication"],
    "trading": [
        "account", "assets", "orders", "positions", "portfolio history",
        "watchlists", "calendar", "clock", "corporate actions", "options", "crypto"
    ],
    "market_data": [
        "stocks", "options", "crypto", "news", "bars", "quotes", "trades", "snapshots"
    ],
    "broker": [
        "accounts", "trading accounts", "account activities", "assets", "orders",
        "positions", "funding/transfers", "journals", "documents", "crypto wallets",
        "events/SSE", "options approval", "fixed income", "IPOs", "corporate actions"
    ],
}


def _truthy(value: Optional[str]) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on", "paper", "sandbox"}


def _client() -> AlpacaAPIClient:
    return AlpacaAPIClient(
        api_key=os.getenv("ALPACA_API_KEY_ID") or os.getenv("ALPACA_API_KEY") or os.getenv("APCA_API_KEY_ID"),
        secret_key=os.getenv("ALPACA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY") or os.getenv("APCA_API_SECRET_KEY"),
        paper=_truthy(os.getenv("ALPACA_PAPER") or os.getenv("ALPACA_SANDBOX") or os.getenv("ALPACA_ENV")),
    )


def _normalize_domain(domain: str) -> str:
    normalized = domain.strip().lower()
    if normalized == "market-data":
        normalized = "market_data"
    if normalized not in {"auth", "trading", "market_data", "broker"}:
        raise ValueError("Unsupported Alpaca API domain. Use auth, trading, market_data, or broker.")
    return normalized


def _clean_path(path: str) -> str:
    if not path:
        return "/"
    if "://" in path or path.startswith("//"):
        raise ValueError("Only relative Alpaca API paths are allowed.")
    cleaned = "/" + path.lstrip("/")
    if ".." in cleaned.split("/"):
        raise ValueError("Path traversal is not allowed.")
    return cleaned


def _payload() -> Optional[Dict[str, Any]]:
    if request.method not in {"POST", "PUT", "PATCH"}:
        return None
    return request.get_json(silent=True) or {}


def _send(result: Dict[str, Any]):
    status_code = int(result.get("status_code") or (200 if result.get("success") else 400))
    response = jsonify(result)
    response.status_code = status_code
    return response


@alpaca_bp.get("/status")
@login_required
def status():
    """Return Alpaca integration status, supported API families, and env vars."""
    return jsonify({
        "success": True,
        "docs": ALPACA_REFERENCE_URL,
        "paper_mode": _client().paper,
        "domains": SUPPORTED_DOMAINS,
        "coverage": REFERENCE_COVERAGE,
        "env_vars": {
            "trading_market_data": ["ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY"],
            "legacy_aliases": ["ALPACA_API_KEY", "ALPACA_SECRET_KEY", "APCA_API_KEY_ID", "APCA_API_SECRET_KEY"],
            "mode": ["ALPACA_ENV=sandbox", "ALPACA_PAPER=true", "ALPACA_SANDBOX=true"],
            "oauth": ["ALPACA_OAUTH_CLIENT_ID", "ALPACA_OAUTH_CLIENT_SECRET"],
        },
        "generic_proxy": "/api/alpaca/proxy/<domain>/<alpaca-path>",
    })


@alpaca_bp.post("/auth/token")
@login_required
def issue_token():
    """Issue Alpaca Authentication API tokens using OAuth client credentials."""
    try:
        body = request.get_json(silent=True) or {}
        client_id = body.get("client_id") or os.getenv("ALPACA_OAUTH_CLIENT_ID")
        client_secret = body.get("client_secret") or os.getenv("ALPACA_OAUTH_CLIENT_SECRET")
        if not client_id:
            return jsonify({"success": False, "error": "Missing client_id or ALPACA_OAUTH_CLIENT_ID"}), 400
        return _send(_client().issue_tokens(client_id=client_id, client_secret=client_secret))
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@alpaca_bp.route("/proxy/<domain>/<path:alpaca_path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@login_required
def proxy(domain: str, alpaca_path: str):
    """Call any documented Alpaca REST endpoint in a supported API family.

    Examples:
      GET  /api/alpaca/proxy/trading/v2/account
      POST /api/alpaca/proxy/trading/v2/orders
      GET  /api/alpaca/proxy/market_data/v2/stocks/AAPL/bars
      GET  /api/alpaca/proxy/broker/v1/accounts
    """
    try:
        result = _client().request(
            domain=_normalize_domain(domain),
            method=request.method,
            path=_clean_path(alpaca_path),
            params=request.args.to_dict(flat=True),
            json_data=_payload(),
        )
        return _send(result)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@alpaca_bp.get("/trading/account")
@login_required
def trading_account():
    return _send(_client().request("trading", "GET", "/v2/account", params=request.args.to_dict(flat=True)))


@alpaca_bp.get("/trading/assets")
@login_required
def trading_assets():
    return _send(_client().request("trading", "GET", "/v2/assets", params=request.args.to_dict(flat=True)))


@alpaca_bp.route("/trading/orders", methods=["GET", "POST"])
@login_required
def trading_orders():
    return _send(_client().request("trading", request.method, "/v2/orders", params=request.args.to_dict(flat=True), json_data=_payload()))


@alpaca_bp.get("/trading/positions")
@login_required
def trading_positions():
    return _send(_client().request("trading", "GET", "/v2/positions", params=request.args.to_dict(flat=True)))


@alpaca_bp.route("/broker/accounts", methods=["GET", "POST"])
@login_required
def broker_accounts():
    return _send(_client().request("broker", request.method, "/v1/accounts", params=request.args.to_dict(flat=True), json_data=_payload()))


@alpaca_bp.get("/market-data/stocks/<symbol>/bars")
@login_required
def stock_bars(symbol: str):
    return _send(_client().request("market_data", "GET", f"/v2/stocks/{symbol.upper()}/bars", params=request.args.to_dict(flat=True)))
