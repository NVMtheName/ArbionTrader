"""
E-trade API Client for fetching real account data
Implements OAuth 1.0a authentication per E-trade API requirements
Compatible with multi-user Arbion trading platform
"""

import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import urllib.parse
import hashlib
import hmac
import base64
import time
import secrets

logger = logging.getLogger(__name__)

class EtradeAPIClient:
    """
    E-trade API client for fetching real account data
    Implements OAuth 1.0a authentication per E-trade API requirements
    """
    
    def __init__(self, client_key: str, client_secret: str, access_token: str = None, 
                 access_secret: str = None, sandbox: bool = False):
        """
        Initialize E-trade API client
        
        Args:
            client_key: E-trade API client key
            client_secret: E-trade API client secret
            access_token: OAuth access token (optional for initial setup)
            access_secret: OAuth access secret (optional for initial setup)
            sandbox: Whether to use sandbox environment
        """
        self.client_key = client_key
        self.client_secret = client_secret
        self.access_token = access_token
        self.access_secret = access_secret
        self.sandbox = sandbox
        
        # Set base URL based on environment
        if sandbox:
            self.base_url = "https://etwssandbox.etrade.com"
        else:
            self.base_url = "https://api.etrade.com"
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Arbion-Trading-Platform/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def _generate_oauth_signature(self, method: str, url: str, params: Dict[str, str]) -> str:
        """
        Generate OAuth 1.0a signature
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            params: Request parameters including OAuth parameters
            
        Returns:
            OAuth signature
        """
        # Create signature base string
        normalized_params = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        signature_base = f"{method}&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(normalized_params, safe='')}"
        
        # Create signing key
        signing_key = f"{urllib.parse.quote(self.client_secret, safe='')}&"
        if self.access_secret:
            signing_key += urllib.parse.quote(self.access_secret, safe='')
        
        # Generate signature
        signature = hmac.new(
            signing_key.encode('utf-8'),
            signature_base.encode('utf-8'),
            hashlib.sha1
        ).digest()
        
        return base64.b64encode(signature).decode('utf-8')
    
    def _get_oauth_header(self, method: str, url: str, params: Dict[str, str] = None) -> str:
        """
        Generate OAuth authorization header
        
        Args:
            method: HTTP method
            url: Request URL
            params: Additional request parameters
            
        Returns:
            Authorization header value
        """
        if params is None:
            params = {}
        
        # OAuth parameters
        oauth_params = {
            'oauth_consumer_key': self.client_key,
            'oauth_nonce': secrets.token_hex(16),
            'oauth_signature_method': 'HMAC-SHA1',
            'oauth_timestamp': str(int(time.time())),
            'oauth_version': '1.0'
        }
        
        if self.access_token:
            oauth_params['oauth_token'] = self.access_token
        
        # Combine all parameters for signature
        all_params = {**params, **oauth_params}
        
        # Generate signature
        signature = self._generate_oauth_signature(method, url, all_params)
        oauth_params['oauth_signature'] = signature
        
        # Build authorization header
        auth_header = 'OAuth ' + ', '.join([f'{k}="{v}"' for k, v in oauth_params.items()])
        return auth_header
    
    def _make_request(self, method: str, endpoint: str, params: Dict[str, str] = None, 
                     json_data: Dict = None) -> requests.Response:
        """
        Make authenticated API request
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            json_data: JSON request body
            
        Returns:
            Response object
        """
        url = f"{self.base_url}{endpoint}"
        
        if params is None:
            params = {}
        
        # Generate OAuth header
        auth_header = self._get_oauth_header(method, url, params)
        
        headers = {
            'Authorization': auth_header,
            'Accept': 'application/json'
        }
        
        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                params=params,
                json=json_data,
                headers=headers,
                timeout=30
            )
            
            response.raise_for_status()
            return response
            
        except requests.exceptions.Timeout:
            logger.error(f"E-trade API request timeout: {url}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"E-trade API request failed: {url} - {str(e)}")
            raise
    
    def get_user_profile(self) -> Dict[str, Any]:
        """
        Get user profile information
        
        Returns:
            User profile dictionary
        """
        try:
            response = self._make_request('GET', '/v1/user/profile')
            data = response.json()
            
            logger.info("Retrieved E-trade user profile")
            return data
            
        except Exception as e:
            logger.error(f"Failed to get user profile: {str(e)}")
            return {}
    
    def get_account_list(self) -> List[Dict[str, Any]]:
        """
        Get list of user accounts
        
        Returns:
            List of account dictionaries
        """
        try:
            response = self._make_request('GET', '/v1/account/list')
            data = response.json()
            
            accounts = data.get('AccountListResponse', {}).get('Accounts', {}).get('Account', [])
            
            # Ensure accounts is a list
            if isinstance(accounts, dict):
                accounts = [accounts]
            
            logger.info(f"Retrieved {len(accounts)} E-trade accounts")
            return accounts
            
        except Exception as e:
            logger.error(f"Failed to get account list: {str(e)}")
            return []
    
    def get_account_balance(self, account_id_key: str) -> Dict[str, Any]:
        """
        Get account balance information
        
        Args:
            account_id_key: E-trade account ID key (accountIdKey from account list)
            
        Returns:
            Balance information dictionary
        """
        try:
            response = self._make_request('GET', f'/v1/account/{account_id_key}/balance')
            data = response.json()
            
            balance_response = data.get('BalanceResponse', {})
            computed = balance_response.get('Computed', {})
            real_time_values = computed.get('RealTimeValues', {})
            
            balance_info = {
                'account_id': account_id_key,
                'account_value': float(real_time_values.get('totalAccountValue', 0)),
                'cash_balance': float(computed.get('cashBalance', 0)),
                'buying_power': float(computed.get('marginBuyingPower', 0)),
                'cash_buying_power': float(computed.get('cashBuyingPower', 0)),
                'margin_balance': float(computed.get('marginBalance', 0)),
                'account_type': balance_response.get('accountType', 'UNKNOWN'),
                'account_desc': balance_response.get('accountDescription', '')
            }
            
            logger.info(f"Retrieved balance for E-trade account {account_id_key}: ${balance_info['account_value']:.2f}")
            return balance_info
            
        except Exception as e:
            logger.error(f"Failed to get balance for account {account_id_key}: {str(e)}")
            return {}
    
    def get_portfolio(self, account_id_key: str) -> List[Dict[str, Any]]:
        """
        Get portfolio positions
        
        Args:
            account_id_key: E-trade account ID key (accountIdKey from account list)
            
        Returns:
            List of position dictionaries
        """
        try:
            response = self._make_request('GET', f'/v1/account/{account_id_key}/portfolio')
            data = response.json()
            
            portfolio_response = data.get('PortfolioResponse', {})
            account_portfolio = portfolio_response.get('AccountPortfolio', [])
            
            # Ensure account_portfolio is a list
            if isinstance(account_portfolio, dict):
                account_portfolio = [account_portfolio]
            
            # Format positions
            formatted_positions = []
            for portfolio in account_portfolio:
                positions = portfolio.get('Position', [])
                
                # Ensure positions is a list
                if isinstance(positions, dict):
                    positions = [positions]
                
                for position in positions:
                    product = position.get('Product', {})
                    quick = position.get('Quick', {})
                    
                    formatted_position = {
                        'symbol': product.get('symbol', 'UNKNOWN'),
                        'description': position.get('symbolDescription', product.get('companyName', '')),
                        'asset_type': product.get('securityType', 'UNKNOWN'),
                        'quantity': float(position.get('quantity', 0)),
                        'market_value': float(position.get('marketValue', 0)),
                        'price_paid': float(position.get('pricePaid', 0)),
                        'current_price': float(quick.get('lastTrade', 0)),
                        'day_pl': float(position.get('todaysGainLoss', 0)),
                        'total_pl': float(position.get('totalGain', 0)),
                        'day_pl_percent': float(position.get('todaysGainLossPercentage', 0)),
                        'total_pl_percent': float(position.get('totalGainLossPercentage', 0))
                    }
                    formatted_positions.append(formatted_position)
            
            logger.info(f"Retrieved {len(formatted_positions)} positions for E-trade account {account_id_key}")
            return formatted_positions
            
        except Exception as e:
            logger.error(f"Failed to get portfolio for account {account_id_key}: {str(e)}")
            return []
    
    def get_orders(self, account_id: str) -> List[Dict[str, Any]]:
        """
        Get account orders
        
        Args:
            account_id: E-trade account ID
            
        Returns:
            List of order dictionaries
        """
        try:
            response = self._make_request('GET', f'/v1/account/{account_id}/orders')
            data = response.json()
            
            orders_response = data.get('OrdersResponse', {})
            order_list = orders_response.get('OrderList', {})
            orders = order_list.get('Order', [])
            
            # Ensure orders is a list
            if isinstance(orders, dict):
                orders = [orders]
            
            # Format orders
            formatted_orders = []
            for order in orders:
                order_detail = order.get('OrderDetail', {})
                instrument = order_detail.get('Instrument', {})
                product = instrument.get('Product', {})
                
                formatted_order = {
                    'order_id': order.get('orderId', ''),
                    'symbol': product.get('symbol', 'UNKNOWN'),
                    'side': order_detail.get('orderAction', 'UNKNOWN'),
                    'quantity': float(order_detail.get('quantity', 0)),
                    'price': float(order_detail.get('price', 0)),
                    'order_type': order_detail.get('orderType', 'UNKNOWN'),
                    'status': order.get('orderStatus', 'UNKNOWN'),
                    'placed_time': order.get('placedTime', ''),
                    'executed_time': order.get('executedTime', '')
                }
                formatted_orders.append(formatted_order)
            
            logger.info(f"Retrieved {len(formatted_orders)} orders for E-trade account {account_id}")
            return formatted_orders
            
        except Exception as e:
            logger.error(f"Failed to get orders for account {account_id}: {str(e)}")
            return []
    
    def get_quotes(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get stock quotes
        
        Args:
            symbols: List of stock symbols
            
        Returns:
            Dictionary of quotes keyed by symbol
        """
        try:
            symbols_str = ','.join(symbols)
            response = self._make_request('GET', f'/v1/market/productlookup/{symbols_str}')
            data = response.json()
            
            quotes = {}
            product_lookup = data.get('ProductLookupResponse', {})
            data_list = product_lookup.get('Data', [])
            
            # Ensure data_list is a list
            if isinstance(data_list, dict):
                data_list = [data_list]
            
            for item in data_list:
                product = item.get('Product', {})
                symbol = product.get('symbol', 'UNKNOWN')
                
                quotes[symbol] = {
                    'symbol': symbol,
                    'company_name': product.get('companyName', ''),
                    'exchange': product.get('exchange', ''),
                    'security_type': product.get('securityType', ''),
                    'last_price': float(item.get('lastPrice', 0)),
                    'change': float(item.get('change', 0)),
                    'change_percent': float(item.get('changePercent', 0)),
                    'volume': int(item.get('volume', 0)),
                    'bid': float(item.get('bid', 0)),
                    'ask': float(item.get('ask', 0))
                }
            
            logger.info(f"Retrieved quotes for {len(quotes)} symbols")
            return quotes
            
        except Exception as e:
            logger.error(f"Failed to get quotes: {str(e)}")
            return {}
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test API connection and authentication
        
        Returns:
            Test result dictionary
        """
        try:
            profile = self.get_user_profile()
            accounts = self.get_account_list()
            
            return {
                'success': True,
                'message': 'E-trade API connection successful',
                'profile': profile,
                'account_count': len(accounts),
                'accounts': accounts
            }
            
        except Exception as e:
            logger.error(f"E-trade API connection test failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }