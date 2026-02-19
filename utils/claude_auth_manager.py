"""
Claude/Anthropic Authentication Manager for Arbion Trading Platform
Enhanced authentication system for reliable Claude API connections with retry logic,
rate limiting, error handling, and connection monitoring.
"""

import os
import time
import logging
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from anthropic import Anthropic, AsyncAnthropic
from anthropic import (
    APIError,
    APIConnectionError,
    RateLimitError,
    AuthenticationError
)
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class ClaudeAPICredentials:
    """Secure Claude API credentials management"""
    api_key: str

    def __post_init__(self):
        """Validate credentials after initialization"""
        if not self.api_key:
            raise ValueError("Claude API key is required")

        if not self.api_key.startswith('sk-ant-'):
            raise ValueError(
                "Invalid Claude API key format. Keys should start with 'sk-ant-'"
            )


@dataclass
class ClaudeConnectionStatus:
    """Track Claude connection status"""
    is_connected: bool = False
    last_test_time: Optional[datetime] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    rate_limit_reset: Optional[datetime] = None
    request_count: int = 0
    success_rate: float = 0.0


class ClaudeRateLimitManager:
    """Manage Claude API rate limits and request throttling"""

    def __init__(self):
        self.request_times: List[datetime] = []
        self.rate_limits = {
            'requests_per_minute': 1000,    # Anthropic tier-1 limit
            'tokens_per_minute': 80000,
            'requests_per_day': 10000
        }
        self.current_usage = {
            'requests_this_minute': 0,
            'tokens_this_minute': 0,
            'requests_today': 0
        }

    def can_make_request(self) -> bool:
        """Check if request can be made without exceeding rate limits"""
        now = datetime.utcnow()

        # Clean old requests (older than 1 minute)
        self.request_times = [
            req_time for req_time in self.request_times
            if now - req_time < timedelta(minutes=1)
        ]

        return len(self.request_times) < self.rate_limits['requests_per_minute']

    def record_request(self, tokens_used: int = 0):
        """Record a new API request"""
        now = datetime.utcnow()
        self.request_times.append(now)
        self.current_usage['requests_this_minute'] += 1
        self.current_usage['tokens_this_minute'] += tokens_used

    def get_wait_time(self) -> float:
        """Calculate recommended wait time before next request"""
        if self.can_make_request():
            return 0.0

        if self.request_times:
            oldest_request = min(self.request_times)
            wait_until = oldest_request + timedelta(minutes=1)
            wait_seconds = (wait_until - datetime.utcnow()).total_seconds()
            return max(wait_seconds, 0.1)

        return 1.0


class ClaudeRetryManager:
    """Advanced retry logic for Claude API calls"""

    def __init__(self):
        self.retry_config = {
            'max_retries': 5,
            'base_delay': 1.0,
            'max_delay': 60.0,
            'exponential_base': 2.0,
            'jitter': True
        }

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt with exponential backoff"""
        delay = self.retry_config['base_delay'] * (
            self.retry_config['exponential_base'] ** attempt
        )
        delay = min(delay, self.retry_config['max_delay'])

        if self.retry_config['jitter']:
            import random
            delay *= (0.5 + random.random() * 0.5)

        return delay

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if request should be retried"""
        if attempt >= self.retry_config['max_retries']:
            return False

        retry_errors = (
            APIConnectionError,
            RateLimitError,
            APIError
        )

        if isinstance(error, retry_errors):
            return True

        # Don't retry authentication errors
        if isinstance(error, AuthenticationError):
            return False

        # Retry on 5xx server errors
        if hasattr(error, 'status_code'):
            return 500 <= error.status_code < 600

        return False


def claude_retry_with_backoff(retry_manager: ClaudeRetryManager = None):
    """Decorator for automatic retry with exponential backoff"""
    if retry_manager is None:
        retry_manager = ClaudeRetryManager()

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(retry_manager.retry_config['max_retries'] + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not retry_manager.should_retry(e, attempt):
                        break

                    if attempt < retry_manager.retry_config['max_retries']:
                        delay = retry_manager.calculate_delay(attempt)
                        logger.warning(
                            f"Claude API call failed (attempt {attempt + 1}), "
                            f"retrying in {delay:.2f}s: {str(e)}"
                        )
                        await asyncio.sleep(delay)

            logger.error(f"Claude API call failed after all retries: {str(last_exception)}")
            raise last_exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(retry_manager.retry_config['max_retries'] + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if not retry_manager.should_retry(e, attempt):
                        break

                    if attempt < retry_manager.retry_config['max_retries']:
                        delay = retry_manager.calculate_delay(attempt)
                        logger.warning(
                            f"Claude API call failed (attempt {attempt + 1}), "
                            f"retrying in {delay:.2f}s: {str(e)}"
                        )
                        time.sleep(delay)

            raise last_exception

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


class ClaudeAuthManager:
    """Comprehensive Claude authentication and connection manager"""

    def __init__(self, user_id: str = None):
        self.user_id = user_id
        self.credentials = self._load_credentials()
        self.connection_status = ClaudeConnectionStatus()
        self.rate_limit_manager = ClaudeRateLimitManager()
        self.retry_manager = ClaudeRetryManager()

        # Initialize clients
        self.sync_client = None
        self.async_client = None

        # Connection monitoring
        self.last_health_check = None
        self.health_check_interval = timedelta(minutes=5)

        logger.info(f"Claude Auth Manager initialized for user {user_id}")

    def _load_credentials(self) -> ClaudeAPICredentials:
        """Load and validate Claude credentials from database or environment"""
        api_key = None

        # Priority 1: Load from database (per-user)
        if self.user_id:
            try:
                from models import APICredential
                from utils.encryption import decrypt_credentials

                credential = APICredential.query.filter_by(
                    user_id=self.user_id,
                    provider='claude',
                    is_active=True
                ).first()

                if credential:
                    creds = decrypt_credentials(credential.encrypted_credentials)
                    api_key = creds.get('api_key')
            except Exception as e:
                logger.error(f"Failed to load Claude key from DB for user {self.user_id}: {e}")

        # Priority 2: Environment variable fallback
        if not api_key:
            api_key = os.environ.get("ANTHROPIC_API_KEY")

        if not api_key:
            alt_keys = ["CLAUDE_API_KEY", "CLAUDE_KEY"]
            for alt_key in alt_keys:
                api_key = os.environ.get(alt_key)
                if api_key:
                    break

        if not api_key:
            raise ValueError(
                "Claude API key not found. Save it in API Settings or "
                "set ANTHROPIC_API_KEY environment variable. "
                "Get your API key from https://console.anthropic.com/"
            )

        return ClaudeAPICredentials(api_key=api_key.strip())

    def _create_client_kwargs(self) -> Dict[str, Any]:
        """Create standardized client configuration"""
        return {
            "api_key": self.credentials.api_key,
            "timeout": 120.0,   # Claude can take longer for complex analysis
            "max_retries": 0    # We handle retries manually
        }

    def get_sync_client(self) -> Anthropic:
        """Get authenticated synchronous Claude client"""
        if self.sync_client is None:
            try:
                self.sync_client = Anthropic(**self._create_client_kwargs())
                logger.info("Synchronous Claude client created successfully")
            except Exception as e:
                logger.error(f"Failed to create sync Claude client: {e}")
                raise

        return self.sync_client

    def get_async_client(self) -> AsyncAnthropic:
        """Get authenticated asynchronous Claude client"""
        if self.async_client is None:
            try:
                self.async_client = AsyncAnthropic(**self._create_client_kwargs())
                logger.info("Asynchronous Claude client created successfully")
            except Exception as e:
                logger.error(f"Failed to create async Claude client: {e}")
                raise

        return self.async_client

    @claude_retry_with_backoff()
    async def test_connection(self) -> Dict[str, Any]:
        """Test Claude API connection with authentication"""
        try:
            client = self.get_async_client()

            response = await client.messages.create(
                model="claude-haiku-4-20250414",
                max_tokens=16,
                messages=[{"role": "user", "content": "Test connection. Reply OK."}]
            )

            self.connection_status.is_connected = True
            self.connection_status.last_test_time = datetime.utcnow()
            self.connection_status.last_error = None
            self.connection_status.consecutive_failures = 0

            logger.info("Claude API connection test successful")

            return {
                'success': True,
                'message': 'Claude API connection successful',
                'model_used': 'claude-haiku-4-20250414',
                'response_id': response.id,
                'timestamp': datetime.utcnow().isoformat()
            }

        except AuthenticationError as e:
            error_msg = f"Authentication failed: {str(e)}"
            self._update_connection_error(error_msg)
            logger.error(error_msg)

            return {
                'success': False,
                'error': 'authentication_failed',
                'message': error_msg,
                'solution': 'Check your Claude API key at https://console.anthropic.com/'
            }

        except RateLimitError as e:
            error_msg = f"Rate limit exceeded: {str(e)}"
            self._update_connection_error(error_msg)

            return {
                'success': False,
                'error': 'rate_limit_exceeded',
                'message': error_msg,
                'solution': 'Wait before making more requests or upgrade your plan'
            }

        except APIConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            self._update_connection_error(error_msg)

            return {
                'success': False,
                'error': 'connection_failed',
                'message': error_msg,
                'solution': 'Check your internet connection and try again'
            }

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self._update_connection_error(error_msg)

            return {
                'success': False,
                'error': 'unknown_error',
                'message': error_msg,
                'solution': 'Contact support if this persists'
            }

    def _update_connection_error(self, error_msg: str):
        """Update connection status with error information"""
        self.connection_status.is_connected = False
        self.connection_status.last_error = error_msg
        self.connection_status.consecutive_failures += 1
        self.connection_status.last_test_time = datetime.utcnow()

    async def ensure_connection(self) -> bool:
        """Ensure Claude connection is healthy, test if needed"""
        now = datetime.utcnow()

        needs_test = (
            not self.connection_status.is_connected or
            self.last_health_check is None or
            (now - self.last_health_check) > self.health_check_interval or
            self.connection_status.consecutive_failures > 0
        )

        if needs_test:
            logger.info("Testing Claude connection health...")
            result = await self.test_connection()
            self.last_health_check = now
            return result.get('success', False)

        return self.connection_status.is_connected

    @claude_retry_with_backoff()
    async def make_message(self, **kwargs) -> Any:
        """Make authenticated message with rate limiting and retry"""
        if not await self.ensure_connection():
            raise APIConnectionError("Claude connection is not healthy")

        if not self.rate_limit_manager.can_make_request():
            wait_time = self.rate_limit_manager.get_wait_time()
            logger.info(f"Rate limit reached, waiting {wait_time:.2f} seconds")
            await asyncio.sleep(wait_time)

        try:
            client = self.get_async_client()
            self.rate_limit_manager.record_request()
            response = await client.messages.create(**kwargs)
            self.connection_status.request_count += 1
            return response
        except Exception as e:
            self._update_connection_error(str(e))
            raise

    def get_connection_info(self) -> Dict[str, Any]:
        """Get comprehensive connection status information"""
        return {
            'user_id': self.user_id,
            'provider': 'claude',
            'connection_status': {
                'is_connected': self.connection_status.is_connected,
                'last_test_time': self.connection_status.last_test_time.isoformat() if self.connection_status.last_test_time else None,
                'last_error': self.connection_status.last_error,
                'consecutive_failures': self.connection_status.consecutive_failures,
                'request_count': self.connection_status.request_count,
                'success_rate': self.connection_status.success_rate
            },
            'rate_limits': {
                'requests_per_minute': self.rate_limit_manager.rate_limits['requests_per_minute'],
                'current_requests': len(self.rate_limit_manager.request_times),
                'can_make_request': self.rate_limit_manager.can_make_request(),
                'wait_time': self.rate_limit_manager.get_wait_time()
            },
            'credentials': {
                'api_key_present': bool(self.credentials.api_key),
                'api_key_format_valid': self.credentials.api_key.startswith('sk-ant-') if self.credentials.api_key else False,
            },
            'client_status': {
                'sync_client_ready': self.sync_client is not None,
                'async_client_ready': self.async_client is not None
            }
        }

    async def refresh_connection(self):
        """Force refresh Claude connection"""
        logger.info("Refreshing Claude connection...")

        self.sync_client = None
        self.async_client = None
        self.connection_status = ClaudeConnectionStatus()

        result = await self.test_connection()

        if result.get('success'):
            logger.info("Claude connection refreshed successfully")
        else:
            logger.error(f"Failed to refresh Claude connection: {result.get('message')}")

        return result

    def validate_api_key_format(self, api_key: str) -> Dict[str, Any]:
        """Validate Claude API key format"""
        if not api_key:
            return {
                'valid': False,
                'error': 'API key is empty',
                'format': 'unknown'
            }

        if api_key.startswith('sk-ant-'):
            return {
                'valid': True,
                'format': 'anthropic_key',
                'description': 'Anthropic API key'
            }
        else:
            return {
                'valid': False,
                'error': 'Invalid API key format',
                'format': 'invalid',
                'expected': "Keys should start with 'sk-ant-'"
            }


# Factory functions
def create_claude_auth_manager(user_id: str = None) -> ClaudeAuthManager:
    """Create Claude authentication manager"""
    return ClaudeAuthManager(user_id=user_id)


async def test_claude_connection(user_id: str = None) -> Dict[str, Any]:
    """Quick test of Claude connection"""
    auth_manager = create_claude_auth_manager(user_id)
    return await auth_manager.test_connection()


def validate_claude_setup() -> Dict[str, Any]:
    """Validate Claude setup and configuration"""
    try:
        auth_manager = create_claude_auth_manager()
        info = auth_manager.get_connection_info()

        validation_result = {
            'setup_valid': True,
            'issues': [],
            'recommendations': []
        }

        if not info['credentials']['api_key_present']:
            validation_result['setup_valid'] = False
            validation_result['issues'].append('ANTHROPIC_API_KEY environment variable not set')
            validation_result['recommendations'].append('Set ANTHROPIC_API_KEY in your environment or save via API Settings')

        elif not info['credentials']['api_key_format_valid']:
            validation_result['setup_valid'] = False
            validation_result['issues'].append('Invalid API key format')
            validation_result['recommendations'].append("API key should start with 'sk-ant-'")

        if not info['connection_status']['is_connected']:
            validation_result['issues'].append('Not connected to Claude API')
            validation_result['recommendations'].append('Test connection to verify API key')

        return validation_result

    except Exception as e:
        return {
            'setup_valid': False,
            'issues': [f'Setup validation failed: {str(e)}'],
            'recommendations': ['Check Claude API key configuration']
        }
