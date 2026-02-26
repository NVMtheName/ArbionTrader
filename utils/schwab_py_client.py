"""
schwab-py Client Wrapper for Arbion Trading Platform
=====================================================
Provides a high-level wrapper around the schwab-py library (https://pypi.org/project/schwab-py/)
for use alongside schwabdev in the Arbion Trading Platform.

schwab-py offers:
- Type-safe enums for all API parameters
- Order builder templates for equities and options
- Streaming client with handler-based architecture
- Async support via AsyncClient

This module integrates schwab-py's client with Arbion's existing
token management (APICredential table + encryption).
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

try:
    import schwab
    from schwab import auth as schwab_auth
    from schwab import client as schwab_client_mod
    from schwab.client import Client as SchwabPyClient
    SCHWAB_PY_AVAILABLE = True
except ImportError:
    SCHWAB_PY_AVAILABLE = False
    schwab = None
    schwab_auth = None
    schwab_client_mod = None
    SchwabPyClient = None

try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger(__name__)


class SchwabPyTokenManager:
    """
    Bridge between Arbion's encrypted token storage (APICredential table)
    and schwab-py's token-based authentication.

    schwab-py expects tokens as a dict with 'access_token', 'refresh_token',
    'token_type', 'expires_in', and 'creation_timestamp' fields. This class
    reads/writes tokens from/to Arbion's database seamlessly.
    """

    def __init__(self, user_id: int):
        self.user_id = user_id
        self._token_data = None

    def read_token(self) -> Optional[Dict]:
        """Read token from APICredential table (schwab-py token_read_func)"""
        try:
            from models import APICredential
            from utils.encryption import decrypt_credentials

            credential = APICredential.query.filter_by(
                user_id=self.user_id,
                provider='schwab',
                is_active=True
            ).first()

            if not credential or not credential.encrypted_credentials:
                logger.warning(f"No Schwab credentials found for user {self.user_id}")
                return None

            creds = decrypt_credentials(credential.encrypted_credentials)

            # Convert Arbion format to schwab-py format
            token = {
                'access_token': creds.get('access_token', ''),
                'refresh_token': creds.get('refresh_token', ''),
                'token_type': creds.get('token_type', 'Bearer'),
                'expires_in': 1800,  # 30 minutes standard
                'scope': creds.get('scope', 'api'),
            }

            # Add creation timestamp for schwab-py's token age tracking
            expires_at_str = creds.get('expires_at') or creds.get('token_expiry')
            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                # Derive creation timestamp from expires_at minus expires_in
                creation_time = expires_at - timedelta(seconds=1800)
                token['creation_timestamp'] = int(creation_time.timestamp())
            else:
                token['creation_timestamp'] = int(datetime.utcnow().timestamp())

            self._token_data = token
            return token

        except Exception as e:
            logger.error(f"Failed to read token for schwab-py: {e}")
            return None

    def write_token(self, token: Dict):
        """Write token to APICredential table (schwab-py token_write_func)"""
        try:
            from models import APICredential
            from utils.encryption import encrypt_credentials
            from app import db

            # Convert schwab-py format to Arbion format
            expires_in = token.get('expires_in', 1800)
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

            creds = {
                'access_token': token.get('access_token', ''),
                'refresh_token': token.get('refresh_token', ''),
                'token_type': token.get('token_type', 'Bearer'),
                'scope': token.get('scope', 'api'),
                'expires_at': expires_at.isoformat(),
                'last_refresh_at': datetime.utcnow().isoformat(),
            }

            credential = APICredential.query.filter_by(
                user_id=self.user_id,
                provider='schwab',
                is_active=True
            ).first()

            if credential:
                credential.encrypted_credentials = encrypt_credentials(creds)
                credential.updated_at = datetime.utcnow()
                credential.mark_refresh_success()
            else:
                credential = APICredential(
                    user_id=self.user_id,
                    provider='schwab',
                    encrypted_credentials=encrypt_credentials(creds),
                    is_active=True,
                    test_status='success',
                    last_tested=datetime.utcnow()
                )
                db.session.add(credential)

            db.session.commit()
            self._token_data = token
            logger.info(f"schwab-py token written to DB for user {self.user_id}")

        except Exception as e:
            logger.error(f"Failed to write schwab-py token: {e}")
            import traceback
            traceback.print_exc()


class SchwabPyClientWrapper:
    """
    Wrapper around schwab-py's Client that integrates with Arbion's
    credential management system.

    Uses schwab-py for:
    - Type-safe API calls with enum parameters
    - Built-in order templates (equities + options)
    - Streaming data via StreamClient
    - Automatic token refresh

    Falls back to direct REST (via SchwabdevManager) when schwab-py
    is not available.
    """

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.client = None
        self.token_manager = SchwabPyTokenManager(user_id) if SCHWAB_PY_AVAILABLE else None
        self._app_key = None
        self._app_secret = None
        self._callback_url = None

        self._load_client_credentials()
        self._initialize_client()

    def _load_client_credentials(self):
        """Load OAuth client credentials from DB or env vars"""
        try:
            from models import OAuthClientCredential
            client_cred = OAuthClientCredential.query.filter_by(
                user_id=self.user_id,
                provider='schwab',
                is_active=True
            ).first()

            if client_cred:
                self._app_key = client_cred.client_id
                self._app_secret = client_cred.client_secret
                self._callback_url = client_cred.redirect_uri
                return
        except Exception as e:
            logger.warning(f"Could not load client creds from DB: {e}")

        # Fallback to env vars
        self._app_key = os.environ.get('SCHWAB_APP_KEY') or os.environ.get('SCHWAB_CLIENT_ID')
        self._app_secret = os.environ.get('SCHWAB_APP_SECRET') or os.environ.get('SCHWAB_CLIENT_SECRET')
        self._callback_url = os.environ.get('SCHWAB_CALLBACK_URL', 'https://127.0.0.1')

    def _initialize_client(self):
        """Initialize schwab-py client using token access functions"""
        if not SCHWAB_PY_AVAILABLE:
            logger.warning("schwab-py not available")
            return

        if not self._app_key or not self._app_secret:
            logger.warning("No Schwab client credentials for schwab-py")
            return

        try:
            self.client = schwab_auth.client_from_access_functions(
                api_key=self._app_key,
                app_secret=self._app_secret,
                token_read_func=self.token_manager.read_token,
                token_write_func=self.token_manager.write_token,
                enforce_enums=True,
            )
            logger.info(f"schwab-py client initialized for user {self.user_id}")
        except Exception as e:
            logger.error(f"Failed to initialize schwab-py client: {e}")
            self.client = None

    @property
    def is_available(self) -> bool:
        return self.client is not None

    # ─── Account Methods ──────────────────────────────────────────────────────

    def get_account_numbers(self) -> Dict[str, Any]:
        """Get account numbers and hashes using schwab-py"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            resp = self.client.get_account_numbers()
            if resp.status_code == 200:
                data = resp.json()
                return {'success': True, 'accounts': data}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py get_account_numbers failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_account(self, account_hash: str, fields: List[str] = None) -> Dict[str, Any]:
        """Get account details with optional position/order fields"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            field_enums = None
            if fields:
                field_enums = []
                for f in fields:
                    try:
                        field_enums.append(SchwabPyClient.Account.Fields[f.upper()])
                    except KeyError:
                        pass

            resp = self.client.get_account(account_hash, fields=field_enums)
            if resp.status_code == 200:
                return {'success': True, 'account': resp.json()}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py get_account failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_all_accounts(self, fields: List[str] = None) -> Dict[str, Any]:
        """Get all linked accounts"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            field_enums = None
            if fields:
                field_enums = []
                for f in fields:
                    try:
                        field_enums.append(SchwabPyClient.Account.Fields[f.upper()])
                    except KeyError:
                        pass

            resp = self.client.get_accounts(fields=field_enums)
            if resp.status_code == 200:
                return {'success': True, 'accounts': resp.json()}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py get_accounts failed: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Market Data Methods ──────────────────────────────────────────────────

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get a single quote using schwab-py"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            resp = self.client.get_quote(symbol.upper())
            if resp.status_code == 200:
                return {'success': True, 'quote': resp.json()}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py get_quote failed for {symbol}: {e}")
            return {'success': False, 'error': str(e)}

    def get_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """Get multiple quotes using schwab-py"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            resp = self.client.get_quotes([s.upper() for s in symbols])
            if resp.status_code == 200:
                return {'success': True, 'quotes': resp.json()}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py get_quotes failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_price_history_daily(self, symbol: str, start_datetime=None,
                                 end_datetime=None, need_extended_hours=False) -> Dict[str, Any]:
        """Get daily price history"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            kwargs = {}
            if start_datetime:
                kwargs['start_datetime'] = start_datetime
            if end_datetime:
                kwargs['end_datetime'] = end_datetime
            kwargs['need_extended_hours_data'] = need_extended_hours

            resp = self.client.get_price_history_every_day(symbol.upper(), **kwargs)
            if resp.status_code == 200:
                return {'success': True, 'price_history': resp.json()}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py get_price_history_daily failed for {symbol}: {e}")
            return {'success': False, 'error': str(e)}

    def get_price_history_minute(self, symbol: str, start_datetime=None,
                                  end_datetime=None, need_extended_hours=False) -> Dict[str, Any]:
        """Get minute-level price history"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            kwargs = {}
            if start_datetime:
                kwargs['start_datetime'] = start_datetime
            if end_datetime:
                kwargs['end_datetime'] = end_datetime
            kwargs['need_extended_hours_data'] = need_extended_hours

            resp = self.client.get_price_history_every_minute(symbol.upper(), **kwargs)
            if resp.status_code == 200:
                return {'success': True, 'price_history': resp.json()}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py get_price_history_minute failed for {symbol}: {e}")
            return {'success': False, 'error': str(e)}

    def get_price_history(self, symbol: str, frequency: str = 'daily',
                          period_type: str = None, period: int = None,
                          start_datetime=None, end_datetime=None) -> Dict[str, Any]:
        """Flexible price history using schwab-py's specific methods"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}

        method_map = {
            'minute': 'get_price_history_every_minute',
            '5min': 'get_price_history_every_five_minutes',
            '10min': 'get_price_history_every_ten_minutes',
            '15min': 'get_price_history_every_fifteen_minutes',
            '30min': 'get_price_history_every_thirty_minutes',
            'daily': 'get_price_history_every_day',
            'weekly': 'get_price_history_every_week',
        }

        method_name = method_map.get(frequency, 'get_price_history_every_day')

        try:
            method = getattr(self.client, method_name)
            kwargs = {}
            if start_datetime:
                kwargs['start_datetime'] = start_datetime
            if end_datetime:
                kwargs['end_datetime'] = end_datetime

            resp = method(symbol.upper(), **kwargs)
            if resp.status_code == 200:
                return {'success': True, 'price_history': resp.json()}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py get_price_history failed for {symbol}: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Options Methods ──────────────────────────────────────────────────────

    def get_option_chain(self, symbol: str, contract_type: str = 'ALL',
                         strike_count: int = None, strategy: str = 'SINGLE',
                         from_date=None, to_date=None) -> Dict[str, Any]:
        """Get option chain with type-safe enums"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            kwargs = {'symbol': symbol.upper()}

            # Map contract type
            ct_map = {
                'ALL': SchwabPyClient.Options.ContractType.ALL,
                'CALL': SchwabPyClient.Options.ContractType.CALL,
                'PUT': SchwabPyClient.Options.ContractType.PUT,
            }
            kwargs['contract_type'] = ct_map.get(contract_type.upper(),
                                                  SchwabPyClient.Options.ContractType.ALL)

            # Map strategy
            strat_map = {
                'SINGLE': SchwabPyClient.Options.Strategy.SINGLE,
                'ANALYTICAL': SchwabPyClient.Options.Strategy.ANALYTICAL,
                'COVERED': SchwabPyClient.Options.Strategy.COVERED,
                'VERTICAL': SchwabPyClient.Options.Strategy.VERTICAL,
                'CALENDAR': SchwabPyClient.Options.Strategy.CALENDAR,
                'STRANGLE': SchwabPyClient.Options.Strategy.STRANGLE,
                'STRADDLE': SchwabPyClient.Options.Strategy.STRADDLE,
                'BUTTERFLY': SchwabPyClient.Options.Strategy.BUTTERFLY,
                'CONDOR': SchwabPyClient.Options.Strategy.CONDOR,
                'DIAGONAL': SchwabPyClient.Options.Strategy.DIAGONAL,
                'COLLAR': SchwabPyClient.Options.Strategy.COLLAR,
                'ROLL': SchwabPyClient.Options.Strategy.ROLL,
            }
            kwargs['strategy'] = strat_map.get(strategy.upper(),
                                                SchwabPyClient.Options.Strategy.SINGLE)

            if strike_count:
                kwargs['strike_count'] = strike_count
            if from_date:
                kwargs['from_date'] = from_date
            if to_date:
                kwargs['to_date'] = to_date

            resp = self.client.get_option_chain(**kwargs)
            if resp.status_code == 200:
                return {'success': True, 'option_chain': resp.json()}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py get_option_chain failed for {symbol}: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Order Methods ────────────────────────────────────────────────────────

    def place_order(self, account_hash: str, order_spec: Dict) -> Dict[str, Any]:
        """Place an order using schwab-py (accepts OrderBuilder dict or raw dict)"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            resp = self.client.place_order(account_hash, order_spec)
            if resp.status_code in (200, 201):
                # Extract order ID from Location header
                order_id = None
                location = resp.headers.get('Location', '')
                if location:
                    order_id = location.split('/')[-1]
                return {'success': True, 'order_id': order_id, 'message': 'Order placed'}
            return {'success': False, 'error': f'HTTP {resp.status_code}: {resp.text}'}
        except Exception as e:
            logger.error(f"schwab-py place_order failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_orders(self, account_hash: str, from_entered_datetime=None,
                   to_entered_datetime=None, status: str = None,
                   max_results: int = None) -> Dict[str, Any]:
        """Get orders for an account"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            kwargs = {}
            if from_entered_datetime:
                kwargs['from_entered_datetime'] = from_entered_datetime
            else:
                kwargs['from_entered_datetime'] = datetime.utcnow() - timedelta(days=30)
            if to_entered_datetime:
                kwargs['to_entered_datetime'] = to_entered_datetime
            else:
                kwargs['to_entered_datetime'] = datetime.utcnow()
            if status:
                try:
                    kwargs['status'] = SchwabPyClient.Order.Status[status.upper()]
                except KeyError:
                    pass
            if max_results:
                kwargs['max_results'] = max_results

            resp = self.client.get_orders_for_account(account_hash, **kwargs)
            if resp.status_code == 200:
                return {'success': True, 'orders': resp.json()}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py get_orders failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_order(self, account_hash: str, order_id: str) -> Dict[str, Any]:
        """Get a specific order"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            resp = self.client.get_order(order_id, account_hash)
            if resp.status_code == 200:
                return {'success': True, 'order': resp.json()}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py get_order failed: {e}")
            return {'success': False, 'error': str(e)}

    def cancel_order(self, account_hash: str, order_id: str) -> Dict[str, Any]:
        """Cancel an order"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            resp = self.client.cancel_order(order_id, account_hash)
            if resp.status_code in (200, 204):
                return {'success': True, 'message': f'Order {order_id} cancelled'}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py cancel_order failed: {e}")
            return {'success': False, 'error': str(e)}

    def replace_order(self, account_hash: str, order_id: str,
                      order_spec: Dict) -> Dict[str, Any]:
        """Replace an existing order"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            resp = self.client.replace_order(account_hash, order_id, order_spec)
            if resp.status_code in (200, 201):
                new_order_id = None
                location = resp.headers.get('Location', '')
                if location:
                    new_order_id = location.split('/')[-1]
                return {'success': True, 'new_order_id': new_order_id, 'message': 'Order replaced'}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py replace_order failed: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Market Info Methods ──────────────────────────────────────────────────

    def get_movers(self, index: str, sort_order: str = None,
                   frequency: int = None) -> Dict[str, Any]:
        """Get top movers for an index (e.g., $DJI, $SPX.X, $COMPX)"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            # Map index string to enum
            idx_map = {
                'DJI': SchwabPyClient.Movers.Index.DJI,
                '$DJI': SchwabPyClient.Movers.Index.DJI,
                'SPX': SchwabPyClient.Movers.Index.SPX,
                '$SPX.X': SchwabPyClient.Movers.Index.SPX,
                'COMPX': SchwabPyClient.Movers.Index.COMPX,
                '$COMPX': SchwabPyClient.Movers.Index.COMPX,
                'NYSE': SchwabPyClient.Movers.Index.NYSE,
                'NASDAQ': SchwabPyClient.Movers.Index.NASDAQ,
                'OTCBB': SchwabPyClient.Movers.Index.OTCBB,
                'INDEX_ALL': SchwabPyClient.Movers.Index.INDEX_ALL,
                'EQUITY_ALL': SchwabPyClient.Movers.Index.EQUITY_ALL,
                'OPTION_ALL': SchwabPyClient.Movers.Index.OPTION_ALL,
                'OPTION_PUT': SchwabPyClient.Movers.Index.OPTION_PUT,
                'OPTION_CALL': SchwabPyClient.Movers.Index.OPTION_CALL,
            }
            index_enum = idx_map.get(index.upper())
            if not index_enum:
                return {'success': False, 'error': f'Unknown index: {index}'}

            kwargs = {'index': index_enum}

            if sort_order:
                so_map = {
                    'VOLUME': SchwabPyClient.Movers.SortOrder.VOLUME,
                    'TRADES': SchwabPyClient.Movers.SortOrder.TRADES,
                    'PERCENT_CHANGE_UP': SchwabPyClient.Movers.SortOrder.PERCENT_CHANGE_UP,
                    'PERCENT_CHANGE_DOWN': SchwabPyClient.Movers.SortOrder.PERCENT_CHANGE_DOWN,
                }
                kwargs['sort_order'] = so_map.get(sort_order.upper())

            if frequency is not None:
                freq_map = {
                    0: SchwabPyClient.Movers.Frequency.ZERO,
                    1: SchwabPyClient.Movers.Frequency.ONE,
                    5: SchwabPyClient.Movers.Frequency.FIVE,
                    10: SchwabPyClient.Movers.Frequency.TEN,
                    30: SchwabPyClient.Movers.Frequency.THIRTY,
                    60: SchwabPyClient.Movers.Frequency.SIXTY,
                }
                kwargs['frequency'] = freq_map.get(frequency)

            resp = self.client.get_movers(**kwargs)
            if resp.status_code == 200:
                return {'success': True, 'movers': resp.json()}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py get_movers failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_market_hours(self, markets: List[str], date=None) -> Dict[str, Any]:
        """Get market hours for specified markets"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            market_map = {
                'EQUITY': SchwabPyClient.MarketHours.Market.EQUITY,
                'OPTION': SchwabPyClient.MarketHours.Market.OPTION,
                'BOND': SchwabPyClient.MarketHours.Market.BOND,
                'FUTURE': SchwabPyClient.MarketHours.Market.FUTURE,
                'FOREX': SchwabPyClient.MarketHours.Market.FOREX,
            }
            market_enums = []
            for m in markets:
                enum = market_map.get(m.upper())
                if enum:
                    market_enums.append(enum)

            if not market_enums:
                return {'success': False, 'error': 'No valid markets specified'}

            kwargs = {'markets': market_enums}
            if date:
                kwargs['date'] = date

            resp = self.client.get_market_hours(**kwargs)
            if resp.status_code == 200:
                return {'success': True, 'market_hours': resp.json()}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py get_market_hours failed: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Instrument Search Methods ────────────────────────────────────────────

    def search_instruments(self, symbols: str, projection: str = 'SYMBOL_SEARCH') -> Dict[str, Any]:
        """Search for instruments by symbol or description"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            proj_map = {
                'SYMBOL_SEARCH': SchwabPyClient.Instrument.Projection.SYMBOL_SEARCH,
                'SYMBOL_REGEX': SchwabPyClient.Instrument.Projection.SYMBOL_REGEX,
                'DESCRIPTION_SEARCH': SchwabPyClient.Instrument.Projection.DESCRIPTION_SEARCH,
                'DESCRIPTION_REGEX': SchwabPyClient.Instrument.Projection.DESCRIPTION_REGEX,
                'SEARCH': SchwabPyClient.Instrument.Projection.SEARCH,
                'FUNDAMENTAL': SchwabPyClient.Instrument.Projection.FUNDAMENTAL,
            }
            proj_enum = proj_map.get(projection.upper(),
                                      SchwabPyClient.Instrument.Projection.SYMBOL_SEARCH)

            resp = self.client.get_instruments(symbols, proj_enum)
            if resp.status_code == 200:
                return {'success': True, 'instruments': resp.json()}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py search_instruments failed: {e}")
            return {'success': False, 'error': str(e)}

    def get_instrument_by_cusip(self, cusip: str) -> Dict[str, Any]:
        """Get instrument by CUSIP"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            resp = self.client.get_instrument_by_cusip(cusip)
            if resp.status_code == 200:
                return {'success': True, 'instrument': resp.json()}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py get_instrument_by_cusip failed: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Transaction Methods ──────────────────────────────────────────────────

    def get_transactions(self, account_hash: str, start_date=None,
                         end_date=None, transaction_types: str = None,
                         symbol: str = None) -> Dict[str, Any]:
        """Get transaction history"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            kwargs = {'account_hash': account_hash}
            if start_date:
                kwargs['start_date'] = start_date
            else:
                kwargs['start_date'] = datetime.utcnow() - timedelta(days=60)
            if end_date:
                kwargs['end_date'] = end_date
            else:
                kwargs['end_date'] = datetime.utcnow()
            if transaction_types:
                try:
                    kwargs['transaction_types'] = SchwabPyClient.Transactions.TransactionType[transaction_types.upper()]
                except KeyError:
                    pass
            if symbol:
                kwargs['symbol'] = symbol.upper()

            resp = self.client.get_transactions(**kwargs)
            if resp.status_code == 200:
                return {'success': True, 'transactions': resp.json()}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py get_transactions failed: {e}")
            return {'success': False, 'error': str(e)}

    # ─── User Preferences ─────────────────────────────────────────────────────

    def get_user_preferences(self) -> Dict[str, Any]:
        """Get user preferences"""
        if not self.is_available:
            return {'success': False, 'error': 'schwab-py client not initialized'}
        try:
            resp = self.client.get_user_preferences()
            if resp.status_code == 200:
                return {'success': True, 'preferences': resp.json()}
            return {'success': False, 'error': f'HTTP {resp.status_code}'}
        except Exception as e:
            logger.error(f"schwab-py get_user_preferences failed: {e}")
            return {'success': False, 'error': str(e)}

    # ─── Diagnostic Methods ───────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Get schwab-py client status"""
        return {
            'schwab_py_available': SCHWAB_PY_AVAILABLE,
            'schwab_py_version': getattr(schwab, '__version__', 'unknown') if SCHWAB_PY_AVAILABLE else None,
            'client_initialized': self.client is not None,
            'has_app_key': bool(self._app_key),
            'user_id': self.user_id,
        }


# ─── Factory Functions ────────────────────────────────────────────────────────

def create_schwab_py_client(user_id: int) -> SchwabPyClientWrapper:
    """Create a schwab-py client wrapper for a user"""
    return SchwabPyClientWrapper(user_id=user_id)


def get_schwab_py_info() -> Dict[str, Any]:
    """Get schwab-py library information"""
    return {
        'library_available': SCHWAB_PY_AVAILABLE,
        'library_version': getattr(schwab, '__version__', 'unknown') if SCHWAB_PY_AVAILABLE else None,
        'description': 'Unofficial Python wrapper for Charles Schwab HTTP API',
        'features': [
            'Type-safe enum parameters for all API calls',
            'Built-in equity order templates (market, limit, short, cover)',
            'Built-in options order templates (single, vertical spreads)',
            'Advanced order strategies (OCO, first-triggers-second)',
            'Streaming client for real-time data',
            'Automatic token refresh via httpx',
            'Movers, market hours, instruments, transactions',
            'Price history at multiple frequencies',
            'Option chains with strategy analysis',
        ],
    }
