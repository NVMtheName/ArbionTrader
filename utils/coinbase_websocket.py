import asyncio
import json
import time
import uuid
from typing import List

import jwt
import websockets

MARKET_WS_URL = "wss://advanced-trade-ws.coinbase.com"
USER_WS_URL = "wss://advanced-trade-ws-user.coinbase.com"


def generate_jwt(api_key: str, signing_key: str) -> str:
    """Generate a short-lived JWT for WebSocket authentication."""
    now = int(time.time())
    payload = {"iss": "cdp", "nbf": now, "exp": now + 120, "sub": api_key}
    headers = {"kid": api_key, "nonce": uuid.uuid4().hex}
    return jwt.encode(payload, signing_key, algorithm="ES256", headers=headers)


async def subscribe_ticker(product_ids: List[str]):
    """Subscribe to ticker updates for given products (public feed)."""
    async with websockets.connect(MARKET_WS_URL) as ws:
        await ws.send(
            json.dumps({"type": "subscribe", "product_ids": product_ids, "channel": "ticker"})
        )
        return await ws.recv()


async def subscribe_user(product_ids: List[str], api_key: str, signing_key: str):
    """Subscribe to user channel with authentication."""
    token = generate_jwt(api_key, signing_key)
    async with websockets.connect(USER_WS_URL) as ws:
        await ws.send(
            json.dumps(
                {"type": "subscribe", "channel": "user", "product_ids": product_ids, "jwt": token}
            )
        )
        return await ws.recv()
