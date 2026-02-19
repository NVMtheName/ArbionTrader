"""
Schwabdev Integration for Arbion Trading Platform
Comprehensive integration of Schwabdev library for seamless Schwab connection and account data management.

Features:
- Complete Schwab API integration using Schwabdev library
- Account data retrieval and management
- Real-time market data and quotes
- Order placement and management
- Portfolio and position tracking
- Enhanced error handling and connection management
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
import requests
from flask_login import current_user

# Import Schwabdev library
try:
    import schwabdev
    SCHWABDEV_AVAILABLE = True
except ImportError:
    SCHWABDEV_AVAILABLE = False
    schwabdev = None

logger = logging.getLogger(__name__)

@dataclass
class SchwabCredentials:
    """Schwab API credentials management"""
    app_key: str
    app_secret: str
    callback_url: str
    refresh_token: Optional[str] = None
    access_token: Optional[str] = None
    token_expiry: Optional[datetime] = None

@dataclass
class AccountInfo:
    """Schwab account information"""
    account_number: str
    account_type: str
    account_value: float
    available_funds: float
    buying_power: float
    day_trading_buying_power: float
    maintenance_requirement: float
    long_market_value: float
    short_market_value: float
    positions: List[Dict] = None

@dataclass
class MarketData:
    """Market data structure"""
    symbol: str
    price: float
    change: float
    change_percent: float
    volume: int
    high: float
    low: float
    open_price: float
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    timestamp: datetime

class SchwabdevManager:
    """Comprehensive Schwab integration using Schwabdev library"""
    
    def __init__(self, user_id: str = None):
        self.user_id = user_id
        self.credentials = None
        self.client = None
        self.last_token_refresh = None
        
        if not SCHWABDEV_AVAILABLE:
            raise ImportError("Schwabdev library not available. Install with: pip install schwabdev")
        
        # Load credentials
        self._load_credentials()
        
        # Initialize client if credentials are available
        if self.credentials and self.credentials.app_key:
            self._initialize_client()
        
        logger.info(f"SchwabdevManager initialized for user {user_id}")
    
    def _load_credentials(self):
        """Load Schwab credentials from environment and database"""
        try:
            # Load from environment variables
            app_key = os.environ.get("SCHWAB_APP_KEY")
            app_secret = os.environ.get("SCHWAB_APP_SECRET") 
            callback_url = os.environ.get("SCHWAB_CALLBACK_URL", "https://127.0.0.1")
            
            if not app_key or not app_secret:
                logger.warning("Schwab credentials not found in environment variables")
                return
            
            # Load tokens from database if user is available
            refresh_token = None
            access_token = None
            token_expiry = None
            
            if self.user_id:
                # Load user-specific tokens from database
                from models import User
                user = User.query.get(int(self.user_id))
                if user and hasattr(user, 'schwab_refresh_token'):
                    refresh_token = user.schwab_refresh_token
                    access_token = getattr(user, 'schwab_access_token', None)
                    token_expiry_str = getattr(user, 'schwab_token_expiry', None)
                    if token_expiry_str:
                        token_expiry = datetime.fromisoformat(token_expiry_str)
            
            self.credentials = SchwabCredentials(
                app_key=app_key,
                app_secret=app_secret,
                callback_url=callback_url,
                refresh_token=refresh_token,
                access_token=access_token,
                token_expiry=token_expiry
            )
            
            logger.info("Schwab credentials loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load Schwab credentials: {e}")
            self.credentials = None
    
    def _initialize_client(self):
        """Initialize Schwabdev client"""
        try:
            if not self.credentials:
                raise ValueError("Schwab credentials not available")
            
            # Create Schwabdev client
            self.client = schwabdev.Client(
                app_key=self.credentials.app_key,
                app_secret=self.credentials.app_secret,
                callback_url=self.credentials.callback_url,
                tokens_file=None,  # We'll manage tokens manually
                timeout=30
            )
            
            # Set tokens if available
            if self.credentials.refresh_token:
                self.client.update_tokens({
                    'refresh_token': self.credentials.refresh_token,
                    'access_token': self.credentials.access_token,
                    'expires_in': 1800,  # 30 minutes default
                    'token_type': 'Bearer'
                })
            
            logger.info("Schwabdev client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Schwabdev client: {e}")
            self.client = None
    
    def get_authorization_url(self) -> Dict[str, Any]:
        """Get Schwab OAuth authorization URL"""
        try:
            if not self.client:
                raise ValueError("Schwabdev client not initialized")
            
            auth_url = self.client.auth_url
            
            return {
                'success': True,
                'authorization_url': auth_url,
                'message': 'Visit this URL to authorize Schwab access'
            }
            
        except Exception as e:
            logger.error(f"Failed to get authorization URL: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def exchange_code_for_tokens(self, authorization_code: str) -> Dict[str, Any]:
        """Exchange authorization code for access tokens"""
        try:
            if not self.client:
                raise ValueError("Schwabdev client not initialized")
            
            # Get tokens using authorization code
            tokens = self.client.get_tokens(authorization_code)
            
            if tokens:
                # Update credentials
                self.credentials.refresh_token = tokens.get('refresh_token')
                self.credentials.access_token = tokens.get('access_token')
                self.credentials.token_expiry = datetime.utcnow() + timedelta(seconds=tokens.get('expires_in', 1800))
                
                # Save tokens to database
                self._save_tokens_to_database()
                
                logger.info("Schwab tokens obtained and saved successfully")
                
                return {
                    'success': True,
                    'message': 'Schwab authorization successful',
                    'token_expiry': self.credentials.token_expiry.isoformat()
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to obtain tokens from Schwab'
                }
                
        except Exception as e:
            logger.error(f"Failed to exchange code for tokens: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _save_tokens_to_database(self):
        """Save Schwab tokens to database"""
        try:
            if not self.user_id or not self.credentials:
                return
            
            from models import User
            from app import db
            
            user = User.query.get(int(self.user_id))
            if user:
                user.schwab_refresh_token = self.credentials.refresh_token
                user.schwab_access_token = self.credentials.access_token
                user.schwab_token_expiry = self.credentials.token_expiry.isoformat() if self.credentials.token_expiry else None
                
                db.session.commit()
                logger.info("Schwab tokens saved to database")
            
        except Exception as e:
            logger.error(f"Failed to save tokens to database: {e}")
    
    def refresh_access_token(self) -> Dict[str, Any]:
        """Refresh Schwab access token"""
        try:
            if not self.client or not self.credentials.refresh_token:
                raise ValueError("Cannot refresh token - client or refresh token not available")
            
            # Refresh tokens
            tokens = self.client.refresh_token()
            
            if tokens:
                # Update credentials
                self.credentials.access_token = tokens.get('access_token')
                self.credentials.token_expiry = datetime.utcnow() + timedelta(seconds=tokens.get('expires_in', 1800))
                
                # Save updated tokens
                self._save_tokens_to_database()
                
                self.last_token_refresh = datetime.utcnow()
                
                logger.info("Schwab access token refreshed successfully")
                
                return {
                    'success': True,
                    'message': 'Access token refreshed',
                    'token_expiry': self.credentials.token_expiry.isoformat()
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to refresh access token'
                }
                
        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token"""
        try:
            if not self.credentials or not self.credentials.access_token:
                return False
            
            # Check if token is close to expiry (refresh if less than 5 minutes remaining)
            if self.credentials.token_expiry:
                time_until_expiry = self.credentials.token_expiry - datetime.utcnow()
                if time_until_expiry.total_seconds() < 300:  # Less than 5 minutes
                    refresh_result = self.refresh_access_token()
                    return refresh_result.get('success', False)
            
            return True
            
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            return False
    
    def get_account_info(self, account_number: str = None) -> Dict[str, Any]:
        """Get comprehensive account information"""
        try:
            if not self.ensure_valid_token():
                return {
                    'success': False,
                    'error': 'Invalid or expired access token'
                }
            
            # Get account numbers if not provided
            if not account_number:
                accounts_response = self.client.get_account_numbers()
                if not accounts_response or not accounts_response.get('accounts'):
                    return {
                        'success': False,
                        'error': 'No accounts found'
                    }
                account_number = accounts_response['accounts'][0]['accountNumber']
            
            # Get detailed account information
            account_details = self.client.get_account(account_number, fields='positions')
            
            if not account_details:
                return {
                    'success': False,
                    'error': 'Failed to retrieve account details'
                }
            
            # Parse account information
            securities_account = account_details.get('securitiesAccount', {})
            initial_balances = securities_account.get('initialBalances', {})
            current_balances = securities_account.get('currentBalances', {})
            positions = securities_account.get('positions', [])
            
            account_info = AccountInfo(
                account_number=account_number,
                account_type=securities_account.get('type', 'Unknown'),
                account_value=current_balances.get('liquidationValue', 0.0),
                available_funds=current_balances.get('availableFunds', 0.0),
                buying_power=current_balances.get('buyingPower', 0.0),
                day_trading_buying_power=current_balances.get('dayTradingBuyingPower', 0.0),
                maintenance_requirement=current_balances.get('maintenanceRequirement', 0.0),
                long_market_value=current_balances.get('longMarketValue', 0.0),
                short_market_value=current_balances.get('shortMarketValue', 0.0),
                positions=self._parse_positions(positions)
            )
            
            return {
                'success': True,
                'account_info': account_info.__dict__,
                'raw_data': account_details
            }
            
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _parse_positions(self, positions: List[Dict]) -> List[Dict]:
        """Parse and format position data"""
        parsed_positions = []
        
        for position in positions:
            try:
                instrument = position.get('instrument', {})
                
                parsed_position = {
                    'symbol': instrument.get('symbol', 'Unknown'),
                    'cusip': instrument.get('cusip', ''),
                    'instrument_type': instrument.get('assetType', 'Unknown'),
                    'quantity': position.get('longQuantity', 0) - position.get('shortQuantity', 0),
                    'long_quantity': position.get('longQuantity', 0),
                    'short_quantity': position.get('shortQuantity', 0),
                    'average_price': position.get('averagePrice', 0.0),
                    'market_value': position.get('marketValue', 0.0),
                    'current_day_pnl': position.get('currentDayProfitLoss', 0.0),
                    'current_day_pnl_percent': position.get('currentDayProfitLossPercentage', 0.0),
                    'description': instrument.get('description', '')
                }
                
                parsed_positions.append(parsed_position)
                
            except Exception as e:
                logger.error(f"Failed to parse position: {e}")
                continue
        
        return parsed_positions
    
    def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get real-time market data for a symbol"""
        try:
            if not self.ensure_valid_token():
                return {
                    'success': False,
                    'error': 'Invalid or expired access token'
                }
            
            # Get quote data
            quote_response = self.client.get_quotes([symbol])
            
            if not quote_response or symbol not in quote_response:
                return {
                    'success': False,
                    'error': f'No market data found for symbol {symbol}'
                }
            
            quote_data = quote_response[symbol]
            
            # Parse market data
            market_data = MarketData(
                symbol=symbol,
                price=quote_data.get('lastPrice', 0.0),
                change=quote_data.get('netChange', 0.0),
                change_percent=quote_data.get('netPercentChangeInDouble', 0.0),
                volume=quote_data.get('totalVolume', 0),
                high=quote_data.get('highPrice', 0.0),
                low=quote_data.get('lowPrice', 0.0),
                open_price=quote_data.get('openPrice', 0.0),
                bid=quote_data.get('bidPrice', 0.0),
                ask=quote_data.get('askPrice', 0.0),
                bid_size=quote_data.get('bidSize', 0),
                ask_size=quote_data.get('askSize', 0),
                timestamp=datetime.utcnow()
            )
            
            return {
                'success': True,
                'market_data': market_data.__dict__,
                'raw_data': quote_data
            }
            
        except Exception as e:
            logger.error(f"Failed to get market data: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_multiple_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """Get market data for multiple symbols"""
        try:
            if not self.ensure_valid_token():
                return {
                    'success': False,
                    'error': 'Invalid or expired access token'
                }
            
            # Get quotes for all symbols
            quotes_response = self.client.get_quotes(symbols)
            
            if not quotes_response:
                return {
                    'success': False,
                    'error': 'Failed to retrieve quotes'
                }
            
            market_data_list = []
            
            for symbol in symbols:
                if symbol in quotes_response:
                    quote_data = quotes_response[symbol]
                    
                    market_data = MarketData(
                        symbol=symbol,
                        price=quote_data.get('lastPrice', 0.0),
                        change=quote_data.get('netChange', 0.0),
                        change_percent=quote_data.get('netPercentChangeInDouble', 0.0),
                        volume=quote_data.get('totalVolume', 0),
                        high=quote_data.get('highPrice', 0.0),
                        low=quote_data.get('lowPrice', 0.0),
                        open_price=quote_data.get('openPrice', 0.0),
                        bid=quote_data.get('bidPrice', 0.0),
                        ask=quote_data.get('askPrice', 0.0),
                        bid_size=quote_data.get('bidSize', 0),
                        ask_size=quote_data.get('askSize', 0),
                        timestamp=datetime.utcnow()
                    )
                    
                    market_data_list.append(market_data.__dict__)
            
            return {
                'success': True,
                'market_data': market_data_list,
                'symbols_requested': len(symbols),
                'symbols_received': len(market_data_list)
            }
            
        except Exception as e:
            logger.error(f"Failed to get multiple quotes: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def place_order(self, account_number: str, order_data: Dict) -> Dict[str, Any]:
        """Place a trading order"""
        try:
            if not self.ensure_valid_token():
                return {
                    'success': False,
                    'error': 'Invalid or expired access token'
                }
            
            # Validate order data
            required_fields = ['orderType', 'session', 'duration', 'orderStrategyType', 'orderLegCollection']
            for field in required_fields:
                if field not in order_data:
                    return {
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }
            
            # Place order
            order_response = self.client.place_order(account_number, order_data)
            
            if order_response:
                return {
                    'success': True,
                    'message': 'Order placed successfully',
                    'order_response': order_response
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to place order'
                }
                
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_orders(self, account_number: str, from_date: datetime = None, to_date: datetime = None) -> Dict[str, Any]:
        """Get order history"""
        try:
            if not self.ensure_valid_token():
                return {
                    'success': False,
                    'error': 'Invalid or expired access token'
                }
            
            # Set default date range if not provided
            if not to_date:
                to_date = datetime.utcnow()
            
            if not from_date:
                from_date = to_date - timedelta(days=30)  # Last 30 days
            
            # Get orders
            orders_response = self.client.get_orders(
                account_number,
                from_entered_time=from_date.strftime('%Y-%m-%d'),
                to_entered_time=to_date.strftime('%Y-%m-%d')
            )
            
            return {
                'success': True,
                'orders': orders_response or [],
                'from_date': from_date.isoformat(),
                'to_date': to_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cancel_order(self, account_number: str, order_id: str) -> Dict[str, Any]:
        """Cancel an existing order"""
        try:
            if not self.ensure_valid_token():
                return {
                    'success': False,
                    'error': 'Invalid or expired access token'
                }
            
            # Cancel order
            cancel_response = self.client.cancel_order(account_number, order_id)
            
            if cancel_response:
                return {
                    'success': True,
                    'message': f'Order {order_id} cancelled successfully'
                }
            else:
                return {
                    'success': False,
                    'error': f'Failed to cancel order {order_id}'
                }
                
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_watchlists(self, account_number: str) -> Dict[str, Any]:
        """Get user watchlists"""
        try:
            if not self.ensure_valid_token():
                return {
                    'success': False,
                    'error': 'Invalid or expired access token'
                }
            
            # Get watchlists
            watchlists_response = self.client.get_watchlists(account_number)
            
            return {
                'success': True,
                'watchlists': watchlists_response or []
            }
            
        except Exception as e:
            logger.error(f"Failed to get watchlists: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get comprehensive connection status"""
        return {
            'schwabdev_available': SCHWABDEV_AVAILABLE,
            'client_initialized': self.client is not None,
            'credentials_loaded': self.credentials is not None,
            'has_access_token': bool(self.credentials and self.credentials.access_token),
            'has_refresh_token': bool(self.credentials and self.credentials.refresh_token),
            'token_expiry': self.credentials.token_expiry.isoformat() if self.credentials and self.credentials.token_expiry else None,
            'last_token_refresh': self.last_token_refresh.isoformat() if self.last_token_refresh else None,
            'user_id': self.user_id
        }

# Factory functions for easy integration
def create_schwabdev_manager(user_id: str = None) -> SchwabdevManager:
    """Create Schwabdev manager instance"""
    return SchwabdevManager(user_id=user_id)

def get_schwabdev_info() -> Dict[str, Any]:
    """Get information about Schwabdev integration"""
    return {
        'library_available': SCHWABDEV_AVAILABLE,
        'library_version': getattr(schwabdev, '__version__', '2.5.0') if SCHWABDEV_AVAILABLE else None,
        'description': 'Comprehensive Schwab API integration using Schwabdev library',
        'features': [
            'OAuth 2.0 authentication with automatic token refresh',
            'Real-time account data and positions',
            'Market data and quotes retrieval',
            'Order placement and management',
            'Order history and tracking',
            'Watchlist management',
            'Portfolio and balance information',
            'Comprehensive error handling and logging'
        ],
        'supported_operations': [
            'get_account_info',
            'get_market_data',
            'get_multiple_quotes',
            'place_order',
            'get_orders',
            'cancel_order',
            'get_watchlists',
            'refresh_access_token'
        ]
    }