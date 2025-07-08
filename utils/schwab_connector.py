import requests
import json
import time
from datetime import datetime
import logging
from models import Trade
from app import db

class SchwabConnector:
    def __init__(self, api_key, secret, sandbox=False):
        self.api_key = api_key
        self.secret = secret
        self.sandbox = sandbox
        self.base_url = 'https://api.schwabapi.com' if not sandbox else 'https://api-sandbox.schwabapi.com'
        self.access_token = None
        self.refresh_token = None
        
    def _get_access_token(self):
        """Get access token using OAuth2"""
        try:
            # This is a simplified implementation
            # In production, you'd need to implement the full OAuth2 flow
            auth_url = f'{self.base_url}/oauth/token'
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f'Basic {self.api_key}'
            }
            
            data = {
                'grant_type': 'client_credentials',
                'scope': 'read'
            }
            
            response = requests.post(auth_url, headers=headers, data=data)
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data['access_token']
            self.refresh_token = token_data.get('refresh_token')
            
            return True
        
        except Exception as e:
            logging.error(f"Error getting Schwab access token: {str(e)}")
            return False
    
    def _make_request(self, method, endpoint, data=None):
        """Make authenticated request to Schwab API"""
        if not self.access_token:
            if not self._get_access_token():
                raise Exception("Failed to get access token")
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        url = f'{self.base_url}/{endpoint}'
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=data)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logging.error(f"Schwab API request failed: {str(e)}")
            raise
    
    def test_connection(self):
        """Test API connection by fetching account info"""
        try:
            # Try to get accounts to test connection
            accounts = self._make_request('GET', 'trader/v1/accounts')
            return {
                'success': True,
                'message': f'Connected successfully. Found {len(accounts)} accounts.'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Connection failed: {str(e)}'
            }
    
    def get_accounts(self):
        """Get all accounts"""
        try:
            return self._make_request('GET', 'trader/v1/accounts')
        except Exception as e:
            logging.error(f"Error fetching accounts: {str(e)}")
            return []
    
    def get_account_info(self, account_id):
        """Get specific account information"""
        try:
            return self._make_request('GET', f'trader/v1/accounts/{account_id}')
        except Exception as e:
            logging.error(f"Error fetching account info: {str(e)}")
            return None
    
    def get_positions(self, account_id):
        """Get account positions"""
        try:
            return self._make_request('GET', f'trader/v1/accounts/{account_id}/positions')
        except Exception as e:
            logging.error(f"Error fetching positions: {str(e)}")
            return []
    
    def get_quote(self, symbol):
        """Get quote for a symbol"""
        try:
            return self._make_request('GET', f'marketdata/v1/quotes/{symbol}')
        except Exception as e:
            logging.error(f"Error fetching quote: {str(e)}")
            return None
    
    def get_current_price(self, symbol):
        """Get current price for a symbol"""
        try:
            quote = self.get_quote(symbol)
            if quote and symbol in quote:
                return quote[symbol]['last']
            return None
        except Exception as e:
            logging.error(f"Error fetching current price: {str(e)}")
            return None
    
    def place_equity_order(self, account_id, symbol, quantity, side, order_type='MARKET', price=None, user_id=None, is_simulation=False):
        """Place an equity order"""
        try:
            # Validate parameters
            if not all([account_id, symbol, quantity, side]):
                raise ValueError("All parameters (account_id, symbol, quantity, side) are required")
            
            if side not in ['BUY', 'SELL']:
                raise ValueError("Invalid side, must be BUY or SELL")
            
            if order_type not in ['MARKET', 'LIMIT', 'STOP']:
                raise ValueError("Invalid order type")
            
            # Prepare order data
            order_data = {
                'orderType': order_type,
                'session': 'NORMAL',
                'duration': 'DAY',
                'orderStrategyType': 'SINGLE',
                'orderLegCollection': [{
                    'instruction': side,
                    'quantity': quantity,
                    'instrument': {
                        'symbol': symbol,
                        'assetType': 'EQUITY'
                    }
                }]
            }
            
            if order_type == 'LIMIT' and price:
                order_data['price'] = price
            
            # Create trade record
            trade = Trade(
                user_id=user_id,
                provider='schwab',
                symbol=symbol,
                side=side.lower(),
                quantity=quantity,
                price=price,
                trade_type=order_type.lower(),
                status='pending',
                is_simulation=is_simulation
            )
            
            if is_simulation:
                # Simulate the order
                current_price = self.get_current_price(symbol)
                if current_price:
                    trade.price = current_price
                    trade.status = 'executed'
                    trade.executed_at = datetime.utcnow()
                    trade.execution_details = json.dumps({
                        'simulated': True,
                        'price': current_price,
                        'message': f'Simulated {order_type} order'
                    })
                    
                    db.session.add(trade)
                    db.session.commit()
                    
                    return {
                        'success': True,
                        'message': f'Simulated {side} order for {symbol}',
                        'order_id': f'sim_{trade.id}',
                        'trade_id': trade.id
                    }
                else:
                    trade.status = 'failed'
                    trade.execution_details = json.dumps({
                        'error': 'Could not fetch current price for simulation'
                    })
                    db.session.add(trade)
                    db.session.commit()
                    
                    return {
                        'success': False,
                        'message': 'Simulation failed: Could not fetch current price'
                    }
            else:
                # Execute real order
                response = self._make_request('POST', f'trader/v1/accounts/{account_id}/orders', order_data)
                
                trade.status = 'executed'
                trade.executed_at = datetime.utcnow()
                trade.execution_details = json.dumps(response)
                
                db.session.add(trade)
                db.session.commit()
                
                return {
                    'success': True,
                    'message': f'{order_type} order placed successfully',
                    'order_id': response.get('orderId'),
                    'trade_id': trade.id
                }
        
        except Exception as e:
            if 'trade' in locals():
                trade.status = 'failed'
                trade.execution_details = json.dumps({'error': str(e)})
                db.session.add(trade)
                db.session.commit()
            
            logging.error(f"Error placing equity order: {str(e)}")
            return {
                'success': False,
                'message': f'Order failed: {str(e)}'
            }
    
    def place_option_order(self, account_id, symbol, quantity, side, option_type, strike, expiration, user_id=None, is_simulation=False):
        """Place an option order"""
        try:
            # Validate parameters
            if not all([account_id, symbol, quantity, side, option_type, strike, expiration]):
                raise ValueError("All parameters are required for option orders")
            
            if side not in ['BUY_TO_OPEN', 'SELL_TO_OPEN', 'BUY_TO_CLOSE', 'SELL_TO_CLOSE']:
                raise ValueError("Invalid option side")
            
            if option_type not in ['CALL', 'PUT']:
                raise ValueError("Invalid option type")
            
            # Prepare order data
            order_data = {
                'orderType': 'MARKET',
                'session': 'NORMAL',
                'duration': 'DAY',
                'orderStrategyType': 'SINGLE',
                'orderLegCollection': [{
                    'instruction': side,
                    'quantity': quantity,
                    'instrument': {
                        'symbol': symbol,
                        'assetType': 'OPTION',
                        'optionType': option_type,
                        'strikePrice': strike,
                        'expirationDate': expiration
                    }
                }]
            }
            
            # Create trade record
            trade = Trade(
                user_id=user_id,
                provider='schwab',
                symbol=f"{symbol}_{option_type}_{strike}_{expiration}",
                side=side.lower(),
                quantity=quantity,
                trade_type='option',
                status='pending',
                is_simulation=is_simulation
            )
            
            if is_simulation:
                # Simulate the order
                trade.status = 'executed'
                trade.executed_at = datetime.utcnow()
                trade.execution_details = json.dumps({
                    'simulated': True,
                    'message': f'Simulated option order'
                })
                
                db.session.add(trade)
                db.session.commit()
                
                return {
                    'success': True,
                    'message': f'Simulated option order for {symbol}',
                    'order_id': f'sim_{trade.id}',
                    'trade_id': trade.id
                }
            else:
                # Execute real order
                response = self._make_request('POST', f'trader/v1/accounts/{account_id}/orders', order_data)
                
                trade.status = 'executed'
                trade.executed_at = datetime.utcnow()
                trade.execution_details = json.dumps(response)
                
                db.session.add(trade)
                db.session.commit()
                
                return {
                    'success': True,
                    'message': f'Option order placed successfully',
                    'order_id': response.get('orderId'),
                    'trade_id': trade.id
                }
        
        except Exception as e:
            if 'trade' in locals():
                trade.status = 'failed'
                trade.execution_details = json.dumps({'error': str(e)})
                db.session.add(trade)
                db.session.commit()
            
            logging.error(f"Error placing option order: {str(e)}")
            return {
                'success': False,
                'message': f'Order failed: {str(e)}'
            }
    
    def get_order_status(self, account_id, order_id):
        """Get order status"""
        try:
            return self._make_request('GET', f'trader/v1/accounts/{account_id}/orders/{order_id}')
        except Exception as e:
            logging.error(f"Error fetching order status: {str(e)}")
            return None
    
    def cancel_order(self, account_id, order_id):
        """Cancel an order"""
        try:
            return self._make_request('DELETE', f'trader/v1/accounts/{account_id}/orders/{order_id}')
        except Exception as e:
            logging.error(f"Error cancelling order: {str(e)}")
            return None
