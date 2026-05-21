"""Alpaca US API client covering trading, market data, and broker reference endpoints."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import requests


class AlpacaAPIClient:
    """Thin Alpaca client with generic request support for all documented US endpoints."""

    TRADING_BASE = "https://api.alpaca.markets"
    DATA_BASE = "https://data.alpaca.markets"
    BROKER_BASE = "https://broker-api.alpaca.markets"
    AUTH_BASE = "https://authx.alpaca.markets/v1"
    SANDBOX_AUTH_BASE = "https://authx.sandbox.alpaca.markets/v1"

    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None, paper: bool = False):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")
        self.paper = paper
        if paper:
            self.TRADING_BASE = "https://paper-api.alpaca.markets"

    def _headers(self) -> Dict[str, str]:
        if not self.api_key or not self.secret_key:
            raise ValueError("Alpaca API key and secret are required")
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "ArbionTrader/1.0",
        }

    def request(self, domain: str, method: str, path: str, params: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        base_map = {
            "trading": self.TRADING_BASE,
            "market_data": self.DATA_BASE,
            "broker": self.BROKER_BASE,
            "auth": self.SANDBOX_AUTH_BASE if self.paper else self.AUTH_BASE,
        }
        base_url = base_map.get(domain)
        if not base_url:
            raise ValueError("domain must be one of: trading, market_data, broker, auth")

        url = f"{base_url}{path if path.startswith('/') else '/' + path}"
        request_headers = self._headers() if domain != "auth" else {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "ArbionTrader/1.0",
        }
        response = requests.request(method.upper(), url, headers=request_headers, params=params, json=json_data, timeout=25)

        content_type = response.headers.get("content-type", "")
        payload: Any = response.json() if "application/json" in content_type else response.text
        if response.status_code >= 400:
            return {"success": False, "status_code": response.status_code, "error": payload}

        return {"success": True, "status_code": response.status_code, "data": payload}

    def test_connection(self) -> Dict[str, Any]:
        return self.request("trading", "GET", "/v2/account")

    def get_account_balance(self) -> Dict[str, Any]:
        result = self.request("trading", "GET", "/v2/account")
        if not result.get("success"):
            return result

        data = result.get("data", {})
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

        url = f"{self.SANDBOX_AUTH_BASE if self.paper else self.AUTH_BASE}/oauth2/token"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "ArbionTrader/1.0",
        }

        response = requests.post(url, headers=headers, data=form_data, timeout=25)

        content_type = response.headers.get("content-type", "")
        payload: Any = response.json() if "application/json" in content_type else response.text
        if response.status_code >= 400:
            return {"success": False, "status_code": response.status_code, "error": payload}

        return {"success": True, "status_code": response.status_code, "data": payload}
