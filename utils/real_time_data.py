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
        """Get live balance from Schwab API"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            # Get accounts
            response = requests.get(
                'https://api.schwabapi.com/trader/v1/accounts',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                total_balance = 0
                account_details = []
                
                for account in data:
                    if 'securitiesAccount' in account:
                        sec_account = account['securitiesAccount']
                        account_number = sec_account.get('accountNumber', 'Unknown')
                        
                        # Get account balance
                        balance_response = requests.get(
                            f'https://api.schwabapi.com/trader/v1/accounts/{account_number}',
                            headers=headers,
                            timeout=10
                        )
                        
                        if balance_response.status_code == 200:
                            balance_data = balance_response.json()
                            sec_account_data = balance_data.get('securitiesAccount', {})
                            
                            # Get current balances
                            current_balances = sec_account_data.get('currentBalances', {})
                            account_value = current_balances.get('liquidationValue', 0)
                            cash_balance = current_balances.get('cashBalance', 0)
                            buying_power = current_balances.get('buyingPower', 0)
                            
                            total_balance += account_value
                            
                            account_details.append({
                                'account_number': account_number,
                                'account_type': sec_account_data.get('type', 'UNKNOWN'),
                                'balance': account_value,
                                'cash_balance': cash_balance,
                                'buying_power': buying_power,
                                'long_market_value': current_balances.get('longMarketValue', 0)
                            })
                
                return {
                    'success': True,
                    'balance': total_balance,
                    'accounts': account_details,
                    'timestamp': datetime.utcnow().isoformat()
                }
            else:
                logger.error(f"Schwab API error: {response.status_code} - {response.text}")
                return {'success': False, 'error': f'API error: {response.status_code}'}
                
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