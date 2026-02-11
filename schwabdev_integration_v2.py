"""
Schwabdev Integration v2 for Arbion Trading Platform
=====================================================
FIXES from v1:
- Bug #1: Token loading now reads from APICredential table (not nonexistent User.schwab_* fields)
- Bug #2: Unified auth path - uses SchwabOAuth for token refresh (single source of truth)
- Bug #3: Proper schwabdev.Client initialization with correct token format
- Added: Direct REST API fallback when schwabdev library methods don't work
- Added: Comprehensive connection diagnostics

Features:
- Complete Schwab API integration using schwabdev library + direct REST fallback
- Reads/writes tokens exclusively through APICredential table via encryption module
- Automatic token refresh with 5-minute buffer
- Account data, market data, order management
- Enhanced error handling with detailed diagnostics
"""

import os
import json
import logging
import base64
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

# Import Schwabdev library
try:
    import schwabdev
    SCHWABDEV_AVAILABLE = True
except ImportError:
    SCHWABDEV_AVAILABLE = False
    schwabdev = None

logger = logging.getLogger(__name__)


# ─── Data Classes ───────────────────────────────────────────────────────────────

@dataclass
class SchwabCredentials:
    """Schwab API credentials - loaded from APICredential table"""
    app_key: str
    app_secret: str
    callback_url: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None


@dataclass
class AccountInfo:
    """Schwab account information"""
    account_number: str
    account_hash: str
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


# ─── Main Manager Class ────────────────────────────────────────────────────────

class SchwabdevManager:
    """
    Comprehensive Schwab integration - UNIFIED token management.
    
    Token flow:
    1. Client credentials (app_key, app_secret) come from OAuthClientCredential table OR env vars
    2. User tokens (access_token, refresh_token) come from APICredential table (encrypted)
    3. Token refresh uses SchwabOAuth.refresh_token() and writes back to APICredential
    4. schwabdev.Client is used for market data/orders; direct REST as fallback
    """

    # Schwab API base URLs
    TRADER_API_BASE = "https://api.schwabapi.com/trader/v1"
    MARKET_DATA_BASE = "https://api.schwabapi.com/marketdata/v1"
    TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"

    def __init__(self, user_id: str = None):
        self.user_id = user_id
        self.credentials = None
        self.client = None
        self.last_token_refresh = None
        self._account_hashes = {}  # Cache: account_number -> account_hash

        # Load credentials from the CORRECT sources
        self._load_credentials()

        # Initialize schwabdev client if possible
        if self.credentials and self.credentials.app_key:
            self._initialize_client()

        logger.info(f"SchwabdevManager v2 initialized for user {user_id} | "
                     f"has_token={bool(self.credentials and self.credentials.access_token)}")

    # ─── Credential Loading (THE FIX) ───────────────────────────────────────────

    def _load_credentials(self):
        """
        Load credentials from the CORRECT sources:
        - App key/secret: OAuthClientCredential table first, then env vars
        - Access/refresh tokens: APICredential table (encrypted)
        """
        try:
            app_key = None
            app_secret = None
            callback_url = None

            # --- Step 1: Load client credentials (app_key, app_secret) ---
            if self.user_id:
                try:
                    from models import OAuthClientCredential
                    client_cred = OAuthClientCredential.query.filter_by(
                        user_id=int(self.user_id),
                        provider='schwab',
                        is_active=True
                    ).first()
                    if client_cred:
                        app_key = client_cred.client_id
                        app_secret = client_cred.client_secret
                        callback_url = client_cred.redirect_uri
                        logger.info(f"Loaded Schwab client credentials from DB for user {self.user_id}")
                except Exception as e:
                    logger.warning(f"Could not load client credentials from DB: {e}")

            # Fallback to environment variables
            if not app_key:
                app_key = os.environ.get("SCHWAB_APP_KEY")
                app_secret = os.environ.get("SCHWAB_APP_SECRET")
                callback_url = os.environ.get("SCHWAB_CALLBACK_URL", "https://127.0.0.1")
                if app_key:
                    logger.info("Loaded Schwab client credentials from environment")

            if not app_key or not app_secret:
                logger.warning("No Schwab client credentials available (DB or env)")
                return

            # --- Step 2: Load user tokens from APICredential table (ENCRYPTED) ---
            access_token = None
            refresh_token = None
            expires_at = None

            if self.user_id:
                try:
                    from models import APICredential
                    from utils.encryption import decrypt_credentials

                    credential = APICredential.query.filter_by(
                        user_id=int(self.user_id),
                        provider='schwab',
                        is_active=True
                    ).first()

                    if credential and credential.encrypted_credentials:
                        token_data = decrypt_credentials(credential.encrypted_credentials)
                        access_token = token_data.get('access_token')
                        refresh_token = token_data.get('refresh_token')

                        # Parse expiry - support both field names
                        expires_at_str = token_data.get('expires_at') or token_data.get('token_expiry')
                        if expires_at_str:
                            expires_at = datetime.fromisoformat(expires_at_str)

                        logger.info(f"Loaded Schwab tokens from APICredential table for user {self.user_id} | "
                                    f"has_access={bool(access_token)} | has_refresh={bool(refresh_token)} | "
                                    f"expires_at={expires_at}")
                    else:
                        logger.info(f"No Schwab APICredential found for user {self.user_id} - needs OAuth flow")

                except Exception as e:
                    logger.error(f"Failed to load tokens from APICredential: {e}")
                    import traceback
                    traceback.print_exc()

            self.credentials = SchwabCredentials(
                app_key=app_key,
                app_secret=app_secret,
                callback_url=callback_url,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at
            )

        except Exception as e:
            logger.error(f"Fatal error loading Schwab credentials: {e}")
            self.credentials = None

    def _initialize_client(self):
        """Initialize schwabdev client with loaded credentials"""
        try:
            if not SCHWABDEV_AVAILABLE:
                logger.warning("schwabdev library not available - will use direct REST API")
                return

            if not self.credentials:
                return

            self.client = schwabdev.Client(
                app_key=self.credentials.app_key,
                app_secret=self.credentials.app_secret,
                callback_url=self.credentials.callback_url,
                tokens_file=None,
                timeout=30
            )

            logger.info("schwabdev client initialized")

        except Exception as e:
            logger.error(f"Failed to initialize schwabdev client: {e}")
            self.client = None

    # ─── Token Management (UNIFIED) ─────────────────────────────────────────────

    def _is_token_expired(self) -> bool:
        """Check if current access token is expired or about to expire"""
        if not self.credentials or not self.credentials.access_token:
            return True
        if not self.credentials.expires_at:
            return True
        # 5-minute buffer
        return datetime.utcnow() + timedelta(minutes=5) >= self.credentials.expires_at

    def _refresh_access_token(self) -> bool:
        """
        Refresh the access token using the UNIFIED path:
        1. Use SchwabOAuth.refresh_token() (which does the actual HTTP call)
        2. Write refreshed tokens back to APICredential table (encrypted)
        3. Update in-memory credentials
        """
        try:
            if not self.credentials or not self.credentials.refresh_token:
                logger.error("Cannot refresh - no refresh token available")
                return False

            # Use SchwabOAuth for the actual refresh (it handles HTTP + auth header)
            from utils.schwab_oauth import SchwabOAuth
            schwab_oauth = SchwabOAuth(user_id=int(self.user_id))

            # If SchwabOAuth didn't load client creds from DB, set them manually
            if not schwab_oauth.client_id:
                schwab_oauth.set_client_credentials(
                    self.credentials.app_key,
                    self.credentials.app_secret,
                    self.credentials.callback_url
                )

            refresh_result = schwab_oauth.refresh_token(self.credentials.refresh_token)

            if not refresh_result.get('success'):
                logger.error(f"Token refresh failed: {refresh_result.get('message')}")
                return False

            new_creds = refresh_result['credentials']

            # Update in-memory credentials
            self.credentials.access_token = new_creds['access_token']
            self.credentials.refresh_token = new_creds.get('refresh_token', self.credentials.refresh_token)
            expires_at_str = new_creds.get('expires_at')
            if expires_at_str:
                self.credentials.expires_at = datetime.fromisoformat(expires_at_str)

            # Write back to APICredential table (encrypted)
            self._save_tokens_to_db(new_creds)

            self.last_token_refresh = datetime.utcnow()
            logger.info(f"Schwab token refreshed successfully for user {self.user_id}")
            return True

        except Exception as e:
            logger.error(f"Token refresh error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _save_tokens_to_db(self, credentials_dict: Dict):
        """Save tokens to APICredential table (encrypted) - the SINGLE source of truth"""
        try:
            from models import APICredential
            from utils.encryption import encrypt_credentials
            from app import db

            credential = APICredential.query.filter_by(
                user_id=int(self.user_id),
                provider='schwab',
                is_active=True
            ).first()

            if credential:
                credential.encrypted_credentials = encrypt_credentials(credentials_dict)
                credential.updated_at = datetime.utcnow()
                credential.test_status = 'success'
                credential.last_tested = datetime.utcnow()
            else:
                # Create new credential record
                credential = APICredential(
                    user_id=int(self.user_id),
                    provider='schwab',
                    encrypted_credentials=encrypt_credentials(credentials_dict),
                    is_active=True,
                    test_status='success',
                    last_tested=datetime.utcnow()
                )
                db.session.add(credential)

            db.session.commit()
            logger.info(f"Schwab tokens saved to APICredential for user {self.user_id}")

        except Exception as e:
            logger.error(f"Failed to save tokens to DB: {e}")
            import traceback
            traceback.print_exc()

    def ensure_valid_token(self) -> bool:
        """Ensure we have a valid access token, refreshing if needed"""
        if not self.credentials or not self.credentials.access_token:
            logger.warning("No access token available")
            return False

        if self._is_token_expired():
            logger.info("Token expired or expiring soon - refreshing...")
            return self._refresh_access_token()

        return True

    # ─── Direct REST API Helpers ─────────────────────────────────────────────────

    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers for direct REST calls"""
        return {
            'Authorization': f'Bearer {self.credentials.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def _api_get(self, url: str, params: Dict = None) -> Optional[Dict]:
        """Make authenticated GET request with auto-refresh"""
        if not self.ensure_valid_token():
            return None
        try:
            response = requests.get(url, headers=self._get_auth_headers(), params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                # Token might have just expired - try one refresh
                if self._refresh_access_token():
                    response = requests.get(url, headers=self._get_auth_headers(), params=params, timeout=30)
                    response.raise_for_status()
                    return response.json()
            logger.error(f"API GET error: {e}")
            raise

    def _api_post(self, url: str, data: Dict = None) -> Optional[requests.Response]:
        """Make authenticated POST request with auto-refresh"""
        if not self.ensure_valid_token():
            return None
        try:
            response = requests.post(url, headers=self._get_auth_headers(), json=data, timeout=30)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                if self._refresh_access_token():
                    response = requests.post(url, headers=self._get_auth_headers(), json=data, timeout=30)
                    response.raise_for_status()
                    return response
            logger.error(f"API POST error: {e}")
            raise

    # ─── OAuth Flow ──────────────────────────────────────────────────────────────

    def get_authorization_url(self) -> Dict[str, Any]:
        """Get Schwab OAuth authorization URL"""
        try:
            if not self.credentials or not self.credentials.app_key:
                return {'success': False, 'error': 'Schwab client credentials not configured'}

            # Use SchwabOAuth for the full OAuth flow (it handles PKCE, state, etc.)
            from utils.schwab_oauth import SchwabOAuth
            schwab_oauth = SchwabOAuth(user_id=int(self.user_id))
            if not schwab_oauth.client_id:
                schwab_oauth.set_client_credentials(
                    self.credentials.app_key,
                    self.credentials.app_secret,
                    self.credentials.callback_url
                )

            auth_url = schwab_oauth.get_authorization_url()
            return {
                'success': True,
                'authorization_url': auth_url,
                'message': 'Visit this URL to authorize Schwab access'
            }

        except Exception as e:
            logger.error(f"Failed to get authorization URL: {e}")
            return {'success': False, 'error': str(e)}

    def exchange_code_for_tokens(self, authorization_code: str, state: str = None) -> Dict[str, Any]:
        """Exchange authorization code for tokens and save to DB"""
        try:
            from utils.schwab_oauth import SchwabOAuth
            schwab_oauth = SchwabOAuth(user_id=int(self.user_id))
            if not schwab_oauth.client_id:
                schwab_oauth.set_client_credentials(
                    self.credentials.app_key,
                    self.credentials.app_secret,
                    self.credentials.callback_url
                )

            result = schwab_oauth.exchange_code_for_token(authorization_code, state)

            if result.get('success'):
                creds = result['credentials']
                # Save to APICredential table
                self._save_tokens_to_db(creds)

                # Update in-memory
                self.credentials.access_token = creds['access_token']
                self.credentials.refresh_token = creds.get('refresh_token')
                expires_at_str = creds.get('expires_at')
                if expires_at_str:
                    self.credentials.expires_at = datetime.fromisoformat(expires_at_str)

                return {
                    'success': True,
                    'message': 'Schwab authorization successful',
                    'token_expiry': self.credentials.expires_at.isoformat() if self.credentials.expires_at else None
                }

            return result

        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            return {'success': False, 'error': str(e)}

    def refresh_access_token(self) -> Dict[str, Any]:
        """Public-facing refresh endpoint"""
        success = self._refresh_access_token()
        if success:
            return {
                'success': True,
                'message': 'Access token refreshed',
                'token_expiry': self.credentials.expires_at.isoformat() if self.credentials.expires_at else None
            }
        return {'success': False, 'error': 'Failed to refresh access token'}

    # ─── Account Data (Direct REST - more reliable) ─────────────────────────────

    def get_account_numbers(self) -> Dict[str, Any]:
        """Get linked account numbers and hashes"""
        try:
            data = self._api_get(f"{self.TRADER_API_BASE}/accounts/accountNumbers")
            if data:
                # Cache account hashes
                for acct in data:
                    self._account_hashes[acct.get('accountNumber', '')] = acct.get('hashValue', '')
                return {'success': True, 'accounts': data}
            return {'success': False, 'error': 'No account data returned'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_account_info(self, account_number: str = None) -> Dict[str, Any]:
        """Get comprehensive account information"""
        try:
            # First get account hashes if we don't have them
            if not self._account_hashes:
                acct_result = self.get_account_numbers()
                if not acct_result.get('success'):
                    return acct_result

            if not self._account_hashes:
                return {'success': False, 'error': 'No linked accounts found'}

            # If specific account requested, get its hash
            if account_number:
                account_hash = self._account_hashes.get(account_number)
                if not account_hash:
                    return {'success': False, 'error': f'Account {account_number} not found'}
                url = f"{self.TRADER_API_BASE}/accounts/{account_hash}"
                data = self._api_get(url, params={'fields': 'positions'})
                accounts_data = [data] if data else []
            else:
                # Get all accounts
                data = self._api_get(f"{self.TRADER_API_BASE}/accounts", params={'fields': 'positions'})
                accounts_data = data if isinstance(data, list) else [data] if data else []

            if not accounts_data:
                return {'success': False, 'error': 'Failed to retrieve account details'}

            parsed_accounts = []
            for account_data in accounts_data:
                securities_account = account_data.get('securitiesAccount', {})
                current_balances = securities_account.get('currentBalances', {})
                positions = securities_account.get('positions', [])
                acct_num = securities_account.get('accountNumber', 'Unknown')

                account_info = AccountInfo(
                    account_number=acct_num,
                    account_hash=self._account_hashes.get(acct_num, ''),
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
                parsed_accounts.append(account_info.__dict__)

            return {
                'success': True,
                'account_info': parsed_accounts[0] if len(parsed_accounts) == 1 else parsed_accounts,
                'account_count': len(parsed_accounts)
            }

        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

    def _parse_positions(self, positions: List[Dict]) -> List[Dict]:
        """Parse and format position data"""
        parsed = []
        for position in positions:
            try:
                instrument = position.get('instrument', {})
                parsed.append({
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
                })
            except Exception as e:
                logger.error(f"Failed to parse position: {e}")
        return parsed

    # ─── Market Data ─────────────────────────────────────────────────────────────

    def get_market_data(self, symbol: str) -> Dict[str, Any]:
        """Get real-time market data for a symbol"""
        try:
            data = self._api_get(f"{self.MARKET_DATA_BASE}/quotes", params={'symbols': symbol})

            if not data or symbol.upper() not in data:
                return {'success': False, 'error': f'No market data for {symbol}'}

            quote = data[symbol.upper()]
            ref = quote.get('reference', {})
            regular = quote.get('regular', {})
            q = quote.get('quote', {})

            # Handle both flat and nested response formats
            market_data = MarketData(
                symbol=symbol.upper(),
                price=regular.get('lastPrice') or q.get('lastPrice', 0.0),
                change=regular.get('netChange') or q.get('netChange', 0.0),
                change_percent=regular.get('netPercentChange') or q.get('netPercentChangeInDouble', 0.0),
                volume=regular.get('totalVolume') or q.get('totalVolume', 0),
                high=regular.get('highPrice') or q.get('highPrice', 0.0),
                low=regular.get('lowPrice') or q.get('lowPrice', 0.0),
                open_price=regular.get('openPrice') or q.get('openPrice', 0.0),
                bid=q.get('bidPrice', 0.0),
                ask=q.get('askPrice', 0.0),
                bid_size=q.get('bidSize', 0),
                ask_size=q.get('askSize', 0),
                timestamp=datetime.utcnow()
            )

            return {
                'success': True,
                'market_data': market_data.__dict__,
                'raw_data': quote
            }

        except Exception as e:
            logger.error(f"Failed to get market data for {symbol}: {e}")
            return {'success': False, 'error': str(e)}

    def get_multiple_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """Get market data for multiple symbols"""
        try:
            symbols_str = ','.join([s.upper() for s in symbols])
            data = self._api_get(f"{self.MARKET_DATA_BASE}/quotes", params={'symbols': symbols_str})

            if not data:
                return {'success': False, 'error': 'No quote data returned'}

            market_data_list = []
            for symbol in symbols:
                sym = symbol.upper()
                if sym in data:
                    quote = data[sym]
                    ref = quote.get('reference', {})
                    regular = quote.get('regular', {})
                    q = quote.get('quote', {})

                    md = MarketData(
                        symbol=sym,
                        price=regular.get('lastPrice') or q.get('lastPrice', 0.0),
                        change=regular.get('netChange') or q.get('netChange', 0.0),
                        change_percent=regular.get('netPercentChange') or q.get('netPercentChangeInDouble', 0.0),
                        volume=regular.get('totalVolume') or q.get('totalVolume', 0),
                        high=regular.get('highPrice') or q.get('highPrice', 0.0),
                        low=regular.get('lowPrice') or q.get('lowPrice', 0.0),
                        open_price=regular.get('openPrice') or q.get('openPrice', 0.0),
                        bid=q.get('bidPrice', 0.0),
                        ask=q.get('askPrice', 0.0),
                        bid_size=q.get('bidSize', 0),
                        ask_size=q.get('askSize', 0),
                        timestamp=datetime.utcnow()
                    )
                    market_data_list.append(md.__dict__)

            return {
                'success': True,
                'market_data': market_data_list,
                'symbols_requested': len(symbols),
                'symbols_received': len(market_data_list)
            }

        except Exception as e:
            logger.error(f"Failed to get multiple quotes: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Order Management ────────────────────────────────────────────────────────

    def place_order(self, account_number: str, order_data: Dict) -> Dict[str, Any]:
        """Place a trading order"""
        try:
            # Validate required fields
            required_fields = ['orderType', 'session', 'duration', 'orderStrategyType', 'orderLegCollection']
            for field in required_fields:
                if field not in order_data:
                    return {'success': False, 'error': f'Missing required field: {field}'}

            # Get account hash
            if not self._account_hashes:
                self.get_account_numbers()
            account_hash = self._account_hashes.get(account_number)
            if not account_hash:
                return {'success': False, 'error': f'Account hash not found for {account_number}'}

            url = f"{self.TRADER_API_BASE}/accounts/{account_hash}/orders"
            response = self._api_post(url, data=order_data)

            if response and response.status_code in [200, 201]:
                # Extract order ID from Location header
                order_id = None
                location = response.headers.get('Location', '')
                if location:
                    order_id = location.split('/')[-1]

                return {
                    'success': True,
                    'message': 'Order placed successfully',
                    'order_id': order_id
                }
            else:
                status = response.status_code if response else 'No response'
                body = response.text if response else ''
                return {'success': False, 'error': f'Order failed: HTTP {status} - {body}'}

        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            return {'success': False, 'error': str(e)}

    def get_orders(self, account_number: str = None, from_date: datetime = None,
                   to_date: datetime = None) -> Dict[str, Any]:
        """Get order history"""
        try:
            if not to_date:
                to_date = datetime.utcnow()
            if not from_date:
                from_date = to_date - timedelta(days=30)

            params = {
                'fromEnteredTime': from_date.strftime('%Y-%m-%dT00:00:00.000Z'),
                'toEnteredTime': to_date.strftime('%Y-%m-%dT23:59:59.000Z')
            }

            if account_number:
                if not self._account_hashes:
                    self.get_account_numbers()
                account_hash = self._account_hashes.get(account_number)
                if not account_hash:
                    return {'success': False, 'error': f'Account {account_number} not found'}
                url = f"{self.TRADER_API_BASE}/accounts/{account_hash}/orders"
            else:
                url = f"{self.TRADER_API_BASE}/orders"

            data = self._api_get(url, params=params)
            return {
                'success': True,
                'orders': data or [],
                'from_date': from_date.isoformat(),
                'to_date': to_date.isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            return {'success': False, 'error': str(e)}

    def cancel_order(self, account_number: str, order_id: str) -> Dict[str, Any]:
        """Cancel an existing order"""
        try:
            if not self._account_hashes:
                self.get_account_numbers()
            account_hash = self._account_hashes.get(account_number)
            if not account_hash:
                return {'success': False, 'error': f'Account {account_number} not found'}

            if not self.ensure_valid_token():
                return {'success': False, 'error': 'Invalid access token'}

            url = f"{self.TRADER_API_BASE}/accounts/{account_hash}/orders/{order_id}"
            response = requests.delete(url, headers=self._get_auth_headers(), timeout=30)
            response.raise_for_status()

            return {'success': True, 'message': f'Order {order_id} cancelled'}

        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return {'success': False, 'error': str(e)}

    def get_watchlists(self, account_number: str) -> Dict[str, Any]:
        """Get user watchlists"""
        try:
            if not self._account_hashes:
                self.get_account_numbers()
            account_hash = self._account_hashes.get(account_number)
            if not account_hash:
                return {'success': False, 'error': f'Account {account_number} not found'}

            data = self._api_get(f"{self.TRADER_API_BASE}/accounts/{account_hash}/watchlists")
            return {'success': True, 'watchlists': data or []}

        except Exception as e:
            logger.error(f"Failed to get watchlists: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Price History (for ML training data) ────────────────────────────────────

    def get_price_history(self, symbol: str, period_type: str = 'month',
                          period: int = 3, frequency_type: str = 'daily',
                          frequency: int = 1) -> Dict[str, Any]:
        """Get historical price data - essential for ML model training"""
        try:
            params = {
                'symbol': symbol.upper(),
                'periodType': period_type,
                'period': period,
                'frequencyType': frequency_type,
                'frequency': frequency,
                'needExtendedHoursData': 'false'
            }
            data = self._api_get(f"{self.MARKET_DATA_BASE}/pricehistory", params=params)

            if not data or 'candles' not in data:
                return {'success': False, 'error': f'No price history for {symbol}'}

            return {
                'success': True,
                'symbol': symbol.upper(),
                'candles': data['candles'],
                'candle_count': len(data['candles'])
            }

        except Exception as e:
            logger.error(f"Failed to get price history for {symbol}: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Options Chain (for options trading) ─────────────────────────────────────

    def get_option_chain(self, symbol: str, contract_type: str = 'ALL',
                         strike_count: int = 10) -> Dict[str, Any]:
        """Get options chain data"""
        try:
            params = {
                'symbol': symbol.upper(),
                'contractType': contract_type,
                'strikeCount': strike_count,
                'includeUnderlyingQuote': 'true'
            }
            data = self._api_get(f"{self.MARKET_DATA_BASE}/chains", params=params)

            if not data:
                return {'success': False, 'error': f'No options data for {symbol}'}

            return {
                'success': True,
                'symbol': symbol.upper(),
                'underlying_price': data.get('underlyingPrice', 0),
                'call_exp_date_map': data.get('callExpDateMap', {}),
                'put_exp_date_map': data.get('putExpDateMap', {}),
                'raw_data': data
            }

        except Exception as e:
            logger.error(f"Failed to get option chain for {symbol}: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Diagnostics ─────────────────────────────────────────────────────────────

    def get_connection_status(self) -> Dict[str, Any]:
        """Get comprehensive connection status with diagnostics"""
        status = {
            'schwabdev_available': SCHWABDEV_AVAILABLE,
            'client_initialized': self.client is not None,
            'credentials_loaded': self.credentials is not None,
            'has_app_key': bool(self.credentials and self.credentials.app_key),
            'has_access_token': bool(self.credentials and self.credentials.access_token),
            'has_refresh_token': bool(self.credentials and self.credentials.refresh_token),
            'token_expired': self._is_token_expired() if self.credentials else True,
            'token_expiry': self.credentials.expires_at.isoformat() if self.credentials and self.credentials.expires_at else None,
            'last_token_refresh': self.last_token_refresh.isoformat() if self.last_token_refresh else None,
            'user_id': self.user_id,
            'auth_version': 'v2_unified'
        }

        # Diagnose issues
        issues = []
        if not status['has_app_key']:
            issues.append('No Schwab app key configured (check OAuthClientCredential table or SCHWAB_APP_KEY env var)')
        if not status['has_access_token']:
            issues.append('No access token - complete OAuth flow at /api/schwabdev/auth/start')
        if not status['has_refresh_token']:
            issues.append('No refresh token - re-authorize via OAuth')
        if status['has_access_token'] and status['token_expired']:
            issues.append('Token expired - will auto-refresh on next API call')

        status['issues'] = issues
        status['healthy'] = len(issues) == 0 or (len(issues) == 1 and 'auto-refresh' in issues[0])

        return status

    def test_connection(self) -> Dict[str, Any]:
        """Test the full connection pipeline"""
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'tests': []
        }

        # Test 1: Credentials loaded
        results['tests'].append({
            'name': 'credentials_loaded',
            'passed': self.credentials is not None and self.credentials.app_key is not None,
            'detail': 'App key and secret available' if self.credentials and self.credentials.app_key else 'Missing credentials'
        })

        # Test 2: Token available
        has_token = self.credentials and self.credentials.access_token
        results['tests'].append({
            'name': 'token_available',
            'passed': bool(has_token),
            'detail': f'Expires: {self.credentials.expires_at}' if has_token else 'No token - needs OAuth'
        })

        # Test 3: Token valid (try refresh if needed)
        if has_token:
            token_valid = self.ensure_valid_token()
            results['tests'].append({
                'name': 'token_valid',
                'passed': token_valid,
                'detail': 'Token is valid' if token_valid else 'Token refresh failed'
            })

            # Test 4: Account access
            if token_valid:
                try:
                    acct_result = self.get_account_numbers()
                    results['tests'].append({
                        'name': 'account_access',
                        'passed': acct_result.get('success', False),
                        'detail': f"Found {len(acct_result.get('accounts', []))} accounts" if acct_result.get('success') else acct_result.get('error')
                    })
                except Exception as e:
                    results['tests'].append({
                        'name': 'account_access',
                        'passed': False,
                        'detail': str(e)
                    })

        results['all_passed'] = all(t['passed'] for t in results['tests'])
        return results


# ─── Factory Functions ───────────────────────────────────────────────────────────

def create_schwabdev_manager(user_id: str = None) -> SchwabdevManager:
    """Create SchwabdevManager instance"""
    return SchwabdevManager(user_id=user_id)


def get_schwabdev_info() -> Dict[str, Any]:
    """Get information about Schwabdev integration"""
    return {
        'library_available': SCHWABDEV_AVAILABLE,
        'library_version': getattr(schwabdev, '__version__', 'unknown') if SCHWABDEV_AVAILABLE else None,
        'auth_version': 'v2_unified',
        'description': 'Schwab API integration with unified token management (v2)',
        'fixes': [
            'Tokens now read/write exclusively from APICredential table (encrypted)',
            'Uses SchwabOAuth for token refresh (single source of truth)',
            'Direct REST API calls with auto-retry on 401',
            'Proper account hash management for Schwab Trader API',
            'Added price history and options chain endpoints for ML'
        ],
        'features': [
            'OAuth 2.0 with PKCE via SchwabOAuth',
            'Automatic token refresh with 5-min buffer',
            'Account data, positions, balances',
            'Real-time quotes and market data',
            'Historical price data (for ML training)',
            'Options chain data',
            'Order placement, tracking, cancellation',
            'Watchlist management',
            'Connection diagnostics and health checks'
        ]
    }
