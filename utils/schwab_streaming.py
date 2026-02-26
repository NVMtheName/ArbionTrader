"""
Schwab Streaming Service for Arbion Trading Platform
=====================================================
Provides real-time market data streaming using both:
- schwab-py's StreamClient (handler-based async websocket)
- schwabdev's Stream (auto-reconnect, market-hours aware)

Features:
- Level 1 equity/option/futures/forex quotes
- OHLCV chart data (equity + futures)
- Level 2 order books (NYSE, NASDAQ, Options)
- Account activity notifications
- Screener data
- Thread-safe subscription management
- Automatic reconnection
"""

import asyncio
import json
import logging
import threading
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from collections import defaultdict

try:
    from schwab.streaming import StreamClient as SchwabPyStreamClient
    SCHWAB_PY_STREAMING = True
except ImportError:
    SCHWAB_PY_STREAMING = False
    SchwabPyStreamClient = None

try:
    import schwabdev
    SCHWABDEV_STREAMING = True
except ImportError:
    SCHWABDEV_STREAMING = False
    schwabdev = None

logger = logging.getLogger(__name__)


class StreamSubscription:
    """Tracks an active streaming subscription"""

    def __init__(self, stream_type: str, symbols: List[str], fields: List[str] = None):
        self.stream_type = stream_type
        self.symbols = symbols
        self.fields = fields
        self.created_at = datetime.utcnow()
        self.message_count = 0
        self.last_message_at = None


class SchwabStreamingService:
    """
    Unified streaming service that can use either schwab-py or schwabdev.

    schwab-py StreamClient:
    - Handler-based architecture (register callbacks per stream type)
    - Requires async event loop
    - Fine-grained field selection
    - Type-safe enums for field names

    schwabdev Stream:
    - Market-hours aware (auto start/stop)
    - Auto crash recovery
    - Simpler callback interface
    """

    # Stream types
    LEVEL_ONE_EQUITY = 'level_one_equity'
    LEVEL_ONE_OPTION = 'level_one_option'
    LEVEL_ONE_FUTURES = 'level_one_futures'
    LEVEL_ONE_FOREX = 'level_one_forex'
    CHART_EQUITY = 'chart_equity'
    CHART_FUTURES = 'chart_futures'
    NYSE_BOOK = 'nyse_book'
    NASDAQ_BOOK = 'nasdaq_book'
    OPTIONS_BOOK = 'options_book'
    SCREENER_EQUITY = 'screener_equity'
    SCREENER_OPTION = 'screener_option'
    ACCOUNT_ACTIVITY = 'account_activity'

    def __init__(self, user_id: int, preferred_library: str = 'schwabdev'):
        """
        Initialize streaming service.

        Args:
            user_id: User ID for credential lookup
            preferred_library: 'schwab_py' or 'schwabdev'
        """
        self.user_id = user_id
        self.preferred_library = preferred_library
        self._subscriptions: Dict[str, StreamSubscription] = {}
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._message_buffer: Dict[str, List[Dict]] = defaultdict(list)
        self._buffer_max = 100  # Keep last 100 messages per stream type
        self._stream_client = None
        self._stream_thread = None
        self._running = False
        self._lock = threading.Lock()

    @property
    def is_streaming(self) -> bool:
        return self._running

    def _get_schwab_py_client(self):
        """Get or create a schwab-py client for streaming"""
        if not SCHWAB_PY_STREAMING:
            return None
        try:
            from utils.schwab_py_client import create_schwab_py_client
            wrapper = create_schwab_py_client(self.user_id)
            if wrapper.client:
                return SchwabPyStreamClient(wrapper.client)
            return None
        except Exception as e:
            logger.error(f"Failed to create schwab-py stream client: {e}")
            return None

    def _get_schwabdev_client(self):
        """Get or create a schwabdev client for streaming"""
        if not SCHWABDEV_STREAMING:
            return None
        try:
            from utils.schwabdev_integration import create_schwabdev_manager
            manager = create_schwabdev_manager(str(self.user_id))
            if manager.client:
                return schwabdev.Stream(manager.client)
            return None
        except Exception as e:
            logger.error(f"Failed to create schwabdev stream client: {e}")
            return None

    # ─── Handler Registration ─────────────────────────────────────────────────

    def add_handler(self, stream_type: str, handler: Callable):
        """
        Register a callback handler for a stream type.

        Handler receives a dict with the parsed message data.
        """
        with self._lock:
            self._handlers[stream_type].append(handler)

    def remove_handler(self, stream_type: str, handler: Callable):
        """Remove a specific handler"""
        with self._lock:
            if handler in self._handlers[stream_type]:
                self._handlers[stream_type].remove(handler)

    def _dispatch(self, stream_type: str, data: Dict):
        """Dispatch message to registered handlers and buffer"""
        with self._lock:
            # Buffer the message
            buf = self._message_buffer[stream_type]
            buf.append({
                'timestamp': datetime.utcnow().isoformat(),
                'data': data,
            })
            if len(buf) > self._buffer_max:
                buf.pop(0)

            # Update subscription stats
            sub = self._subscriptions.get(stream_type)
            if sub:
                sub.message_count += 1
                sub.last_message_at = datetime.utcnow()

            # Dispatch to handlers
            handlers = list(self._handlers.get(stream_type, []))

        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Stream handler error for {stream_type}: {e}")

    # ─── Subscription Management ──────────────────────────────────────────────

    def subscribe_level_one_equity(self, symbols: List[str]) -> Dict[str, Any]:
        """Subscribe to level 1 equity quotes"""
        return self._subscribe(self.LEVEL_ONE_EQUITY, symbols)

    def subscribe_level_one_option(self, symbols: List[str]) -> Dict[str, Any]:
        """Subscribe to level 1 option quotes"""
        return self._subscribe(self.LEVEL_ONE_OPTION, symbols)

    def subscribe_level_one_futures(self, symbols: List[str]) -> Dict[str, Any]:
        """Subscribe to level 1 futures quotes"""
        return self._subscribe(self.LEVEL_ONE_FUTURES, symbols)

    def subscribe_level_one_forex(self, symbols: List[str]) -> Dict[str, Any]:
        """Subscribe to level 1 forex quotes"""
        return self._subscribe(self.LEVEL_ONE_FOREX, symbols)

    def subscribe_chart_equity(self, symbols: List[str]) -> Dict[str, Any]:
        """Subscribe to equity chart (OHLCV) data"""
        return self._subscribe(self.CHART_EQUITY, symbols)

    def subscribe_chart_futures(self, symbols: List[str]) -> Dict[str, Any]:
        """Subscribe to futures chart (OHLCV) data"""
        return self._subscribe(self.CHART_FUTURES, symbols)

    def subscribe_nyse_book(self, symbols: List[str]) -> Dict[str, Any]:
        """Subscribe to NYSE level 2 order book"""
        return self._subscribe(self.NYSE_BOOK, symbols)

    def subscribe_nasdaq_book(self, symbols: List[str]) -> Dict[str, Any]:
        """Subscribe to NASDAQ level 2 order book"""
        return self._subscribe(self.NASDAQ_BOOK, symbols)

    def subscribe_account_activity(self) -> Dict[str, Any]:
        """Subscribe to account activity notifications"""
        return self._subscribe(self.ACCOUNT_ACTIVITY, [])

    def _subscribe(self, stream_type: str, symbols: List[str]) -> Dict[str, Any]:
        """Internal subscription handler"""
        with self._lock:
            self._subscriptions[stream_type] = StreamSubscription(
                stream_type=stream_type,
                symbols=[s.upper() for s in symbols],
            )
        return {
            'success': True,
            'stream_type': stream_type,
            'symbols': [s.upper() for s in symbols],
            'message': f'Subscribed to {stream_type}',
        }

    def unsubscribe(self, stream_type: str) -> Dict[str, Any]:
        """Unsubscribe from a stream type"""
        with self._lock:
            if stream_type in self._subscriptions:
                del self._subscriptions[stream_type]
                return {'success': True, 'message': f'Unsubscribed from {stream_type}'}
            return {'success': False, 'error': f'Not subscribed to {stream_type}'}

    # ─── Stream Control ───────────────────────────────────────────────────────

    def start(self) -> Dict[str, Any]:
        """Start the streaming connection in a background thread"""
        if self._running:
            return {'success': False, 'error': 'Already streaming'}

        if not self._subscriptions:
            return {'success': False, 'error': 'No active subscriptions'}

        self._running = True
        self._stream_thread = threading.Thread(
            target=self._run_stream_loop,
            daemon=True,
            name=f'schwab-stream-{self.user_id}'
        )
        self._stream_thread.start()

        return {
            'success': True,
            'message': 'Streaming started',
            'subscriptions': list(self._subscriptions.keys()),
        }

    def stop(self) -> Dict[str, Any]:
        """Stop the streaming connection"""
        self._running = False
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=5)
        return {'success': True, 'message': 'Streaming stopped'}

    def _run_stream_loop(self):
        """Run the async streaming event loop in a background thread"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            if self.preferred_library == 'schwab_py' and SCHWAB_PY_STREAMING:
                loop.run_until_complete(self._run_schwab_py_stream())
            elif SCHWABDEV_STREAMING:
                self._run_schwabdev_stream()
            else:
                logger.error("No streaming library available")
        except Exception as e:
            logger.error(f"Streaming loop error: {e}")
        finally:
            self._running = False

    async def _run_schwab_py_stream(self):
        """Run streaming using schwab-py's StreamClient"""
        try:
            stream_client = self._get_schwab_py_client()
            if not stream_client:
                logger.error("Could not create schwab-py stream client")
                return

            await stream_client.login()

            # Register handlers and subscribe based on active subscriptions
            for stream_type, sub in self._subscriptions.items():
                await self._setup_schwab_py_subscription(stream_client, stream_type, sub)

            # Process messages
            while self._running:
                await stream_client.handle_message()

            await stream_client.logout()

        except Exception as e:
            logger.error(f"schwab-py streaming error: {e}")

    async def _setup_schwab_py_subscription(self, stream_client, stream_type: str,
                                             sub: StreamSubscription):
        """Set up a schwab-py stream subscription"""
        try:
            handler = lambda msg, st=stream_type: self._dispatch(st, msg)

            if stream_type == self.LEVEL_ONE_EQUITY:
                stream_client.add_level_one_equity_handler(handler)
                await stream_client.level_one_equity_subs(sub.symbols)

            elif stream_type == self.LEVEL_ONE_OPTION:
                stream_client.add_level_one_option_handler(handler)
                await stream_client.level_one_option_subs(sub.symbols)

            elif stream_type == self.LEVEL_ONE_FUTURES:
                stream_client.add_level_one_futures_handler(handler)
                await stream_client.level_one_futures_subs(sub.symbols)

            elif stream_type == self.LEVEL_ONE_FOREX:
                stream_client.add_level_one_forex_handler(handler)
                await stream_client.level_one_forex_subs(sub.symbols)

            elif stream_type == self.CHART_EQUITY:
                stream_client.add_chart_equity_handler(handler)
                await stream_client.chart_equity_subs(sub.symbols)

            elif stream_type == self.CHART_FUTURES:
                stream_client.add_chart_futures_handler(handler)
                await stream_client.chart_futures_subs(sub.symbols)

            elif stream_type == self.NYSE_BOOK:
                stream_client.add_nyse_book_handler(handler)
                await stream_client.nyse_book_subs(sub.symbols)

            elif stream_type == self.NASDAQ_BOOK:
                stream_client.add_nasdaq_book_handler(handler)
                await stream_client.nasdaq_book_subs(sub.symbols)

            elif stream_type == self.ACCOUNT_ACTIVITY:
                stream_client.add_account_activity_handler(handler)
                await stream_client.account_activity_sub()

        except Exception as e:
            logger.error(f"Failed to setup schwab-py subscription {stream_type}: {e}")

    def _run_schwabdev_stream(self):
        """Run streaming using schwabdev's Stream"""
        try:
            stream = self._get_schwabdev_client()
            if not stream:
                logger.error("Could not create schwabdev stream client")
                return

            # schwabdev uses a simpler callback approach
            def on_message(message):
                try:
                    if isinstance(message, str):
                        data = json.loads(message)
                    else:
                        data = message

                    # Route to appropriate handlers based on message content
                    self._route_schwabdev_message(data)
                except Exception as e:
                    logger.error(f"schwabdev message handling error: {e}")

            # Start stream with active subscriptions
            symbols = set()
            for sub in self._subscriptions.values():
                symbols.update(sub.symbols)

            if symbols:
                stream.start(on_message, list(symbols))

                # Keep running until stopped
                while self._running:
                    import time
                    time.sleep(0.1)

                stream.stop()

        except Exception as e:
            logger.error(f"schwabdev streaming error: {e}")

    def _route_schwabdev_message(self, data: Dict):
        """Route schwabdev messages to appropriate handlers"""
        # schwabdev messages include service/command fields
        service = ''
        if isinstance(data, dict):
            # Check for notify messages
            for notify in data.get('notify', []):
                self._dispatch(self.ACCOUNT_ACTIVITY, notify)

            # Check for data messages
            for response in data.get('data', []):
                service = response.get('service', '').upper()
                content = response.get('content', [])

                service_map = {
                    'LEVELONE_EQUITIES': self.LEVEL_ONE_EQUITY,
                    'LEVELONE_OPTIONS': self.LEVEL_ONE_OPTION,
                    'LEVELONE_FUTURES': self.LEVEL_ONE_FUTURES,
                    'LEVELONE_FOREX': self.LEVEL_ONE_FOREX,
                    'CHART_EQUITY': self.CHART_EQUITY,
                    'CHART_FUTURES': self.CHART_FUTURES,
                    'NYSE_BOOK': self.NYSE_BOOK,
                    'NASDAQ_BOOK': self.NASDAQ_BOOK,
                    'OPTIONS_BOOK': self.OPTIONS_BOOK,
                    'SCREENER_EQUITY': self.SCREENER_EQUITY,
                    'SCREENER_OPTION': self.SCREENER_OPTION,
                }

                stream_type = service_map.get(service)
                if stream_type:
                    for item in content:
                        self._dispatch(stream_type, item)

    # ─── Data Access ──────────────────────────────────────────────────────────

    def get_latest_data(self, stream_type: str, count: int = 10) -> Dict[str, Any]:
        """Get the latest buffered messages for a stream type"""
        with self._lock:
            buf = self._message_buffer.get(stream_type, [])
            data = buf[-count:] if count < len(buf) else list(buf)

        return {
            'success': True,
            'stream_type': stream_type,
            'messages': data,
            'total_buffered': len(self._message_buffer.get(stream_type, [])),
        }

    def get_status(self) -> Dict[str, Any]:
        """Get streaming service status"""
        with self._lock:
            subs = {}
            for stream_type, sub in self._subscriptions.items():
                subs[stream_type] = {
                    'symbols': sub.symbols,
                    'message_count': sub.message_count,
                    'last_message_at': sub.last_message_at.isoformat() if sub.last_message_at else None,
                    'created_at': sub.created_at.isoformat(),
                }

        return {
            'is_streaming': self._running,
            'preferred_library': self.preferred_library,
            'schwab_py_available': SCHWAB_PY_STREAMING,
            'schwabdev_available': SCHWABDEV_STREAMING,
            'subscriptions': subs,
            'user_id': self.user_id,
        }


# ─── Factory ──────────────────────────────────────────────────────────────────

# Keep one streaming service per user (singleton per user_id)
_streaming_services: Dict[int, SchwabStreamingService] = {}
_services_lock = threading.Lock()


def get_streaming_service(user_id: int,
                          preferred_library: str = 'schwabdev') -> SchwabStreamingService:
    """Get or create a streaming service for a user"""
    with _services_lock:
        if user_id not in _streaming_services:
            _streaming_services[user_id] = SchwabStreamingService(
                user_id=user_id,
                preferred_library=preferred_library,
            )
        return _streaming_services[user_id]


def get_streaming_info() -> Dict[str, Any]:
    """Get streaming service capabilities"""
    return {
        'schwab_py_streaming': SCHWAB_PY_STREAMING,
        'schwabdev_streaming': SCHWABDEV_STREAMING,
        'stream_types': {
            'level_one_equity': 'Real-time equity quotes (bid/ask/last/volume)',
            'level_one_option': 'Real-time option quotes with Greeks',
            'level_one_futures': 'Real-time futures quotes',
            'level_one_forex': 'Real-time forex quotes',
            'chart_equity': 'Minute-by-minute OHLCV equity charts',
            'chart_futures': 'Minute-by-minute OHLCV futures charts',
            'nyse_book': 'NYSE level 2 order book',
            'nasdaq_book': 'NASDAQ level 2 order book',
            'options_book': 'Options level 2 order book',
            'screener_equity': 'Real-time equity screener',
            'screener_option': 'Real-time option screener',
            'account_activity': 'Account activity notifications',
        },
    }
