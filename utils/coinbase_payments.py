"""
Coinbase Payments API Client
Handles deposits, withdrawals, transfers, and webhook subscriptions.
Uses the same CDP JWT (ES256) authentication as Advanced Trade.

Reference: https://docs.cdp.coinbase.com/get-started/docs/welcome
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

PAYMENTS_BASE_URL = "https://api.coinbase.com/api/v3/brokerage"


class CoinbasePaymentsClient:
    """Client for Coinbase payment/transfer operations."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.api_key: Optional[str] = None
        self.api_secret: Optional[str] = None
        self._load_credentials()

    # ------------------------------------------------------------------
    # Credential management (shares provider with Advanced Trade)
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
                logger.info("Loaded Coinbase payments credentials for user %s", self.user_id)
            else:
                logger.warning("No Coinbase credentials for user %s", self.user_id)
        except Exception as e:
            logger.error("Error loading payments credentials: %s", e)

    # ------------------------------------------------------------------
    # JWT + HTTP helpers
    # ------------------------------------------------------------------

    def _generate_jwt(self, method: str = "", path: str = "") -> str:
        if not self.api_key or not self.api_secret:
            raise ValueError("Coinbase API credentials not configured")
        now = int(time.time())
        uri = f"{method} {path}" if method and path else ""
        payload = {"iss": "cdp", "sub": self.api_key, "nbf": now, "exp": now + 120}
        if uri:
            payload["uri"] = uri
        headers = {"kid": self.api_key, "nonce": uuid.uuid4().hex, "typ": "JWT"}
        return jwt.encode(payload, self.api_secret, algorithm="ES256", headers=headers)

    def _request(self, method: str, endpoint: str,
                 params: Dict = None, data: Dict = None,
                 base_url: str = None) -> Dict:
        url_base = base_url or PAYMENTS_BASE_URL
        url = f"{url_base}{endpoint}"
        if params:
            url = f"{url}?{urlencode(params, doseq=True)}"

        request_path = endpoint if base_url else f"/api/v3/brokerage{endpoint}"
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
            body = e.response.text[:500] if e.response is not None else ""
            logger.error("Payments API %s %s failed: %s — %s", method, endpoint, e, body)
            raise
        except requests.exceptions.RequestException as e:
            logger.error("Payments API request error: %s", e)
            raise

    # ==================================================================
    #  PAYMENT METHODS
    # ==================================================================

    def list_payment_methods(self) -> Dict:
        return self._request("GET", "/payment_methods")

    def get_payment_method(self, payment_method_id: str) -> Dict:
        return self._request("GET", f"/payment_methods/{payment_method_id}")

    # ==================================================================
    #  ACCOUNT DEPOSITS
    # ==================================================================

    def deposit_from_payment_method(self, amount: str, currency: str,
                                    payment_method_id: str) -> Dict:
        """Deposit funds from a linked payment method (bank, card)."""
        data = {
            "amount": str(amount),
            "currency": currency,
            "payment_method_id": payment_method_id,
        }
        return self._request("POST", "/deposits/payment_method", data=data)

    def deposit_from_coinbase_account(self, amount: str, currency: str,
                                      coinbase_account_id: str) -> Dict:
        """Deposit funds from a Coinbase wallet account."""
        data = {
            "amount": str(amount),
            "currency": currency,
            "coinbase_account_id": coinbase_account_id,
        }
        return self._request("POST", "/deposits/coinbase_account", data=data)

    # ==================================================================
    #  WITHDRAWALS
    # ==================================================================

    def withdraw_to_payment_method(self, amount: str, currency: str,
                                   payment_method_id: str) -> Dict:
        """Withdraw to a linked payment method."""
        data = {
            "amount": str(amount),
            "currency": currency,
            "payment_method_id": payment_method_id,
        }
        return self._request("POST", "/withdrawals/payment_method", data=data)

    def withdraw_to_coinbase_account(self, amount: str, currency: str,
                                     coinbase_account_id: str) -> Dict:
        """Withdraw to a Coinbase wallet account."""
        data = {
            "amount": str(amount),
            "currency": currency,
            "coinbase_account_id": coinbase_account_id,
        }
        return self._request("POST", "/withdrawals/coinbase_account", data=data)

    def withdraw_to_crypto_address(self, amount: str, currency: str,
                                   crypto_address: str, network: str = None,
                                   destination_tag: str = None) -> Dict:
        """Withdraw crypto to an external address."""
        data: Dict[str, Any] = {
            "amount": str(amount),
            "currency": currency,
            "crypto_address": crypto_address,
        }
        if network:
            data["network"] = network
        if destination_tag:
            data["destination_tag"] = destination_tag
        return self._request("POST", "/withdrawals/crypto", data=data)

    def get_crypto_withdrawal_fee_estimate(self, currency: str,
                                           crypto_address: str,
                                           network: str = None) -> Dict:
        """Get fee estimate for a crypto withdrawal."""
        params: Dict[str, Any] = {
            "currency": currency,
            "crypto_address": crypto_address,
        }
        if network:
            params["network"] = network
        return self._request("GET", "/withdrawals/fee_estimate", params=params)

    # ==================================================================
    #  TRANSFERS
    # ==================================================================

    def list_transfers(self, transfer_type: str = None, limit: int = None,
                       cursor: str = None) -> Dict:
        params: Dict[str, Any] = {}
        if transfer_type:
            params["type"] = transfer_type
        if limit:
            params["limit"] = limit
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/transfers", params=params)

    def get_transfer(self, transfer_id: str) -> Dict:
        return self._request("GET", f"/transfers/{transfer_id}")

    # ==================================================================
    #  COINBASE WALLETS (for deposit/withdraw operations)
    # ==================================================================

    def list_coinbase_wallets(self) -> Dict:
        """List Coinbase wallet accounts available for deposit/withdrawal."""
        return self._request("GET", "/coinbase_accounts")

    def generate_crypto_address(self, account_id: str) -> Dict:
        """Generate a new crypto deposit address for a wallet account."""
        return self._request("POST", f"/coinbase_accounts/{account_id}/addresses")

    # ==================================================================
    #  CONVERSIONS
    # ==================================================================

    def convert_currency(self, from_currency: str, to_currency: str,
                         amount: str) -> Dict:
        """Convert between currencies."""
        data = {
            "from": from_currency,
            "to": to_currency,
            "amount": str(amount),
        }
        return self._request("POST", "/conversions", data=data)

    def get_conversion(self, conversion_id: str) -> Dict:
        return self._request("GET", f"/conversions/{conversion_id}")

    # ==================================================================
    #  CURRENCIES
    # ==================================================================

    def list_currencies(self) -> Dict:
        return self._request("GET", "/currencies")

    def get_currency(self, currency_id: str) -> Dict:
        return self._request("GET", f"/currencies/{currency_id}")

    # ==================================================================
    #  FEES
    # ==================================================================

    def get_fees(self) -> Dict:
        return self._request("GET", "/fees")

    # ==================================================================
    #  CONNECTION TEST
    # ==================================================================

    def test_connection(self) -> Dict:
        try:
            self.list_payment_methods()
            return {'success': True, 'message': 'Payments API connection successful'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
