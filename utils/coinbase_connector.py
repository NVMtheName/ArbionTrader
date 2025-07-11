import requests
import json
import hmac
import hashlib
import base64
import time
from datetime import datetime
import logging
from models import Trade
from app import db

class CoinbaseConnector:
    def __init__(self, api_key, secret, passphrase, sandbox=False, oauth_mode=False):
        self.api_key = api_key
        self.secret = secret
        self.passphrase = passphrase
        self.sandbox = sandbox
        self.oauth_mode = oauth_mode
        self.base_url = 'https://api-public.sandbox.pro.coinbase.com' if sandbox else 'https://api.pro.coinbase.com'
        
    def _generate_signature(self, timestamp, method, path, body=''):
        """Generate signature for Coinbase Pro API authentication"""
        if self.oauth_mode:
            # OAuth mode doesn't use signatures
            return None
            
        message = timestamp + method + path + body
        signature = hmac.new(
            base64.b64decode(self.secret),
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        return base64.b64encode(signature).decode('utf-8')
    
    def _make_request(self, method, endpoint, data=None):
        """Make authenticated request to Coinbase Pro API"""
        timestamp = str(time.time())
        path = f'/{endpoint}'
        
        body = json.dumps(data) if data else ''
        
        if self.oauth_mode:
            # OAuth mode uses Bearer token
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
        else:
            # Legacy API key mode
            signature = self._generate_signature(timestamp, method, path, body)
            headers = {
                'CB-ACCESS-KEY': self.api_key,
                'CB-ACCESS-SIGN': signature,
                'CB-ACCESS-TIMESTAMP': timestamp,
                'CB-ACCESS-PASSPHRASE': self.passphrase,
                'Content-Type': 'application/json'
            }
        
        url = f'{self.base_url}{path}'
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, headers=headers, data=body)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logging.error(f"Coinbase API request failed: {str(e)}")
            raise
    
    def test_connection(self):
        """Test API connection by fetching account info"""
        try:
            accounts = self._make_request('GET', 'accounts')
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
            return self._make_request('GET', 'accounts')
        except Exception as e:
            logging.error(f"Error fetching accounts: {str(e)}")
            return []
    
    def get_account_balance(self, currency='USD'):
        """Get balance for specific currency"""
        try:
            accounts = self.get_accounts()
            for account in accounts:
                if account['currency'] == currency:
                    return float(account['balance'])
            return 0.0
        except Exception as e:
            logging.error(f"Error fetching balance: {str(e)}")
            return 0.0
    
    def get_product_info(self, product_id):
        """Get product information"""
        try:
            return self._make_request('GET', f'products/{product_id}')
        except Exception as e:
            logging.error(f"Error fetching product info: {str(e)}")
            return None
    
    def get_current_price(self, product_id):
        """Get current price for a product"""
        try:
            ticker = self._make_request('GET', f'products/{product_id}/ticker')
            return float(ticker['price'])
        except Exception as e:
            logging.error(f"Error fetching current price: {str(e)}")
            return None
    
    def place_market_order(self, product_id, side, size=None, funds=None, user_id=None, is_simulation=False):
        """Place a market order"""
        try:
            # Validate parameters
            if not product_id or side not in ['buy', 'sell']:
                raise ValueError("Invalid product_id or side")
            
            if not size and not funds:
                raise ValueError("Either size or funds must be specified")
            
            # Prepare order data
            order_data = {
                'type': 'market',
                'side': side,
                'product_id': product_id
            }
            
            if size:
                order_data['size'] = str(size)
            if funds:
                order_data['funds'] = str(funds)
            
            # Create trade record
            trade = Trade(
                user_id=user_id,
                provider='coinbase',
                symbol=product_id,
                side=side,
                quantity=size if size else 0,
                amount=funds if funds else 0,
                trade_type='market',
                status='pending',
                is_simulation=is_simulation
            )
            
            if is_simulation:
                # Simulate the order
                current_price = self.get_current_price(product_id)
                if current_price:
                    trade.price = current_price
                    trade.status = 'executed'
                    trade.executed_at = datetime.utcnow()
                    trade.execution_details = json.dumps({
                        'simulated': True,
                        'price': current_price,
                        'message': 'Simulated market order'
                    })
                    
                    db.session.add(trade)
                    db.session.commit()
                    
                    return {
                        'success': True,
                        'message': f'Simulated {side} order for {product_id}',
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
                response = self._make_request('POST', 'orders', order_data)
                
                trade.status = 'executed'
                trade.executed_at = datetime.utcnow()
                trade.execution_details = json.dumps(response)
                
                db.session.add(trade)
                db.session.commit()
                
                return {
                    'success': True,
                    'message': f'Market order placed successfully',
                    'order_id': response['id'],
                    'trade_id': trade.id
                }
        
        except Exception as e:
            if 'trade' in locals():
                trade.status = 'failed'
                trade.execution_details = json.dumps({'error': str(e)})
                db.session.add(trade)
                db.session.commit()
            
            logging.error(f"Error placing market order: {str(e)}")
            return {
                'success': False,
                'message': f'Order failed: {str(e)}'
            }
    
    def place_limit_order(self, product_id, side, size, price, user_id=None, is_simulation=False):
        """Place a limit order"""
        try:
            # Validate parameters
            if not all([product_id, side, size, price]):
                raise ValueError("All parameters (product_id, side, size, price) are required")
            
            if side not in ['buy', 'sell']:
                raise ValueError("Invalid side")
            
            # Prepare order data
            order_data = {
                'type': 'limit',
                'side': side,
                'product_id': product_id,
                'size': str(size),
                'price': str(price)
            }
            
            # Create trade record
            trade = Trade(
                user_id=user_id,
                provider='coinbase',
                symbol=product_id,
                side=side,
                quantity=size,
                price=price,
                trade_type='limit',
                status='pending',
                is_simulation=is_simulation
            )
            
            if is_simulation:
                # Simulate the order
                trade.status = 'executed'
                trade.executed_at = datetime.utcnow()
                trade.execution_details = json.dumps({
                    'simulated': True,
                    'price': price,
                    'message': 'Simulated limit order'
                })
                
                db.session.add(trade)
                db.session.commit()
                
                return {
                    'success': True,
                    'message': f'Simulated {side} limit order for {product_id}',
                    'order_id': f'sim_{trade.id}',
                    'trade_id': trade.id
                }
            else:
                # Execute real order
                response = self._make_request('POST', 'orders', order_data)
                
                trade.status = 'executed'
                trade.executed_at = datetime.utcnow()
                trade.execution_details = json.dumps(response)
                
                db.session.add(trade)
                db.session.commit()
                
                return {
                    'success': True,
                    'message': f'Limit order placed successfully',
                    'order_id': response['id'],
                    'trade_id': trade.id
                }
        
        except Exception as e:
            if 'trade' in locals():
                trade.status = 'failed'
                trade.execution_details = json.dumps({'error': str(e)})
                db.session.add(trade)
                db.session.commit()
            
            logging.error(f"Error placing limit order: {str(e)}")
            return {
                'success': False,
                'message': f'Order failed: {str(e)}'
            }
    
    def get_order_status(self, order_id):
        """Get order status"""
        try:
            return self._make_request('GET', f'orders/{order_id}')
        except Exception as e:
            logging.error(f"Error fetching order status: {str(e)}")
            return None
    
    def cancel_order(self, order_id):
        """Cancel an order"""
        try:
            return self._make_request('DELETE', f'orders/{order_id}')
        except Exception as e:
            logging.error(f"Error cancelling order: {str(e)}")
            return None
