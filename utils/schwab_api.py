"""
Schwab API Client for fetching real account data
Implements RFC 6750 Bearer Token Usage for secure API access
"""

import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class SchwabAPIClient:
    """
    Schwab API client for fetching real account data
    Implements RFC 6750 Bearer Token Usage compliance
    """
    
    def __init__(self, access_token: str, base_url: str = "https://api.schwabapi.com"):
        """
        Initialize Schwab API client
        
        Args:
            access_token: Bearer token for API authentication
            base_url: Schwab API base URL
        """
        self.access_token = access_token
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        
        # Set default headers with Bearer token per RFC 6750
        self.session.headers.update({
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'Arbion-Trading-Platform/1.0'
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make authenticated API request with proper error handling
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional request parameters
            
        Returns:
            Response object
            
        Raises:
            requests.exceptions.RequestException: For API errors
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                timeout=30,
                **kwargs
            )
            
            # Handle Bearer token errors per RFC 6750 Section 3.1
            if response.status_code == 401:
                error_data = response.json() if response.content else {}
                error_code = error_data.get('error', 'invalid_token')
                
                if error_code == 'invalid_token':
                    logger.error("Schwab API: Invalid or expired Bearer token")
                    raise requests.exceptions.HTTPError("Bearer token is invalid or expired")
                elif error_code == 'insufficient_scope':
                    logger.error("Schwab API: Insufficient scope for this operation")
                    raise requests.exceptions.HTTPError("Insufficient scope for this operation")
                else:
                    logger.error(f"Schwab API: Authentication error - {error_code}")
                    raise requests.exceptions.HTTPError(f"Authentication error: {error_code}")
            
            response.raise_for_status()
            return response
            
        except requests.exceptions.Timeout:
            logger.error(f"Schwab API request timeout: {url}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Schwab API request failed: {url} - {str(e)}")
            raise
    
    def get_account_numbers(self) -> List[str]:
        """
        Get list of account numbers for the authenticated user
        
        Returns:
            List of account numbers
        """
        try:
            response = self._make_request('GET', '/trader/v1/accounts/accountNumbers')
            data = response.json()
            
            # Extract account numbers from response
            account_numbers = []
            for account in data:
                if 'accountNumber' in account:
                    account_numbers.append(account['accountNumber'])
            
            logger.info(f"Retrieved {len(account_numbers)} Schwab account numbers")
            return account_numbers
            
        except Exception as e:
            logger.error(f"Failed to get Schwab account numbers: {str(e)}")
            return []
    
    def get_account_details(self, account_number: str) -> Dict[str, Any]:
        """
        Get detailed account information
        
        Args:
            account_number: Schwab account number
            
        Returns:
            Account details dictionary
        """
        try:
            response = self._make_request(
                'GET', 
                f'/trader/v1/accounts/{account_number}',
                params={'fields': 'positions,orders'}
            )
            data = response.json()
            
            logger.info(f"Retrieved account details for {account_number}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to get account details for {account_number}: {str(e)}")
            return {}
    
    def get_account_balance(self, account_number: str) -> Dict[str, float]:
        """
        Get account balance information
        
        Args:
            account_number: Schwab account number
            
        Returns:
            Balance information dictionary
        """
        try:
            account_data = self.get_account_details(account_number)
            
            if not account_data:
                return {}
            
            # Extract balance information
            securities_account = account_data.get('securitiesAccount', {})
            initial_balances = securities_account.get('initialBalances', {})
            current_balances = securities_account.get('currentBalances', {})
            
            balance_info = {
                'account_number': account_number,
                'account_value': current_balances.get('liquidationValue', 0.0),
                'cash_balance': current_balances.get('cashBalance', 0.0),
                'buying_power': current_balances.get('buyingPower', 0.0),
                'day_trading_buying_power': current_balances.get('dayTradingBuyingPower', 0.0),
                'long_market_value': current_balances.get('longMarketValue', 0.0),
                'short_market_value': current_balances.get('shortMarketValue', 0.0),
                'total_cash': current_balances.get('totalCash', 0.0),
                'account_type': securities_account.get('type', 'UNKNOWN')
            }
            
            logger.info(f"Retrieved balance for account {account_number}: ${balance_info['account_value']:.2f}")
            return balance_info
            
        except Exception as e:
            logger.error(f"Failed to get balance for account {account_number}: {str(e)}")
            return {}
    
    def get_user_profile(self) -> Dict[str, Any]:
        """
        Get user profile information
        
        Returns:
            User profile dictionary
        """
        try:
            response = self._make_request('GET', '/trader/v1/userPreference')
            data = response.json()
            
            logger.info("Retrieved Schwab user profile")
            return data
            
        except Exception as e:
            logger.error(f"Failed to get user profile: {str(e)}")
            return {}
    
    def get_positions(self, account_number: str) -> List[Dict[str, Any]]:
        """
        Get account positions
        
        Args:
            account_number: Schwab account number
            
        Returns:
            List of position dictionaries
        """
        try:
            account_data = self.get_account_details(account_number)
            
            if not account_data:
                return []
            
            securities_account = account_data.get('securitiesAccount', {})
            positions = securities_account.get('positions', [])
            
            # Process and format positions
            formatted_positions = []
            for position in positions:
                instrument = position.get('instrument', {})
                formatted_position = {
                    'symbol': instrument.get('symbol', 'UNKNOWN'),
                    'description': instrument.get('description', ''),
                    'asset_type': instrument.get('assetType', 'UNKNOWN'),
                    'quantity': position.get('longQuantity', 0) - position.get('shortQuantity', 0),
                    'market_value': position.get('marketValue', 0.0),
                    'average_price': position.get('averagePrice', 0.0),
                    'current_price': position.get('currentPrice', 0.0),
                    'day_pl': position.get('currentDayProfitLoss', 0.0),
                    'day_pl_percent': position.get('currentDayProfitLossPercentage', 0.0)
                }
                formatted_positions.append(formatted_position)
            
            logger.info(f"Retrieved {len(formatted_positions)} positions for account {account_number}")
            return formatted_positions
            
        except Exception as e:
            logger.error(f"Failed to get positions for account {account_number}: {str(e)}")
            return []
    
    def get_orders(self, account_number: str, from_date: Optional[str] = None, to_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get account orders
        
        Args:
            account_number: Schwab account number
            from_date: Start date (YYYY-MM-DD format)
            to_date: End date (YYYY-MM-DD format)
            
        Returns:
            List of order dictionaries
        """
        try:
            # Default to last 30 days if dates not provided
            if not from_date:
                from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            if not to_date:
                to_date = datetime.now().strftime('%Y-%m-%d')
            
            params = {
                'fromEnteredTime': from_date,
                'toEnteredTime': to_date,
                'maxResults': 100
            }
            
            response = self._make_request(
                'GET',
                f'/trader/v1/accounts/{account_number}/orders',
                params=params
            )
            data = response.json()
            
            logger.info(f"Retrieved {len(data)} orders for account {account_number}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to get orders for account {account_number}: {str(e)}")
            return []
    
    def get_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        """
        Get market data for symbols
        
        Args:
            symbols: List of symbols to get quotes for
            
        Returns:
            Market data dictionary
        """
        try:
            # Convert symbols list to comma-separated string
            symbol_string = ','.join(symbols)
            
            response = self._make_request(
                'GET',
                '/marketdata/v1/quotes',
                params={'symbols': symbol_string}
            )
            data = response.json()
            
            logger.info(f"Retrieved market data for {len(symbols)} symbols")
            return data
            
        except Exception as e:
            logger.error(f"Failed to get market data: {str(e)}")
            return {}
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test API connection and token validity
        
        Returns:
            Connection test result
        """
        try:
            # Test with a simple API call
            account_numbers = self.get_account_numbers()
            
            if account_numbers:
                return {
                    'success': True,
                    'message': f'Connected successfully. Found {len(account_numbers)} account(s).',
                    'account_count': len(account_numbers)
                }
            else:
                return {
                    'success': False,
                    'message': 'Connected but no accounts found.'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Connection failed: {str(e)}'
            }