"""
OpenAI Authentication Manager for Arbion Trading Platform
Enhanced authentication system for reliable OpenAI API connections with retry logic,
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
from openai import OpenAI, AsyncOpenAI
from openai._exceptions import APIError, APIConnectionError, RateLimitError, AuthenticationError
import requests
from functools import wraps

logger = logging.getLogger(__name__)

@dataclass
class APICredentials:
    """Secure API credentials management"""
    api_key: str
    organization_id: Optional[str] = None
    project_id: Optional[str] = None
    base_url: Optional[str] = None
    
    def __post_init__(self):
        """Validate credentials after initialization"""
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        if not self.api_key.startswith(('sk-', 'sk-proj-')):
            raise ValueError("Invalid OpenAI API key format")

@dataclass
class ConnectionStatus:
    """Track OpenAI connection status"""
    is_connected: bool = False
    last_test_time: Optional[datetime] = None
    last_error: Optional[str] = None
    consecutive_failures: int = 0
    rate_limit_reset: Optional[datetime] = None
    request_count: int = 0
    success_rate: float = 0.0

class RateLimitManager:
    """Manage OpenAI API rate limits and request throttling"""
    
    def __init__(self):
        self.request_times: List[datetime] = []
        self.rate_limits = {
            'requests_per_minute': 3500,  # Conservative limit
            'tokens_per_minute': 150000,
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
        
        # Check current minute limits
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
        
        # If rate limited, wait until oldest request is > 1 minute old
        if self.request_times:
            oldest_request = min(self.request_times)
            wait_until = oldest_request + timedelta(minutes=1)
            wait_seconds = (wait_until - datetime.utcnow()).total_seconds()
            return max(wait_seconds, 0.1)
        
        return 1.0  # Default wait time

class RetryManager:
    """Advanced retry logic for OpenAI API calls"""
    
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
        
        # Cap at max delay
        delay = min(delay, self.retry_config['max_delay'])
        
        # Add jitter to prevent thundering herd
        if self.retry_config['jitter']:
            import random
            delay *= (0.5 + random.random() * 0.5)
        
        return delay
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Determine if request should be retried"""
        if attempt >= self.retry_config['max_retries']:
            return False
        
        # Retry on specific error types
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

def retry_with_backoff(retry_manager: RetryManager = None):
    """Decorator for automatic retry with exponential backoff"""
    if retry_manager is None:
        retry_manager = RetryManager()
    
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
                            f"OpenAI API call failed (attempt {attempt + 1}), "
                            f"retrying in {delay:.2f}s: {str(e)}"
                        )
                        await asyncio.sleep(delay)
            
            # If we get here, all retries failed
            logger.error(f"OpenAI API call failed after all retries: {str(last_exception)}")
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
                            f"OpenAI API call failed (attempt {attempt + 1}), "
                            f"retrying in {delay:.2f}s: {str(e)}"
                        )
                        time.sleep(delay)
            
            raise last_exception
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

class OpenAIAuthManager:
    """Comprehensive OpenAI authentication and connection manager"""
    
    def __init__(self, user_id: str = None):
        self.user_id = user_id
        self.credentials = self._load_credentials()
        self.connection_status = ConnectionStatus()
        self.rate_limit_manager = RateLimitManager()
        self.retry_manager = RetryManager()
        
        # Initialize clients
        self.sync_client = None
        self.async_client = None
        
        # Connection monitoring
        self.last_health_check = None
        self.health_check_interval = timedelta(minutes=5)
        
        logger.info(f"OpenAI Auth Manager initialized for user {user_id}")
    
    def _load_credentials(self) -> APICredentials:
        """Load and validate OpenAI credentials"""
        api_key = os.environ.get("OPENAI_API_KEY")
        
        if not api_key:
            # Try alternative environment variables
            alt_keys = ["OPENAI_SECRET_KEY", "OPENAI_TOKEN", "OPENAI_KEY"]
            for alt_key in alt_keys:
                api_key = os.environ.get(alt_key)
                if api_key:
                    break
        
        if not api_key:
            raise ValueError(
                "OpenAI API key not found. Please set OPENAI_API_KEY environment variable. "
                "Get your API key from https://platform.openai.com/api-keys"
            )
        
        return APICredentials(
            api_key=api_key.strip(),
            organization_id=os.environ.get("OPENAI_ORG_ID"),
            project_id=os.environ.get("OPENAI_PROJECT_ID"),
            base_url=os.environ.get("OPENAI_BASE_URL")
        )
    
    def _create_client_kwargs(self) -> Dict[str, Any]:
        """Create standardized client configuration"""
        kwargs = {
            "api_key": self.credentials.api_key,
            "timeout": 60.0,  # Increased timeout for trading operations
            "max_retries": 0  # We handle retries manually
        }
        
        if self.credentials.organization_id:
            kwargs["organization"] = self.credentials.organization_id
        
        if self.credentials.project_id:
            kwargs["project"] = self.credentials.project_id
        
        if self.credentials.base_url:
            kwargs["base_url"] = self.credentials.base_url
        
        return kwargs
    
    def get_sync_client(self) -> OpenAI:
        """Get authenticated synchronous OpenAI client"""
        if self.sync_client is None:
            try:
                self.sync_client = OpenAI(**self._create_client_kwargs())
                logger.info("Synchronous OpenAI client created successfully")
            except Exception as e:
                logger.error(f"Failed to create sync OpenAI client: {e}")
                raise
        
        return self.sync_client
    
    def get_async_client(self) -> AsyncOpenAI:
        """Get authenticated asynchronous OpenAI client"""
        if self.async_client is None:
            try:
                self.async_client = AsyncOpenAI(**self._create_client_kwargs())
                logger.info("Asynchronous OpenAI client created successfully")
            except Exception as e:
                logger.error(f"Failed to create async OpenAI client: {e}")
                raise
        
        return self.async_client
    
    @retry_with_backoff()
    async def test_connection(self) -> Dict[str, Any]:
        """Test OpenAI API connection with authentication"""
        try:
            client = self.get_async_client()
            
            # Make a simple API call to test connection
            response = await client.chat.completions.create(
                model="gpt-5.2-mini",
                messages=[{"role": "user", "content": "Test connection"}],
                max_tokens=5
            )
            
            # Update connection status
            self.connection_status.is_connected = True
            self.connection_status.last_test_time = datetime.utcnow()
            self.connection_status.last_error = None
            self.connection_status.consecutive_failures = 0
            
            logger.info("OpenAI API connection test successful")
            
            return {
                'success': True,
                'message': 'OpenAI API connection successful',
                'model_used': 'gpt-3.5-turbo',
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
                'solution': 'Check your OpenAI API key at https://platform.openai.com/api-keys'
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
        """Ensure OpenAI connection is healthy, test if needed"""
        now = datetime.utcnow()
        
        # Check if we need to test connection
        needs_test = (
            not self.connection_status.is_connected or
            self.last_health_check is None or
            (now - self.last_health_check) > self.health_check_interval or
            self.connection_status.consecutive_failures > 0
        )
        
        if needs_test:
            logger.info("Testing OpenAI connection health...")
            result = await self.test_connection()
            self.last_health_check = now
            return result.get('success', False)
        
        return self.connection_status.is_connected
    
    @retry_with_backoff()
    async def make_chat_completion(self, **kwargs) -> Any:
        """Make authenticated chat completion with rate limiting and retry"""
        # Ensure connection is healthy
        if not await self.ensure_connection():
            raise APIConnectionError("OpenAI connection is not healthy")
        
        # Check rate limits
        if not self.rate_limit_manager.can_make_request():
            wait_time = self.rate_limit_manager.get_wait_time()
            logger.info(f"Rate limit reached, waiting {wait_time:.2f} seconds")
            await asyncio.sleep(wait_time)
        
        try:
            client = self.get_async_client()
            
            # Record the request
            self.rate_limit_manager.record_request()
            
            # Make the API call
            response = await client.chat.completions.create(**kwargs)
            
            # Update success metrics
            self.connection_status.request_count += 1
            
            return response
            
        except Exception as e:
            self._update_connection_error(str(e))
            raise
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get comprehensive connection status information"""
        return {
            'user_id': self.user_id,
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
                'api_key_format_valid': self.credentials.api_key.startswith(('sk-', 'sk-proj-')) if self.credentials.api_key else False,
                'organization_id_present': bool(self.credentials.organization_id),
                'project_id_present': bool(self.credentials.project_id)
            },
            'client_status': {
                'sync_client_ready': self.sync_client is not None,
                'async_client_ready': self.async_client is not None
            }
        }
    
    async def refresh_connection(self):
        """Force refresh OpenAI connection"""
        logger.info("Refreshing OpenAI connection...")
        
        # Reset clients
        self.sync_client = None
        self.async_client = None
        
        # Reset connection status
        self.connection_status = ConnectionStatus()
        
        # Test new connection
        result = await self.test_connection()
        
        if result.get('success'):
            logger.info("OpenAI connection refreshed successfully")
        else:
            logger.error(f"Failed to refresh OpenAI connection: {result.get('message')}")
        
        return result
    
    def validate_api_key_format(self, api_key: str) -> Dict[str, Any]:
        """Validate OpenAI API key format"""
        if not api_key:
            return {
                'valid': False,
                'error': 'API key is empty',
                'format': 'unknown'
            }
        
        if api_key.startswith('sk-proj-'):
            return {
                'valid': True,
                'format': 'project_key',
                'description': 'Project-scoped API key'
            }
        elif api_key.startswith('sk-'):
            return {
                'valid': True,
                'format': 'standard_key',
                'description': 'Standard API key'
            }
        else:
            return {
                'valid': False,
                'error': 'Invalid API key format',
                'format': 'invalid',
                'expected': 'Keys should start with sk- or sk-proj-'
            }

# Factory functions for easy integration
def create_auth_manager(user_id: str = None) -> OpenAIAuthManager:
    """Create OpenAI authentication manager"""
    return OpenAIAuthManager(user_id=user_id)

async def test_openai_connection(user_id: str = None) -> Dict[str, Any]:
    """Quick test of OpenAI connection"""
    auth_manager = create_auth_manager(user_id)
    return await auth_manager.test_connection()

def validate_openai_setup() -> Dict[str, Any]:
    """Validate OpenAI setup and configuration"""
    try:
        auth_manager = create_auth_manager()
        info = auth_manager.get_connection_info()
        
        validation_result = {
            'setup_valid': True,
            'issues': [],
            'recommendations': []
        }
        
        # Check API key
        if not info['credentials']['api_key_present']:
            validation_result['setup_valid'] = False
            validation_result['issues'].append('OPENAI_API_KEY environment variable not set')
            validation_result['recommendations'].append('Set OPENAI_API_KEY in your environment')
        
        elif not info['credentials']['api_key_format_valid']:
            validation_result['setup_valid'] = False
            validation_result['issues'].append('Invalid API key format')
            validation_result['recommendations'].append('API key should start with sk- or sk-proj-')
        
        # Check connection
        if not info['connection_status']['is_connected']:
            validation_result['issues'].append('Not connected to OpenAI API')
            validation_result['recommendations'].append('Test connection to verify API key')
        
        return validation_result
        
    except Exception as e:
        return {
            'setup_valid': False,
            'issues': [f'Setup validation failed: {str(e)}'],
            'recommendations': ['Check OpenAI API key configuration']
        }