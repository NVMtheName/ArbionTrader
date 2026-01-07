"""
Custom Exception Hierarchy for ArbionTrader
Provides structured error handling for trading operations
"""

import logging
from typing import Optional, Dict, Any
from flask import jsonify

logger = logging.getLogger(__name__)


# ============================================================================
# Base Exception Classes
# ============================================================================

class ArbionBaseException(Exception):
    """Base exception for all ArbionTrader errors"""

    def __init__(self, message: str, error_code: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None, status_code: int = 500):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            'error': self.error_code,
            'message': self.message,
            'details': self.details,
            'status_code': self.status_code
        }

    def to_json_response(self):
        """Return Flask JSON response"""
        return jsonify(self.to_dict()), self.status_code

    def log_error(self):
        """Log the error with appropriate level"""
        logger.error(f"{self.error_code}: {self.message}", extra={'details': self.details})


# ============================================================================
# Trading Operation Exceptions
# ============================================================================

class TradingException(ArbionBaseException):
    """Base exception for trading-related errors"""
    pass


class OrderExecutionError(TradingException):
    """Raised when order execution fails"""

    def __init__(self, message: str, symbol: Optional[str] = None,
                 order_type: Optional[str] = None, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code='ORDER_EXECUTION_ERROR',
            details={
                'symbol': symbol,
                'order_type': order_type,
                **(details or {})
            },
            status_code=400
        )


class OrderNotFoundError(TradingException):
    """Raised when order ID is not found"""

    def __init__(self, order_id: str):
        super().__init__(
            message=f"Order {order_id} not found",
            error_code='ORDER_NOT_FOUND',
            details={'order_id': order_id},
            status_code=404
        )


class OrderCancellationError(TradingException):
    """Raised when order cancellation fails"""

    def __init__(self, order_id: str, reason: Optional[str] = None):
        super().__init__(
            message=f"Failed to cancel order {order_id}: {reason or 'Unknown error'}",
            error_code='ORDER_CANCELLATION_ERROR',
            details={'order_id': order_id, 'reason': reason},
            status_code=400
        )


class InsufficientFundsError(TradingException):
    """Raised when user has insufficient funds for trade"""

    def __init__(self, required: float, available: float):
        super().__init__(
            message=f"Insufficient funds. Required: ${required:,.2f}, Available: ${available:,.2f}",
            error_code='INSUFFICIENT_FUNDS',
            details={'required': required, 'available': available},
            status_code=402
        )


class InvalidOrderError(TradingException):
    """Raised when order parameters are invalid"""

    def __init__(self, message: str, validation_errors: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code='INVALID_ORDER',
            details={'validation_errors': validation_errors or {}},
            status_code=400
        )


class MarketClosedError(TradingException):
    """Raised when attempting to trade outside market hours"""

    def __init__(self, symbol: str):
        super().__init__(
            message=f"Market is closed for {symbol}",
            error_code='MARKET_CLOSED',
            details={'symbol': symbol},
            status_code=400
        )


class SymbolNotFoundError(TradingException):
    """Raised when trading symbol is not found"""

    def __init__(self, symbol: str):
        super().__init__(
            message=f"Symbol {symbol} not found or not tradeable",
            error_code='SYMBOL_NOT_FOUND',
            details={'symbol': symbol},
            status_code=404
        )


# ============================================================================
# Risk Management Exceptions
# ============================================================================

class RiskManagementException(ArbionBaseException):
    """Base exception for risk management errors"""
    pass


class RiskLimitExceededError(RiskManagementException):
    """Raised when trade exceeds risk limits"""

    def __init__(self, limit_type: str, current_value: float,
                 limit_value: float, details: Optional[Dict] = None):
        super().__init__(
            message=f"{limit_type} limit exceeded. Current: ${current_value:,.2f}, Limit: ${limit_value:,.2f}",
            error_code='RISK_LIMIT_EXCEEDED',
            details={
                'limit_type': limit_type,
                'current_value': current_value,
                'limit_value': limit_value,
                **(details or {})
            },
            status_code=403
        )


class DailyTradingLimitExceededError(RiskManagementException):
    """Raised when daily trading limit is exceeded"""

    def __init__(self, used: float, limit: float):
        super().__init__(
            message=f"Daily trading limit exceeded. Used: ${used:,.2f}, Limit: ${limit:,.2f}",
            error_code='DAILY_LIMIT_EXCEEDED',
            details={'used': used, 'limit': limit},
            status_code=403
        )


class PositionSizeLimitError(RiskManagementException):
    """Raised when position size exceeds limits"""

    def __init__(self, symbol: str, requested_size: float, max_size: float):
        super().__init__(
            message=f"Position size for {symbol} exceeds limit. Requested: {requested_size}, Max: {max_size}",
            error_code='POSITION_SIZE_LIMIT',
            details={'symbol': symbol, 'requested_size': requested_size, 'max_size': max_size},
            status_code=403
        )


class StopLossNotSetError(RiskManagementException):
    """Raised when stop-loss is required but not provided"""

    def __init__(self, trade_id: int):
        super().__init__(
            message=f"Stop-loss is required for trade {trade_id}",
            error_code='STOP_LOSS_REQUIRED',
            details={'trade_id': trade_id},
            status_code=400
        )


class MarginCallError(RiskManagementException):
    """Raised when margin call is triggered"""

    def __init__(self, account_value: float, margin_requirement: float):
        super().__init__(
            message=f"Margin call: Account value ${account_value:,.2f} below requirement ${margin_requirement:,.2f}",
            error_code='MARGIN_CALL',
            details={'account_value': account_value, 'margin_requirement': margin_requirement},
            status_code=403
        )


# ============================================================================
# Market Data Exceptions
# ============================================================================

class MarketDataException(ArbionBaseException):
    """Base exception for market data errors"""
    pass


class DataNotAvailableError(MarketDataException):
    """Raised when market data is not available"""

    def __init__(self, symbol: str, data_type: Optional[str] = None):
        super().__init__(
            message=f"Market data not available for {symbol}" + (f" ({data_type})" if data_type else ""),
            error_code='DATA_NOT_AVAILABLE',
            details={'symbol': symbol, 'data_type': data_type},
            status_code=503
        )


class StaleDataError(MarketDataException):
    """Raised when market data is too old to be reliable"""

    def __init__(self, symbol: str, data_age_seconds: int, max_age_seconds: int):
        super().__init__(
            message=f"Market data for {symbol} is stale. Age: {data_age_seconds}s, Max: {max_age_seconds}s",
            error_code='STALE_DATA',
            details={'symbol': symbol, 'data_age_seconds': data_age_seconds, 'max_age_seconds': max_age_seconds},
            status_code=503
        )


class DataValidationError(MarketDataException):
    """Raised when market data fails validation"""

    def __init__(self, symbol: str, reason: str):
        super().__init__(
            message=f"Data validation failed for {symbol}: {reason}",
            error_code='DATA_VALIDATION_ERROR',
            details={'symbol': symbol, 'reason': reason},
            status_code=500
        )


# ============================================================================
# API Integration Exceptions
# ============================================================================

class APIException(ArbionBaseException):
    """Base exception for API integration errors"""
    pass


class BrokerAPIError(APIException):
    """Raised when broker API returns an error"""

    def __init__(self, provider: str, message: str, status_code: Optional[int] = None,
                 response_data: Optional[Dict] = None):
        super().__init__(
            message=f"{provider} API error: {message}",
            error_code='BROKER_API_ERROR',
            details={
                'provider': provider,
                'api_status_code': status_code,
                'response': response_data
            },
            status_code=status_code or 500
        )


class AuthenticationError(APIException):
    """Raised when API authentication fails"""

    def __init__(self, provider: str, reason: Optional[str] = None):
        super().__init__(
            message=f"Authentication failed for {provider}" + (f": {reason}" if reason else ""),
            error_code='AUTHENTICATION_ERROR',
            details={'provider': provider, 'reason': reason},
            status_code=401
        )


class TokenExpiredError(APIException):
    """Raised when API token has expired"""

    def __init__(self, provider: str):
        super().__init__(
            message=f"Access token expired for {provider}. Please re-authenticate.",
            error_code='TOKEN_EXPIRED',
            details={'provider': provider},
            status_code=401
        )


class RateLimitExceededError(APIException):
    """Raised when API rate limit is exceeded"""

    def __init__(self, provider: str, retry_after: Optional[int] = None):
        super().__init__(
            message=f"Rate limit exceeded for {provider}" + (f". Retry after {retry_after}s" if retry_after else ""),
            error_code='RATE_LIMIT_EXCEEDED',
            details={'provider': provider, 'retry_after': retry_after},
            status_code=429
        )


class APIConnectionError(APIException):
    """Raised when connection to API fails"""

    def __init__(self, provider: str, reason: Optional[str] = None):
        super().__init__(
            message=f"Failed to connect to {provider}" + (f": {reason}" if reason else ""),
            error_code='API_CONNECTION_ERROR',
            details={'provider': provider, 'reason': reason},
            status_code=503
        )


# ============================================================================
# Database & Configuration Exceptions
# ============================================================================

class ConfigurationError(ArbionBaseException):
    """Raised when configuration is invalid or missing"""

    def __init__(self, config_key: str, reason: Optional[str] = None):
        super().__init__(
            message=f"Configuration error for '{config_key}'" + (f": {reason}" if reason else ""),
            error_code='CONFIGURATION_ERROR',
            details={'config_key': config_key, 'reason': reason},
            status_code=500
        )


class DatabaseError(ArbionBaseException):
    """Raised when database operation fails"""

    def __init__(self, operation: str, reason: Optional[str] = None):
        super().__init__(
            message=f"Database error during {operation}" + (f": {reason}" if reason else ""),
            error_code='DATABASE_ERROR',
            details={'operation': operation, 'reason': reason},
            status_code=500
        )


# ============================================================================
# Strategy & AI Exceptions
# ============================================================================

class StrategyException(ArbionBaseException):
    """Base exception for trading strategy errors"""
    pass


class StrategyExecutionError(StrategyException):
    """Raised when strategy execution fails"""

    def __init__(self, strategy_name: str, reason: str):
        super().__init__(
            message=f"Strategy '{strategy_name}' execution failed: {reason}",
            error_code='STRATEGY_EXECUTION_ERROR',
            details={'strategy_name': strategy_name, 'reason': reason},
            status_code=500
        )


class AIModelError(StrategyException):
    """Raised when AI model prediction fails"""

    def __init__(self, model_name: str, reason: str):
        super().__init__(
            message=f"AI model '{model_name}' error: {reason}",
            error_code='AI_MODEL_ERROR',
            details={'model_name': model_name, 'reason': reason},
            status_code=500
        )


class PromptInjectionDetectedError(StrategyException):
    """Raised when prompt injection attempt is detected"""

    def __init__(self, detected_pattern: str):
        super().__init__(
            message="Potential prompt injection detected and blocked",
            error_code='PROMPT_INJECTION_DETECTED',
            details={'detected_pattern': detected_pattern},
            status_code=400
        )


# ============================================================================
# Utility Functions
# ============================================================================

def handle_exception(error: Exception, default_message: str = "An unexpected error occurred") -> tuple:
    """
    Global exception handler that returns appropriate JSON response

    Args:
        error: The exception to handle
        default_message: Default message for unknown exceptions

    Returns:
        Tuple of (response, status_code) for Flask
    """
    if isinstance(error, ArbionBaseException):
        error.log_error()
        return error.to_json_response()
    else:
        # Handle unknown exceptions
        logger.exception(f"Unhandled exception: {str(error)}")
        generic_error = ArbionBaseException(
            message=default_message,
            error_code='INTERNAL_SERVER_ERROR',
            details={'original_error': str(error)},
            status_code=500
        )
        return generic_error.to_json_response()


def raise_for_broker_response(provider: str, response, success_codes=(200, 201)):
    """
    Raise appropriate exception based on broker API response

    Args:
        provider: Broker name (schwab, coinbase, etc.)
        response: Response object from requests
        success_codes: Tuple of HTTP status codes considered successful
    """
    if response.status_code in success_codes:
        return

    error_data = None
    try:
        error_data = response.json()
    except:
        pass

    if response.status_code == 401:
        raise AuthenticationError(provider, "Invalid or expired credentials")
    elif response.status_code == 403:
        raise AuthenticationError(provider, "Insufficient permissions")
    elif response.status_code == 429:
        retry_after = response.headers.get('Retry-After')
        raise RateLimitExceededError(provider, int(retry_after) if retry_after else None)
    elif response.status_code == 404:
        raise BrokerAPIError(provider, "Resource not found", response.status_code, error_data)
    elif response.status_code >= 500:
        raise BrokerAPIError(provider, "Broker service unavailable", response.status_code, error_data)
    else:
        raise BrokerAPIError(provider, f"Request failed with status {response.status_code}",
                           response.status_code, error_data)
