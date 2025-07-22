import requests
import uuid

class CoinbaseTransferClient:
    """Simple client for Coinbase 'Send Money' API."""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://api.coinbase.com/v2"

    def send_crypto(self, account_id: str, to: str, amount: str, currency: str, **kwargs):
        """Send crypto funds from an account using OAuth access token."""
        url = f"{self.base_url}/accounts/{account_id}/transactions"
        payload = {
            "type": "send",
            "to": to,
            "amount": str(amount),
            "currency": currency,
            "idem": kwargs.get("idem", str(uuid.uuid4())),
        }
        optional_fields = [
            "description",
            "skip_notifications",
            "destination_tag",
            "network",
            "travel_rule_data",
        ]
        for field in optional_fields:
            if field in kwargs and kwargs[field] is not None:
                payload[field] = kwargs[field]
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json()
