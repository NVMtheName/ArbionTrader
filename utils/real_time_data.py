"""
Real-time data fetcher for live account balances and market data
Provides authenticated API calls to get actual account values
"""

import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

class RealTimeDataFetcher:
    """Fetches real-time data from all connected APIs"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        
    def get_live_coinbase_balance(self, access_token: str) -> Dict[str, Any]:
        """Get live balance from Coinbase API"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'User-Agent': 'Arbion-Trading-Platform/1.0'
            }
            
            # Get accounts
            response = requests.get(
                'https://api.coinbase.com/v2/accounts',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                total_balance = 0
                holdings = []
                
                for account in data.get('data', []):
                    balance = account.get('balance', {})
                    amount = float(balance.get('amount', 0))
                    currency = balance.get('currency', 'USD')
                    
                    if amount > 0:
                        holdings.append({
                            'currency': currency,
                            'amount': amount,
                            'name': account.get('name', currency)
                        })
                        
                        # Convert to USD
                        if currency == 'USD':
                            total_balance += amount
                        else:
                            # Get current price for conversion
                            price = self._get_crypto_price(currency)
                            if price:
                                total_balance += amount * price
                
                return {
                    'success': True,
                    'balance': total_balance,
                    'holdings': holdings,
                    'timestamp': datetime.utcnow().isoformat()
                }
            else:
                logger.error(f"Coinbase API error: {response.status_code} - {response.text}")
                return {'success': False, 'error': f'API error: {response.status_code}'}
                
        except Exception as e:
            logger.error(f"Error fetching Coinbase balance: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_live_schwab_balance(self, access_token: str) -> Dict[str, Any]:
        """Get live balance from Schwab API using official Trader API"""
        try:
            from utils.schwab_api import SchwabAPIClient

            client = SchwabAPIClient(access_token)
            account_refs = client.get_account_numbers()
            total_balance = 0
            account_details = []

            for account_ref in account_refs:
                # Use the hashed value for API requests with display number
                hashed = account_ref.get('hash_value')
                display_number = account_ref.get('account_number')
                balance_info = client.get_account_balance(hashed, display_number)
                if balance_info:
                    total_balance += balance_info.get('account_value', 0)
                    account_details.append(balance_info)

            logger.info(f"Successfully fetched Schwab balance: ${total_balance:.2f} from {len(account_details)} accounts")
            return {
                'success': True,
                'balance': total_balance,
                'accounts': account_details,
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error fetching Schwab balance: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _get_crypto_price(self, currency: str) -> Optional[float]:
        """Get current crypto price for conversion"""
        try:
            coin_map = {
                'BTC': 'bitcoin',
                'ETH': 'ethereum',
                'LTC': 'litecoin',
                'BCH': 'bitcoin-cash'
            }
            
            coin_id = coin_map.get(currency.upper())
            if not coin_id:
                return None
                
            response = requests.get(
                f'https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd',
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get(coin_id, {}).get('usd')
                
        except Exception as e:
            logger.error(f"Error getting crypto price for {currency}: {str(e)}")
            
        return None
    
    def get_live_market_data(self, symbols: List[str]) -> Dict[str, Any]:
        """Get live market data for symbols"""
        try:
            market_data = {}
            
            for symbol in symbols:
                # Get stock data
                if symbol.upper() in ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'NVDA', 'META', 'NFLX']:
                    try:
                        # Use Alpha Vantage or similar for real-time stock data
                        # For now, using a simple quote endpoint
                        response = requests.get(
                            f'https://query1.finance.yahoo.com/v8/finance/quote?symbols={symbol}',
                            timeout=5
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            if 'quoteResponse' in data and 'result' in data['quoteResponse']:
                                quote = data['quoteResponse']['result'][0]
                                
                                price = quote.get('regularMarketPrice', 0)
                                change = quote.get('regularMarketChange', 0)
                                change_percent = quote.get('regularMarketChangePercent', 0)
                                volume = quote.get('regularMarketVolume', 0)
                                
                                market_data[symbol] = {
                                    'price': price,
                                    'change': change,
                                    'change_percent': change_percent,
                                    'volume': volume,
                                    'timestamp': datetime.utcnow().isoformat()
                                }
                    except Exception as e:
                        logger.error(f"Error fetching data for {symbol}: {str(e)}")
                        continue
                
                # Get crypto data
                elif symbol.upper() in ['BTC', 'ETH', 'LTC', 'BCH']:
                    price = self._get_crypto_price(symbol)
                    if price:
                        market_data[symbol] = {
                            'price': price,
                            'change': 0,  # Would need historical data for change
                            'change_percent': 0,
                            'volume': 0,
                            'timestamp': datetime.utcnow().isoformat()
                        }
            
            return market_data
            
        except Exception as e:
            logger.error(f"Error fetching market data: {str(e)}")
            return {}

    def get_live_schwab_positions(self, access_token: str) -> Dict[str, Any]:
        """Get live positions from Schwab accounts using official Trader API"""
        try:
            from utils.schwab_api import SchwabAPIClient

            client = SchwabAPIClient(access_token)
            account_refs = client.get_account_numbers()
            positions_data = []

            for acc_ref in account_refs:
                hashed = acc_ref.get('hash_value')
                display_number = acc_ref.get('account_number')
                positions = client.get_positions(hashed, display_number)
                positions_data.append({
                    'account_number': display_number,
                    'positions': positions,
                })

            logger.info(f"Successfully fetched Schwab positions from {len(positions_data)} accounts")
            return {
                'success': True,
                'accounts': positions_data,
                'timestamp': datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error fetching Schwab positions: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_live_etrade_balance(self, client_key: str, client_secret: str, 
                               access_token: str, access_secret: str) -> Dict[str, Any]:
        """Get live balance from E-trade API using OAuth 1.0a"""
        try:
            from utils.etrade_api import EtradeAPIClient

            client = EtradeAPIClient(client_key, client_secret, access_token, access_secret)
            accounts = client.get_account_list()
            total_balance = 0
            account_details = []

            for account in accounts:
                account_id_key = account.get('accountIdKey', '')
                account_name = account.get('accountDesc', '')
                balance_info = client.get_account_balance(account_id_key)
                
                if balance_info:
                    balance_info['account_name'] = account_name
                    total_balance += balance_info.get('account_value', 0)
                    account_details.append(balance_info)

            logger.info(f"Successfully fetched E-trade balance: ${total_balance:.2f} from {len(account_details)} accounts")
            return {
                'success': True,
                'balance': total_balance,
                'accounts': account_details,
                'timestamp': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error fetching E-trade balance: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def get_live_etrade_positions(self, client_key: str, client_secret: str, 
                                 access_token: str, access_secret: str) -> Dict[str, Any]:
        """Get live positions from E-trade accounts using OAuth 1.0a"""
        try:
            from utils.etrade_api import EtradeAPIClient

            client = EtradeAPIClient(client_key, client_secret, access_token, access_secret)
            accounts = client.get_account_list()
            positions_data = []

            for account in accounts:
                account_id_key = account.get('accountIdKey', '')
                account_name = account.get('accountDesc', '')
                positions = client.get_portfolio(account_id_key)
                positions_data.append({
                    'account_id': account_id_key,
                    'account_name': account_name,
                    'positions': positions,
                })

            logger.info(f"Successfully fetched E-trade positions from {len(positions_data)} accounts")
            return {
                'success': True,
                'accounts': positions_data,
                'timestamp': datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error fetching E-trade positions: {str(e)}")
            return {'success': False, 'error': str(e)}

