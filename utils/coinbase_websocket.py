"""
Coinbase Advanced Trade WebSocket Client
Full-featured async WebSocket integration covering all CDP channels:
  - heartbeats, candles, market_trades, status, ticker, ticker_batch,
    level2, user (authenticated)

Reference: https://docs.cdp.coinbase.com/advanced-trade/docs/ws-overview
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

import jwt
import websockets

logger = logging.getLogger(__name__)

# Public market data feed
MARKET_WS_URL = "wss://advanced-trade-ws.coinbase.com"
# Authenticated user-level feed
USER_WS_URL = "wss://advanced-trade-ws-user.coinbase.com"

# Available channels
CHANNEL_HEARTBEATS = "heartbeats"
CHANNEL_CANDLES = "candles"
CHANNEL_MARKET_TRADES = "market_trades"
CHANNEL_STATUS = "status"
CHANNEL_TICKER = "ticker"
CHANNEL_TICKER_BATCH = "ticker_batch"
CHANNEL_LEVEL2 = "level2"
CHANNEL_USER = "user"

PUBLIC_CHANNELS = {
    CHANNEL_HEARTBEATS,
    CHANNEL_CANDLES,
    CHANNEL_MARKET_TRADES,
    CHANNEL_STATUS,
    CHANNEL_TICKER,
    CHANNEL_TICKER_BATCH,
    CHANNEL_LEVEL2,
}
AUTHENTICATED_CHANNELS = {CHANNEL_USER}


def generate_jwt(api_key: str, signing_key: str) -> str:
    """Generate a short-lived JWT for WebSocket authentication (ES256)."""
    now = int(time.time())
    payload = {"iss": "cdp", "nbf": now, "exp": now + 120, "sub": api_key}
    headers = {"kid": api_key, "nonce": uuid.uuid4().hex, "typ": "JWT"}
    return jwt.encode(payload, signing_key, algorithm="ES256", headers=headers)


class CoinbaseWebSocket:
    """Manages a persistent WebSocket connection to the Coinbase Advanced Trade feed."""

    def __init__(
        self,
        api_key: str = None,
        api_secret: str = None,
        on_message: Callable[[Dict], None] = None,
        on_error: Callable[[Exception], None] = None,
        on_close: Callable[[], None] = None,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.on_message = on_message or self._default_on_message
        self.on_error = on_error or self._default_on_error
        self.on_close = on_close or (lambda: None)
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._running = False
        self._subscriptions: Dict[str, List[str]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self, authenticated: bool = False):
        """Open a WebSocket connection."""
        url = USER_WS_URL if authenticated else MARKET_WS_URL
        try:
            self._ws = await websockets.connect(url, ping_interval=20, ping_timeout=10)
            self._running = True
            logger.info("WebSocket connected to %s", url)
        except Exception as e:
            logger.error("WebSocket connection failed: %s", e)
            raise

    async def disconnect(self):
        """Gracefully close the WebSocket."""
        self._running = False
        if self._ws:
            await self._ws.close()
            logger.info("WebSocket disconnected")
        self._ws = None

    async def listen(self):
        """Listen for messages until the connection closes or is stopped."""
        if not self._ws:
            raise RuntimeError("Not connected. Call connect() first.")
        try:
            async for raw_msg in self._ws:
                try:
                    msg = json.loads(raw_msg)
                    self.on_message(msg)
                except json.JSONDecodeError:
                    logger.warning("Received non-JSON message: %s", raw_msg[:200])
        except websockets.ConnectionClosed as e:
            logger.info("WebSocket closed: %s", e)
        except Exception as e:
            self.on_error(e)
        finally:
            self.on_close()

    async def run(self, authenticated: bool = False,
                  channels: Dict[str, List[str]] = None,
                  reconnect: bool = True, max_retries: int = 5):
        """Connect, subscribe, and listen with optional auto-reconnect."""
        retries = 0
        while True:
            try:
                await self.connect(authenticated=authenticated)
                if channels:
                    for channel, product_ids in channels.items():
                        await self.subscribe(channel, product_ids)
                retries = 0
                await self.listen()
            except Exception as e:
                logger.error("WebSocket error: %s", e)
                self.on_error(e)

            if not reconnect or retries >= max_retries:
                break
            retries += 1
            wait = min(2 ** retries, 30)
            logger.info("Reconnecting in %ds (attempt %d/%d)...", wait, retries, max_retries)
            await asyncio.sleep(wait)

    # ------------------------------------------------------------------
    # Subscribe / Unsubscribe
    # ------------------------------------------------------------------

    async def subscribe(self, channel: str, product_ids: List[str]):
        """Subscribe to a channel for the given product IDs."""
        if not self._ws:
            raise RuntimeError("Not connected")
        msg: Dict[str, Any] = {
            "type": "subscribe",
            "product_ids": product_ids,
            "channel": channel,
        }
        if channel in AUTHENTICATED_CHANNELS:
            if not self.api_key or not self.api_secret:
                raise ValueError("Authentication credentials required for %s channel" % channel)
            msg["jwt"] = generate_jwt(self.api_key, self.api_secret)

        await self._ws.send(json.dumps(msg))
        self._subscriptions[channel] = product_ids
        logger.info("Subscribed to %s for %s", channel, product_ids)

    async def unsubscribe(self, channel: str, product_ids: List[str]):
        """Unsubscribe from a channel."""
        if not self._ws:
            raise RuntimeError("Not connected")
        msg: Dict[str, Any] = {
            "type": "unsubscribe",
            "product_ids": product_ids,
            "channel": channel,
        }
        if channel in AUTHENTICATED_CHANNELS and self.api_key and self.api_secret:
            msg["jwt"] = generate_jwt(self.api_key, self.api_secret)

        await self._ws.send(json.dumps(msg))
        self._subscriptions.pop(channel, None)
        logger.info("Unsubscribed from %s for %s", channel, product_ids)

    # ------------------------------------------------------------------
    # Convenience subscription helpers
    # ------------------------------------------------------------------

    async def subscribe_heartbeats(self, product_ids: List[str]):
        await self.subscribe(CHANNEL_HEARTBEATS, product_ids)

    async def subscribe_candles(self, product_ids: List[str]):
        await self.subscribe(CHANNEL_CANDLES, product_ids)

    async def subscribe_market_trades(self, product_ids: List[str]):
        await self.subscribe(CHANNEL_MARKET_TRADES, product_ids)

    async def subscribe_status(self, product_ids: List[str]):
        await self.subscribe(CHANNEL_STATUS, product_ids)

    async def subscribe_ticker(self, product_ids: List[str]):
        await self.subscribe(CHANNEL_TICKER, product_ids)

    async def subscribe_ticker_batch(self, product_ids: List[str]):
        await self.subscribe(CHANNEL_TICKER_BATCH, product_ids)

    async def subscribe_level2(self, product_ids: List[str]):
        await self.subscribe(CHANNEL_LEVEL2, product_ids)

    async def subscribe_user(self, product_ids: List[str]):
        await self.subscribe(CHANNEL_USER, product_ids)

    # ------------------------------------------------------------------
    # Default callbacks
    # ------------------------------------------------------------------

    @staticmethod
    def _default_on_message(msg: Dict):
        channel = msg.get("channel", "unknown")
        msg_type = msg.get("type", "unknown")
        logger.debug("WS [%s/%s]: %s", channel, msg_type, json.dumps(msg)[:200])

    @staticmethod
    def _default_on_error(error: Exception):
        logger.error("WS error: %s", error)


# ------------------------------------------------------------------
# Simple one-shot helpers (backwards-compatible with the old API)
# ------------------------------------------------------------------

async def subscribe_ticker(product_ids: List[str]) -> str:
    """Subscribe to ticker updates for given products (public feed)."""
    async with websockets.connect(MARKET_WS_URL) as ws:
        await ws.send(
            json.dumps({"type": "subscribe", "product_ids": product_ids, "channel": "ticker"})
        )
        return await ws.recv()


async def subscribe_user(product_ids: List[str], api_key: str, signing_key: str) -> str:
    """Subscribe to user channel with authentication."""
    token = generate_jwt(api_key, signing_key)
    async with websockets.connect(USER_WS_URL) as ws:
        await ws.send(
            json.dumps(
                {"type": "subscribe", "channel": "user", "product_ids": product_ids, "jwt": token}
            )
        )
        return await ws.recv()
