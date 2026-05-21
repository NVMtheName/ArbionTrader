"""Alpaca US API client covering Authentication API through Broker API.

This client is intentionally generic: Alpaca's reference contains many REST
resources, and Arbion can call any documented endpoint by domain + relative path
without waiting for a new wrapper function each time Alpaca adds an endpoint.
"""

from __future__ import annotations

import base64
import os
from typing import Any, Dict, Mapping, Optional

import requests


class AlpacaAPIClient:
    """Thin Alpaca client with generic request support for all documented US endpoints."""

    TRADING_BASE = "https://api.alpaca.markets"
    PAPER_TRADING_BASE = "https://paper-api.alpaca.markets"
    DATA_BASE = "https://data.alpaca.markets"
    BROKER_BASE = "https://broker-api.alpaca.markets"
    SANDBOX_BROKER_BASE = "https://broker-api.sandbox.alpaca.markets"
    AUTH_BASE = "https://authx.alpaca.markets/v1"
    SANDBOX_AUTH_BASE = "https://authx.sandbox.alpaca.markets/v1"

    DOMAIN_ALIASES = {
        "authentication": "auth",
        "oauth": "auth",
        "data": "market_data",
        "market-data": "market_data",
        "marketdata": "market_data",
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        broker_key: Optional[str] = None,
        broker_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        paper: bool = False,
    ):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY_ID") or os.getenv("ALPACA_API_KEY") or os.getenv("APCA_API_KEY_ID")
        self.secret_key = secret_key or os.getenv("ALPACA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY") or os.getenv("APCA_API_SECRET_KEY")
        self.broker_key = broker_key or os.getenv("ALPACA_BROKER_KEY") or self.api_key
        self.broker_secret = broker_secret or os.getenv("ALPACA_BROKER_SECRET") or self.secret_key
        self.access_token = access_token or os.getenv("ALPACA_ACCESS_TOKEN")
        self.paper = paper

    @property
    def trading_base(self) -> str:
        return os.getenv("ALPACA_TRADING_BASE_URL") or (self.PAPER_TRADING_BASE if self.paper else self.TRADING_BASE)

    @property
    def data_base(self) -> str:
        return os.getenv("ALPACA_MARKET_DATA_BASE_URL") or self.DATA_BASE

    @property
    def broker_base(self) -> str:
        return os.getenv("ALPACA_BROKER_BASE_URL") or (self.SANDBOX_BROKER_BASE if self.paper else self.BROKER_BASE)

    @property
    def auth_base(self) -> str:
        return os.getenv("ALPACA_AUTH_BASE_URL") or (self.SANDBOX_AUTH_BASE if self.paper else self.AUTH_BASE)

    def _normalize_domain(self, domain: str) -> str:
        normalized = self.DOMAIN_ALIASES.get(domain.strip().lower(), domain.strip().lower())
        if normalized not in {"trading", "market_data", "broker", "auth"}:
            raise ValueError("domain must be one of: trading, market_data, broker, auth")
        return normalized

    def _base_url(self, domain: str) -> str:
        domain = self._normalize_domain(domain)
        base_map = {
            "trading": self.trading_base,
            "market_data": self.data_base,
            "broker": self.broker_base,
            "auth": self.auth_base,
        }
        return base_map[domain].rstrip("/")

    def _basic_auth(self, key: str, secret: str) -> str:
        token = base64.b64encode(f"{key}:{secret}".encode("utf-8")).decode("ascii")
        return f"Basic {token}"

    def _headers(self, domain: str, content_type: str = "application/json") -> Dict[str, str]:
        domain = self._normalize_domain(domain)
        headers = {
            "Accept": "application/json",
            "Content-Type": content_type,
            "User-Agent": "ArbionTrader-Alpaca/1.0",
        }

        if domain == "auth":
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"
            return headers

        if domain == "broker":
            if not self.broker_key or not self.broker_secret:
                raise ValueError("Alpaca Broker API requires ALPACA_BROKER_KEY and ALPACA_BROKER_SECRET")
            headers["Authorization"] = self._basic_auth(self.broker_key, self.broker_secret)
            return headers

        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
            return headers

        if not self.api_key or not self.secret_key:
            raise ValueError("Alpaca API key and secret are required")

        headers["APCA-API-KEY-ID"] = self.api_key
        headers["APCA-API-SECRET-KEY"] = self.secret_key
        return headers

    def _clean_path(self, path: str) -> str:
        if not path:
            return "/"
        if "://" in path or path.startswith("//"):
            raise ValueError("Only relative Alpaca API paths are allowed")
        cleaned = path if path.startswith("/") else f"/{path}"
        if ".." in cleaned.split("/"):
            raise ValueError("Path traversal is not allowed")
        return cleaned

    def request(
        self,
        domain: str,
        method: str,
        path: str,
        params: Optional[Mapping[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Mapping[str, Any]] = None,
        content_type: str = "application/json",
    ) -> Dict[str, Any]:
        domain = self._normalize_domain(domain)
        method = method.upper()
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            raise ValueError("Unsupported HTTP method")

        url = f"{self._base_url(domain)}{self._clean_path(path)}"
        response = requests.request(
            method,
            url,
            headers=self._headers(domain, content_type=content_type),
            params=dict(params or {}),
            json=json_data if content_type == "application/json" else None,
            data=data if content_type != "application/json" else None,
            timeout=30,
        )

        content = response.headers.get("content-type", "")
        try:
            payload: Any = response.json() if "application/json" in content else response.text
        except ValueError:
            payload = response.text

        return {
            "success": 200 <= response.status_code < 300,
            "status_code": response.status_code,
            "url": url,
            "data": payload if response.status_code < 400 else None,
            "error": payload if response.status_code >= 400 else None,
        }

    def test_connection(self) -> Dict[str, Any]:
        return self.request("trading", "GET", "/v2/account")

    def get_account_balance(self) -> Dict[str, Any]:
        result = self.request("trading", "GET", "/v2/account")
        if not result.get("success"):
            return result

        data = result.get("data", {}) or {}
        equity = float(data.get("equity", data.get("cash", 0)) or 0)
        return {
            "success": True,
            "balance": equity,
            "account": data,
        }

    def issue_tokens(
        self,
        client_id: str,
        client_secret: Optional[str] = None,
        client_assertion_type: Optional[str] = None,
        client_assertion: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Issue OAuth2 access token from Alpaca AuthX using client_credentials grant."""
        form_data: Dict[str, Any] = {
            "grant_type": "client_credentials",
            "client_id": client_id,
        }

        if client_secret:
            form_data["client_secret"] = client_secret
        if client_assertion_type:
            form_data["client_assertion_type"] = client_assertion_type
        if client_assertion:
            form_data["client_assertion"] = client_assertion

        return self.request(
            "auth",
            "POST",
            "/oauth2/token",
            data=form_data,
            content_type="application/x-www-form-urlencoded",
        )
