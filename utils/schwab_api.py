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
            base_url: Schwab API base URL (official: https://api.schwabapi.com)
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
    
    def get_account_numbers(self) -> List[Dict[str, str]]:
        """
        Get list of account numbers and their encrypted hashes for the
        authenticated user using official Schwab Trader API.

        Schwab's Trader API requires using the ``hashValue`` when accessing
        account-specific endpoints. The plain account number is provided only
        for display purposes.

        Returns:
            List of dictionaries with ``account_number`` and ``hash_value`` keys.
        """
        try:
            response = self._make_request('GET', '/trader/v1/accounts/accountNumbers')
            data = response.json()

            account_numbers = []
            for account in data:
                if 'accountNumber' in account and 'hashValue' in account:
                    account_numbers.append({
                        'account_number': account['accountNumber'],
                        'hash_value': account['hashValue'],
                    })

            logger.info(
                f"Retrieved {len(account_numbers)} Schwab account numbers"
            )
            return account_numbers
            
        except Exception as e:
            logger.error(f"Failed to get Schwab account numbers: {str(e)}")
            return []
    
    def get_account_details(self, account_hash: str) -> Dict[str, Any]:
        """
        Get detailed account information using official Schwab Trader API
        
        Args:
            account_hash: Schwab account hash value (not plain account number)
            
        Returns:
            Account details dictionary
        """
        try:
            response = self._make_request(
                'GET', 
                f'/trader/v1/accounts/{account_hash}',
                params={'fields': 'positions,orders'}
            )
            data = response.json()
            
            logger.info(f"Retrieved account details for hash {account_hash[:8]}...")
            return data
            
        except Exception as e:
            logger.error(f"Failed to get account details for hash {account_hash[:8]}...: {str(e)}")
            return {}
    
    def get_account_balance(self, account_hash: str, account_number: str) -> Dict[str, float]:
        """
        Get account balance information using official Schwab Trader API
        
        Args:
            account_hash: Schwab account hash value (required for API calls)
            account_number: Plain account number (for display purposes)
            
        Returns:
            Balance information dictionary
        """
        try:
            account_data = self.get_account_details(account_hash)
            
            if not account_data:
                return {}
            
            # Extract balance information from securities account
            securities_account = account_data.get('securitiesAccount', {})
            initial_balances = securities_account.get('initialBalances', {})
            current_balances = securities_account.get('currentBalances', {})
            
            balance_info = {
                'account_number': account_number,
                'account_hash': account_hash,
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
    
    def get_positions(self, account_hash: str, account_number: str) -> List[Dict[str, Any]]:
        """
        Get account positions using official Schwab Trader API
        
        Args:
            account_hash: Schwab account hash value (required for API calls)
            account_number: Plain account number (for display purposes)
            
        Returns:
            List of position dictionaries
        """
        try:
            account_data = self.get_account_details(account_hash)
            
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
    
    def place_order(self, account_hash: str, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Place a trading order

        Args:
            account_hash: Schwab account hash value (required for API calls)
            order_data: Order specification following Schwab's order schema

        Returns:
            Order response with order_id or error details

        Raises:
            requests.exceptions.HTTPError: For API errors
        """
        try:
            response = self._make_request(
                'POST',
                f'/trader/v1/accounts/{account_hash}/orders',
                json=order_data
            )

            # Schwab returns 201 on successful order placement
            # Order ID is in Location header
            if response.status_code == 201:
                location = response.headers.get('Location', '')
                order_id = location.split('/')[-1] if location else None

                logger.info(f"Successfully placed order for account {account_hash[:8]}... Order ID: {order_id}")

                return {
                    'success': True,
                    'order_id': order_id,
                    'message': 'Order placed successfully',
                    'location': location
                }
            else:
                # Return response body for error details
                error_data = response.json() if response.content else {}
                logger.error(f"Failed to place order: {response.status_code} - {error_data}")
                return {
                    'success': False,
                    'status_code': response.status_code,
                    'error': error_data,
                    'message': f'Order placement failed with status {response.status_code}'
                }

        except Exception as e:
            logger.error(f"Failed to place order for account {account_hash[:8]}...: {str(e)}")
            return {
                'success': False,
                'message': f'Order placement error: {str(e)}'
            }

    def get_order_by_id(self, account_hash: str, order_id: str) -> Dict[str, Any]:
        """
        Get details of a specific order by ID

        Args:
            account_hash: Schwab account hash value
            order_id: Order ID to retrieve

        Returns:
            Order details dictionary
        """
        try:
            response = self._make_request(
                'GET',
                f'/trader/v1/accounts/{account_hash}/orders/{order_id}'
            )
            data = response.json()

            logger.info(f"Retrieved order {order_id} for account {account_hash[:8]}...")
            return data

        except Exception as e:
            logger.error(f"Failed to get order {order_id}: {str(e)}")
            return {}

    def cancel_order(self, account_hash: str, order_id: str) -> Dict[str, Any]:
        """
        Cancel a pending order

        Args:
            account_hash: Schwab account hash value
            order_id: Order ID to cancel

        Returns:
            Cancellation result dictionary
        """
        try:
            response = self._make_request(
                'DELETE',
                f'/trader/v1/accounts/{account_hash}/orders/{order_id}'
            )

            if response.status_code == 200:
                logger.info(f"Successfully cancelled order {order_id} for account {account_hash[:8]}...")
                return {
                    'success': True,
                    'order_id': order_id,
                    'message': 'Order cancelled successfully'
                }
            else:
                error_data = response.json() if response.content else {}
                logger.error(f"Failed to cancel order {order_id}: {response.status_code} - {error_data}")
                return {
                    'success': False,
                    'order_id': order_id,
                    'status_code': response.status_code,
                    'error': error_data,
                    'message': f'Order cancellation failed with status {response.status_code}'
                }

        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {str(e)}")
            return {
                'success': False,
                'order_id': order_id,
                'message': f'Order cancellation error: {str(e)}'
            }

    def replace_order(self, account_hash: str, order_id: str, new_order_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Replace (modify) an existing order

        Args:
            account_hash: Schwab account hash value
            order_id: Order ID to replace
            new_order_data: New order specification

        Returns:
            Replacement result with new order_id
        """
        try:
            response = self._make_request(
                'PUT',
                f'/trader/v1/accounts/{account_hash}/orders/{order_id}',
                json=new_order_data
            )

            if response.status_code in [200, 201]:
                location = response.headers.get('Location', '')
                new_order_id = location.split('/')[-1] if location else None

                logger.info(f"Successfully replaced order {order_id} with {new_order_id} for account {account_hash[:8]}...")
                return {
                    'success': True,
                    'old_order_id': order_id,
                    'new_order_id': new_order_id,
                    'message': 'Order replaced successfully',
                    'location': location
                }
            else:
                error_data = response.json() if response.content else {}
                logger.error(f"Failed to replace order {order_id}: {response.status_code} - {error_data}")
                return {
                    'success': False,
                    'order_id': order_id,
                    'status_code': response.status_code,
                    'error': error_data,
                    'message': f'Order replacement failed with status {response.status_code}'
                }

        except Exception as e:
            logger.error(f"Failed to replace order {order_id}: {str(e)}")
            return {
                'success': False,
                'order_id': order_id,
                'message': f'Order replacement error: {str(e)}'
            }

    def get_all_orders(self, account_hash: str, from_date: Optional[str] = None,
                       to_date: Optional[str] = None, max_results: int = 100,
                       status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all orders for an account with filtering options

        Args:
            account_hash: Schwab account hash value
            from_date: Start date (ISO 8601 format: YYYY-MM-DDTHH:MM:SS.SSSZ)
            to_date: End date (ISO 8601 format: YYYY-MM-DDTHH:MM:SS.SSSZ)
            max_results: Maximum number of orders to return (default 100)
            status: Filter by order status (PENDING, FILLED, CANCELLED, etc.)

        Returns:
            List of order dictionaries
        """
        try:
            # Build query parameters
            params = {'maxResults': max_results}

            if from_date:
                params['fromEnteredTime'] = from_date
            else:
                # Default to last 60 days if not specified
                params['fromEnteredTime'] = (datetime.now() - timedelta(days=60)).isoformat() + 'Z'

            if to_date:
                params['toEnteredTime'] = to_date
            else:
                params['toEnteredTime'] = datetime.now().isoformat() + 'Z'

            if status:
                params['status'] = status

            response = self._make_request(
                'GET',
                f'/trader/v1/accounts/{account_hash}/orders',
                params=params
            )
            data = response.json()

            logger.info(f"Retrieved {len(data)} orders for account {account_hash[:8]}...")
            return data

        except Exception as e:
            logger.error(f"Failed to get orders for account {account_hash[:8]}...: {str(e)}")
            return []

    def get_order_executions(self, account_hash: str, order_id: str) -> List[Dict[str, Any]]:
        """
        Get execution details (fills) for a specific order

        Args:
            account_hash: Schwab account hash value
            order_id: Order ID to get executions for

        Returns:
            List of execution/fill dictionaries
        """
        try:
            # Get full order details which includes executions
            order_details = self.get_order_by_id(account_hash, order_id)

            if not order_details:
                return []

            # Extract execution legs
            executions = []
            order_legs = order_details.get('orderLegCollection', [])

            for leg in order_legs:
                leg_executions = leg.get('orderLegExecutions', [])
                for execution in leg_executions:
                    executions.append({
                        'execution_id': execution.get('executionId'),
                        'quantity': execution.get('quantity', 0),
                        'price': execution.get('price', 0.0),
                        'time': execution.get('time'),
                        'symbol': leg.get('instrument', {}).get('symbol')
                    })

            logger.info(f"Retrieved {len(executions)} executions for order {order_id}")
            return executions

        except Exception as e:
            logger.error(f"Failed to get executions for order {order_id}: {str(e)}")
            return []

    def get_account_transactions(self, account_hash: str, start_date: Optional[str] = None,
                                 end_date: Optional[str] = None, transaction_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get account transactions (trades, dividends, fees, etc.)

        Args:
            account_hash: Schwab account hash value
            start_date: Start date (YYYY-MM-DD format)
            end_date: End date (YYYY-MM-DD format)
            transaction_type: Filter by type (TRADE, DIVIDEND, INTEREST, FEE, etc.)

        Returns:
            List of transaction dictionaries
        """
        try:
            # Build query parameters
            params = {}

            if start_date:
                params['startDate'] = start_date
            else:
                # Default to last 30 days
                params['startDate'] = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

            if end_date:
                params['endDate'] = end_date
            else:
                params['endDate'] = datetime.now().strftime('%Y-%m-%d')

            if transaction_type:
                params['types'] = transaction_type

            response = self._make_request(
                'GET',
                f'/trader/v1/accounts/{account_hash}/transactions',
                params=params
            )
            data = response.json()

            logger.info(f"Retrieved {len(data)} transactions for account {account_hash[:8]}...")
            return data

        except Exception as e:
            logger.error(f"Failed to get transactions for account {account_hash[:8]}...: {str(e)}")
            return []

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