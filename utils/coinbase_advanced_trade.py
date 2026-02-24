"""
Coinbase Advanced Trade API Client
Full integration with the CDP Advanced Trade REST API using JWT (ES256) authentication.
Covers: Accounts, Orders, Products, Portfolios, Fees, Converts, and Payment Methods.

Reference: https://docs.cdp.coinbase.com/advanced-trade/docs/welcome
"""

import json
import time
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode

import jwt
import requests

from utils.encryption import encrypt_credentials, decrypt_credentials

logger = logging.getLogger(__name__)

# Advanced Trade API base URL
AT_BASE_URL = "https://api.coinbase.com/api/v3/brokerage"


class CoinbaseAdvancedTradeClient:
    """Client for the Coinbase Advanced Trade API with JWT auth."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.api_key: Optional[str] = None
        self.api_secret: Optional[str] = None
        self._load_credentials()

    # ------------------------------------------------------------------
    # Credential management
    # ------------------------------------------------------------------

    def _load_credentials(self):
        try:
            from models import APICredential
            cred = APICredential.query.filter_by(
                user_id=self.user_id,
                provider='coinbase_advanced_trade',
                is_active=True,
            ).first()
            if cred:
                decrypted = decrypt_credentials(cred.encrypted_credentials)
                self.api_key = decrypted.get('api_key')
                self.api_secret = decrypted.get('api_secret')
                logger.info("Loaded Coinbase Advanced Trade credentials for user %s", self.user_id)
            else:
                logger.warning("No Coinbase Advanced Trade credentials for user %s", self.user_id)
        except Exception as e:
            logger.error("Error loading Advanced Trade credentials: %s", e)

    def save_credentials(self, api_key: str, api_secret: str):
        from models import APICredential
        from app import db
        creds = encrypt_credentials({'api_key': api_key, 'api_secret': api_secret})
        existing = APICredential.query.filter_by(
            user_id=self.user_id, provider='coinbase_advanced_trade'
        ).first()
        if existing:
            existing.encrypted_credentials = creds
            existing.is_active = True
            existing.credential_type = 'api_key'
            existing.updated_at = datetime.utcnow()
        else:
            new_cred = APICredential(
                user_id=self.user_id,
                provider='coinbase_advanced_trade',
                encrypted_credentials=creds,
                credential_type='api_key',
                is_active=True,
            )
            db.session.add(new_cred)
        db.session.commit()
        self.api_key = api_key
        self.api_secret = api_secret
        logger.info("Saved Advanced Trade credentials for user %s", self.user_id)

    # ------------------------------------------------------------------
    # JWT helpers
    # ------------------------------------------------------------------

    def _generate_jwt(self, method: str = "", path: str = "") -> str:
        """Generate a short-lived CDP JWT (ES256) for REST requests."""
        if not self.api_key or not self.api_secret:
            raise ValueError("Coinbase Advanced Trade API credentials not configured")
        now = int(time.time())
        uri = f"{method} {path}" if method and path else ""
        payload = {
            "iss": "cdp",
            "sub": self.api_key,
            "nbf": now,
            "exp": now + 120,
        }
        if uri:
            payload["uri"] = uri
        headers = {"kid": self.api_key, "nonce": uuid.uuid4().hex, "typ": "JWT"}
        return jwt.encode(payload, self.api_secret, algorithm="ES256", headers=headers)

    # ------------------------------------------------------------------
    # HTTP helper
    # ------------------------------------------------------------------

    def _request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Dict:
        """Perform an authenticated request against the Advanced Trade REST API."""
        url = f"{AT_BASE_URL}{endpoint}"
        if params:
            url = f"{url}?{urlencode(params, doseq=True)}"

        # Build the URI string that Coinbase expects in the JWT
        # Format: "METHOD host+path"
        request_path = f"/api/v3/brokerage{endpoint}"
        token = self._generate_jwt(method.upper(), request_path)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Arbion-Trading-Platform/2.0",
        }

        try:
            resp = requests.request(
                method.upper(), url, headers=headers,
                json=data if data else None,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json() if resp.content else {}
        except requests.exceptions.HTTPError as e:
            body = ""
            if e.response is not None:
                body = e.response.text[:500]
            logger.error("Advanced Trade API %s %s failed: %s — %s", method, endpoint, e, body)
            raise
        except requests.exceptions.RequestException as e:
            logger.error("Advanced Trade API request error: %s", e)
            raise

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------

    def test_connection(self) -> Dict:
        try:
            accounts = self.list_accounts(limit=1)
            return {'success': True, 'message': 'Connected to Coinbase Advanced Trade API'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # ==================================================================
    #  ACCOUNTS
    # ==================================================================

    def list_accounts(self, limit: int = 49, cursor: str = None) -> Dict:
        params: Dict[str, Any] = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/accounts", params=params)

    def get_account(self, account_uuid: str) -> Dict:
        return self._request("GET", f"/accounts/{account_uuid}")

    # ==================================================================
    #  PRODUCTS  (market data)
    # ==================================================================

    def list_products(self, product_type: str = None, limit: int = None,
                      offset: int = None, product_ids: List[str] = None) -> Dict:
        params: Dict[str, Any] = {}
        if product_type:
            params["product_type"] = product_type
        if limit:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        if product_ids:
            params["product_ids"] = product_ids
        return self._request("GET", "/products", params=params)

    def get_product(self, product_id: str) -> Dict:
        return self._request("GET", f"/products/{product_id}")

    def get_product_candles(self, product_id: str, start: str, end: str,
                            granularity: str = "ONE_HOUR") -> Dict:
        """
        Granularity options: ONE_MINUTE, FIVE_MINUTE, FIFTEEN_MINUTE,
        THIRTY_MINUTE, ONE_HOUR, TWO_HOUR, SIX_HOUR, ONE_DAY.
        start/end are Unix timestamps (string).
        """
        params = {"start": start, "end": end, "granularity": granularity}
        return self._request("GET", f"/products/{product_id}/candles", params=params)

    def get_market_trades(self, product_id: str, limit: int = 100,
                          start: str = None, end: str = None) -> Dict:
        params: Dict[str, Any] = {"limit": limit}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return self._request("GET", f"/products/{product_id}/ticker", params=params)

    def get_product_book(self, product_id: str, limit: int = None) -> Dict:
        params: Dict[str, Any] = {"product_id": product_id}
        if limit:
            params["limit"] = limit
        return self._request("GET", "/product_book", params=params)

    def get_best_bid_ask(self, product_ids: List[str] = None) -> Dict:
        params = {}
        if product_ids:
            params["product_ids"] = product_ids
        return self._request("GET", "/best_bid_ask", params=params)

    # ==================================================================
    #  ORDERS
    # ==================================================================

    def create_order(self, client_order_id: str, product_id: str, side: str,
                     order_configuration: Dict) -> Dict:
        """
        side: "BUY" or "SELL"
        order_configuration is one of:
          {"market_market_ioc": {"quote_size": "10.00"}}
          {"limit_limit_gtc": {"base_size": "0.001", "limit_price": "50000", "post_only": false}}
          {"limit_limit_gtd": {..., "end_time": "2025-01-01T00:00:00Z"}}
          {"stop_limit_stop_limit_gtc": {"base_size":..., "limit_price":..., "stop_price":...}}
          {"stop_limit_stop_limit_gtd": {..., "end_time":...}}
          {"trigger_bracket_gtc": {"base_size":..., "limit_price":..., "stop_trigger_price":...}}
          {"trigger_bracket_gtd": {..., "end_time":...}}
        """
        data = {
            "client_order_id": client_order_id,
            "product_id": product_id,
            "side": side.upper(),
            "order_configuration": order_configuration,
        }
        return self._request("POST", "/orders", data=data)

    def create_market_order(self, product_id: str, side: str,
                            quote_size: str = None, base_size: str = None,
                            user_id: int = None, is_simulation: bool = False) -> Dict:
        """Convenience: place a market order and record in Trade table."""
        client_order_id = str(uuid.uuid4())
        config: Dict[str, Any] = {}
        if side.upper() == "BUY":
            if not quote_size:
                raise ValueError("quote_size required for market BUY")
            config = {"market_market_ioc": {"quote_size": str(quote_size)}}
        else:
            if not base_size:
                raise ValueError("base_size required for market SELL")
            config = {"market_market_ioc": {"base_size": str(base_size)}}

        from models import Trade
        from app import db

        trade = Trade(
            user_id=user_id or int(self.user_id),
            provider='coinbase_advanced_trade',
            symbol=product_id,
            side=side.lower(),
            quantity=float(base_size or 0),
            amount=float(quote_size or 0),
            trade_type='market',
            status='pending',
            is_simulation=is_simulation,
        )

        if is_simulation:
            try:
                product = self.get_product(product_id)
                price = float(product.get('price', 0))
            except Exception:
                price = 0
            trade.price = price
            trade.status = 'executed'
            trade.executed_at = datetime.utcnow()
            trade.execution_details = json.dumps({'simulated': True, 'price': price})
            db.session.add(trade)
            db.session.commit()
            return {'success': True, 'simulated': True, 'trade_id': trade.id, 'price': price}

        result = self.create_order(client_order_id, product_id, side.upper(), config)
        trade.order_id = result.get('order_id') or result.get('success_response', {}).get('order_id')
        trade.status = 'executed'
        trade.executed_at = datetime.utcnow()
        trade.execution_details = json.dumps(result)
        db.session.add(trade)
        db.session.commit()
        return {'success': True, 'order_id': trade.order_id, 'trade_id': trade.id, 'response': result}

    def create_limit_order(self, product_id: str, side: str, base_size: str,
                           limit_price: str, post_only: bool = False,
                           end_time: str = None, user_id: int = None,
                           is_simulation: bool = False) -> Dict:
        """Convenience: place a limit order (GTC or GTD) and record in Trade table."""
        client_order_id = str(uuid.uuid4())
        if end_time:
            config = {
                "limit_limit_gtd": {
                    "base_size": str(base_size),
                    "limit_price": str(limit_price),
                    "post_only": post_only,
                    "end_time": end_time,
                }
            }
        else:
            config = {
                "limit_limit_gtc": {
                    "base_size": str(base_size),
                    "limit_price": str(limit_price),
                    "post_only": post_only,
                }
            }

        from models import Trade
        from app import db

        trade = Trade(
            user_id=user_id or int(self.user_id),
            provider='coinbase_advanced_trade',
            symbol=product_id,
            side=side.lower(),
            quantity=float(base_size),
            price=float(limit_price),
            trade_type='limit',
            status='pending',
            is_simulation=is_simulation,
        )

        if is_simulation:
            trade.status = 'executed'
            trade.executed_at = datetime.utcnow()
            trade.execution_details = json.dumps({
                'simulated': True, 'limit_price': limit_price
            })
            db.session.add(trade)
            db.session.commit()
            return {'success': True, 'simulated': True, 'trade_id': trade.id}

        result = self.create_order(client_order_id, product_id, side.upper(), config)
        trade.order_id = result.get('order_id') or result.get('success_response', {}).get('order_id')
        trade.status = 'executed'
        trade.executed_at = datetime.utcnow()
        trade.execution_details = json.dumps(result)
        db.session.add(trade)
        db.session.commit()
        return {'success': True, 'order_id': trade.order_id, 'trade_id': trade.id, 'response': result}

    def create_stop_limit_order(self, product_id: str, side: str, base_size: str,
                                limit_price: str, stop_price: str,
                                end_time: str = None) -> Dict:
        client_order_id = str(uuid.uuid4())
        if end_time:
            config = {
                "stop_limit_stop_limit_gtd": {
                    "base_size": str(base_size),
                    "limit_price": str(limit_price),
                    "stop_price": str(stop_price),
                    "end_time": end_time,
                }
            }
        else:
            config = {
                "stop_limit_stop_limit_gtc": {
                    "base_size": str(base_size),
                    "limit_price": str(limit_price),
                    "stop_price": str(stop_price),
                }
            }
        return self.create_order(client_order_id, product_id, side.upper(), config)

    def create_bracket_order(self, product_id: str, side: str, base_size: str,
                             limit_price: str, stop_trigger_price: str,
                             end_time: str = None) -> Dict:
        client_order_id = str(uuid.uuid4())
        if end_time:
            config = {
                "trigger_bracket_gtd": {
                    "base_size": str(base_size),
                    "limit_price": str(limit_price),
                    "stop_trigger_price": str(stop_trigger_price),
                    "end_time": end_time,
                }
            }
        else:
            config = {
                "trigger_bracket_gtc": {
                    "base_size": str(base_size),
                    "limit_price": str(limit_price),
                    "stop_trigger_price": str(stop_trigger_price),
                }
            }
        return self.create_order(client_order_id, product_id, side.upper(), config)

    def cancel_orders(self, order_ids: List[str]) -> Dict:
        return self._request("POST", "/orders/batch_cancel", data={"order_ids": order_ids})

    def list_orders(self, product_id: str = None, order_status: List[str] = None,
                    limit: int = None, start_date: str = None, end_date: str = None,
                    order_type: str = None, order_side: str = None,
                    cursor: str = None, product_type: str = None,
                    order_placement_source: str = None,
                    contract_expiry_type: str = None) -> Dict:
        params: Dict[str, Any] = {}
        if product_id:
            params["product_id"] = product_id
        if order_status:
            params["order_status"] = order_status
        if limit:
            params["limit"] = limit
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if order_type:
            params["order_type"] = order_type
        if order_side:
            params["order_side"] = order_side
        if cursor:
            params["cursor"] = cursor
        if product_type:
            params["product_type"] = product_type
        if order_placement_source:
            params["order_placement_source"] = order_placement_source
        if contract_expiry_type:
            params["contract_expiry_type"] = contract_expiry_type
        return self._request("GET", "/orders/historical/batch", params=params)

    def get_order(self, order_id: str) -> Dict:
        return self._request("GET", f"/orders/historical/{order_id}")

    def list_fills(self, order_id: str = None, product_id: str = None,
                   start_sequence_timestamp: str = None,
                   end_sequence_timestamp: str = None,
                   limit: int = None, cursor: str = None) -> Dict:
        params: Dict[str, Any] = {}
        if order_id:
            params["order_id"] = order_id
        if product_id:
            params["product_id"] = product_id
        if start_sequence_timestamp:
            params["start_sequence_timestamp"] = start_sequence_timestamp
        if end_sequence_timestamp:
            params["end_sequence_timestamp"] = end_sequence_timestamp
        if limit:
            params["limit"] = limit
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/orders/historical/fills", params=params)

    def edit_order(self, order_id: str, price: str = None, size: str = None) -> Dict:
        data: Dict[str, Any] = {"order_id": order_id}
        if price:
            data["price"] = str(price)
        if size:
            data["size"] = str(size)
        return self._request("POST", "/orders/edit", data=data)

    def preview_edit_order(self, order_id: str, price: str = None, size: str = None) -> Dict:
        data: Dict[str, Any] = {"order_id": order_id}
        if price:
            data["price"] = str(price)
        if size:
            data["size"] = str(size)
        return self._request("POST", "/orders/edit_preview", data=data)

    def preview_order(self, product_id: str, side: str,
                      order_configuration: Dict) -> Dict:
        data = {
            "product_id": product_id,
            "side": side.upper(),
            "order_configuration": order_configuration,
        }
        return self._request("POST", "/orders/preview", data=data)

    def close_position(self, client_order_id: str, product_id: str,
                       size: str = None) -> Dict:
        data: Dict[str, Any] = {
            "client_order_id": client_order_id,
            "product_id": product_id,
        }
        if size:
            data["size"] = str(size)
        return self._request("POST", "/orders/close_position", data=data)

    # ==================================================================
    #  PORTFOLIOS
    # ==================================================================

    def list_portfolios(self, portfolio_type: str = None) -> Dict:
        params = {}
        if portfolio_type:
            params["portfolio_type"] = portfolio_type
        return self._request("GET", "/portfolios", params=params)

    def create_portfolio(self, name: str) -> Dict:
        return self._request("POST", "/portfolios", data={"name": name})

    def get_portfolio_breakdown(self, portfolio_uuid: str, currency: str = None) -> Dict:
        params = {}
        if currency:
            params["currency"] = currency
        return self._request("GET", f"/portfolios/{portfolio_uuid}", params=params)

    def move_portfolio_funds(self, funds_value: str, funds_currency: str,
                             source_portfolio_uuid: str,
                             target_portfolio_uuid: str) -> Dict:
        data = {
            "funds": {"value": str(funds_value), "currency": funds_currency},
            "source_portfolio_uuid": source_portfolio_uuid,
            "target_portfolio_uuid": target_portfolio_uuid,
        }
        return self._request("POST", "/portfolios/move_funds", data=data)

    def edit_portfolio(self, portfolio_uuid: str, name: str) -> Dict:
        return self._request("PUT", f"/portfolios/{portfolio_uuid}", data={"name": name})

    def delete_portfolio(self, portfolio_uuid: str) -> Dict:
        return self._request("DELETE", f"/portfolios/{portfolio_uuid}")

    # ==================================================================
    #  CONVERTS
    # ==================================================================

    def create_convert_quote(self, from_account: str, to_account: str,
                             amount: str, trade_incentive_metadata: Dict = None) -> Dict:
        data: Dict[str, Any] = {
            "from_account": from_account,
            "to_account": to_account,
            "amount": str(amount),
        }
        if trade_incentive_metadata:
            data["trade_incentive_metadata"] = trade_incentive_metadata
        return self._request("POST", "/convert/quote", data=data)

    def commit_convert_trade(self, trade_id: str, from_account: str,
                             to_account: str) -> Dict:
        data = {
            "from_account": from_account,
            "to_account": to_account,
        }
        return self._request("POST", f"/convert/trade/{trade_id}", data=data)

    def get_convert_trade(self, trade_id: str, from_account: str,
                          to_account: str) -> Dict:
        params = {"from_account": from_account, "to_account": to_account}
        return self._request("GET", f"/convert/trade/{trade_id}", params=params)

    # ==================================================================
    #  FEES
    # ==================================================================

    def get_transaction_summary(self, start_date: str = None, end_date: str = None,
                                user_native_currency: str = "USD",
                                product_type: str = None) -> Dict:
        params: Dict[str, Any] = {"user_native_currency": user_native_currency}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if product_type:
            params["product_type"] = product_type
        return self._request("GET", "/transaction_summary", params=params)

    # ==================================================================
    #  PAYMENT METHODS
    # ==================================================================

    def list_payment_methods(self) -> Dict:
        return self._request("GET", "/payment_methods")

    def get_payment_method(self, payment_method_id: str) -> Dict:
        return self._request("GET", f"/payment_methods/{payment_method_id}")

    # ==================================================================
    #  PERPETUALS  (for futures-enabled accounts)
    # ==================================================================

    def get_perpetuals_portfolio_summary(self, portfolio_uuid: str) -> Dict:
        return self._request("GET", f"/intx/portfolio/{portfolio_uuid}")

    def list_perpetuals_positions(self, portfolio_uuid: str) -> Dict:
        return self._request("GET", f"/intx/positions/{portfolio_uuid}")

    def get_perpetuals_position(self, portfolio_uuid: str, symbol: str) -> Dict:
        return self._request("GET", f"/intx/positions/{portfolio_uuid}/{symbol}")

    def get_portfolio_balances(self, portfolio_uuid: str) -> Dict:
        return self._request("GET", f"/intx/balances/{portfolio_uuid}")

    def allocate_portfolio(self, portfolio_uuid: str, symbol: str,
                           amount: str, currency: str) -> Dict:
        data = {
            "portfolio_uuid": portfolio_uuid,
            "symbol": symbol,
            "amount": str(amount),
            "currency": currency,
        }
        return self._request("POST", "/intx/allocate", data=data)

    # ==================================================================
    #  FUTURES / US DERIVATIVES
    # ==================================================================

    def get_futures_balance_summary(self) -> Dict:
        return self._request("GET", "/cfm/balance_summary")

    def list_futures_positions(self) -> Dict:
        return self._request("GET", "/cfm/positions")

    def get_futures_position(self, product_id: str) -> Dict:
        return self._request("GET", f"/cfm/positions/{product_id}")

    def schedule_futures_sweep(self, usd_amount: str = None) -> Dict:
        data = {}
        if usd_amount:
            data["usd_amount"] = str(usd_amount)
        return self._request("POST", "/cfm/sweeps/schedule", data=data)

    def list_futures_sweeps(self) -> Dict:
        return self._request("GET", "/cfm/sweeps")

    def cancel_pending_futures_sweep(self) -> Dict:
        return self._request("DELETE", "/cfm/sweeps")

    def get_current_margin_window(self, margin_profile_type: str = None) -> Dict:
        params = {}
        if margin_profile_type:
            params["margin_profile_type"] = margin_profile_type
        return self._request("GET", "/cfm/intraday/current_margin_window", params=params)

    def get_intraday_margin_setting(self) -> Dict:
        return self._request("GET", "/cfm/intraday/margin_setting")

    def set_intraday_margin_setting(self, setting: str) -> Dict:
        return self._request("POST", "/cfm/intraday/margin_setting", data={"setting": setting})

    # ==================================================================
    #  PUBLIC ENDPOINTS  (no auth required, but we send it anyway)
    # ==================================================================

    def get_server_time(self) -> Dict:
        return self._request("GET", "/time")

    def get_api_key_permissions(self) -> Dict:
        return self._request("GET", "/key_permissions")
