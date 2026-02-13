"""
Schwabdev Routes for Arbion Trading Platform
Flask endpoints for Schwab API integration using Schwabdev library
"""

from flask import Blueprint, request, jsonify, redirect, url_for, session
from flask_login import login_required, current_user
import logging
from datetime import datetime, timedelta
from utils.schwabdev_integration import create_schwabdev_manager, get_schwabdev_info

logger = logging.getLogger(__name__)

# Create blueprint for Schwabdev routes
schwabdev_bp = Blueprint('schwabdev', __name__)

@schwabdev_bp.route('/api/schwabdev/info', methods=['GET'])
@login_required
def get_schwabdev_integration_info():
    """Get information about Schwabdev integration"""
    try:
        info = get_schwabdev_info()
        return jsonify({
            'success': True,
            'schwabdev_info': info
        })
    
    except Exception as e:
        logger.error(f"Error getting Schwabdev info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schwabdev_bp.route('/api/schwabdev/status', methods=['GET'])
@login_required
def get_schwabdev_status():
    """Get Schwabdev connection status"""
    try:
        manager = create_schwabdev_manager(str(current_user.id))
        status = manager.get_connection_status()
        
        return jsonify({
            'success': True,
            'connection_status': status
        })
    
    except Exception as e:
        logger.error(f"Error getting Schwabdev status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schwabdev_bp.route('/api/schwabdev/auth/start', methods=['POST'])
@login_required
def start_schwab_authorization():
    """Start Schwab OAuth authorization process"""
    try:
        manager = create_schwabdev_manager(str(current_user.id))
        auth_result = manager.get_authorization_url()
        
        if auth_result.get('success'):
            return jsonify({
                'success': True,
                'authorization_url': auth_result['authorization_url'],
                'message': 'Visit the authorization URL to complete Schwab authentication'
            })
        else:
            return jsonify({
                'success': False,
                'error': auth_result.get('error', 'Failed to get authorization URL')
            }), 400
    
    except Exception as e:
        logger.error(f"Error starting Schwab authorization: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schwabdev_bp.route('/api/schwabdev/auth/callback', methods=['POST'])
@login_required
def handle_schwab_callback():
    """Handle Schwab OAuth callback with authorization code"""
    try:
        data = request.get_json()
        authorization_code = data.get('code')
        
        if not authorization_code:
            return jsonify({
                'success': False,
                'error': 'Authorization code is required'
            }), 400
        
        manager = create_schwabdev_manager(str(current_user.id))
        token_result = manager.exchange_code_for_tokens(authorization_code)
        
        return jsonify(token_result)
    
    except Exception as e:
        logger.error(f"Error handling Schwab callback: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schwabdev_bp.route('/api/schwabdev/auth/refresh', methods=['POST'])
@login_required
def refresh_schwab_tokens():
    """Refresh Schwab access tokens"""
    try:
        manager = create_schwabdev_manager(str(current_user.id))
        refresh_result = manager.refresh_access_token()
        
        return jsonify(refresh_result)
    
    except Exception as e:
        logger.error(f"Error refreshing Schwab tokens: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schwabdev_bp.route('/api/schwabdev/accounts', methods=['GET'])
@login_required
def get_schwab_accounts():
    """Get Schwab account information"""
    try:
        account_number = request.args.get('account_number')
        
        manager = create_schwabdev_manager(str(current_user.id))
        account_result = manager.get_account_info(account_number)
        
        return jsonify(account_result)
    
    except Exception as e:
        logger.error(f"Error getting Schwab accounts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schwabdev_bp.route('/api/schwabdev/quotes/<symbol>', methods=['GET'])
@login_required
def get_schwab_quote(symbol):
    """Get market data for a specific symbol"""
    try:
        manager = create_schwabdev_manager(str(current_user.id))
        quote_result = manager.get_market_data(symbol.upper())
        
        return jsonify(quote_result)
    
    except Exception as e:
        logger.error(f"Error getting Schwab quote for {symbol}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schwabdev_bp.route('/api/schwabdev/quotes', methods=['POST'])
@login_required
def get_schwab_multiple_quotes():
    """Get market data for multiple symbols"""
    try:
        data = request.get_json()
        symbols = data.get('symbols', [])
        
        if not symbols:
            return jsonify({
                'success': False,
                'error': 'Symbols list is required'
            }), 400
        
        # Convert to uppercase and limit to reasonable number
        symbols = [symbol.upper() for symbol in symbols[:50]]  # Limit to 50 symbols
        
        manager = create_schwabdev_manager(str(current_user.id))
        quotes_result = manager.get_multiple_quotes(symbols)
        
        return jsonify(quotes_result)
    
    except Exception as e:
        logger.error(f"Error getting multiple Schwab quotes: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schwabdev_bp.route('/api/schwabdev/orders', methods=['GET'])
@login_required
def get_schwab_orders():
    """Get Schwab order history"""
    try:
        account_number = request.args.get('account_number')
        from_date_str = request.args.get('from_date')
        to_date_str = request.args.get('to_date')
        
        # Parse dates if provided
        from_date = None
        to_date = None
        
        if from_date_str:
            from_date = datetime.fromisoformat(from_date_str)
        
        if to_date_str:
            to_date = datetime.fromisoformat(to_date_str)
        
        manager = create_schwabdev_manager(str(current_user.id))
        orders_result = manager.get_orders(account_number, from_date, to_date)
        
        return jsonify(orders_result)
    
    except Exception as e:
        logger.error(f"Error getting Schwab orders: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schwabdev_bp.route('/api/schwabdev/orders', methods=['POST'])
@login_required
def place_schwab_order():
    """Place a Schwab trading order"""
    try:
        data = request.get_json()
        account_number = data.get('account_number')
        order_data = data.get('order_data')
        
        if not account_number or not order_data:
            return jsonify({
                'success': False,
                'error': 'Account number and order data are required'
            }), 400
        
        manager = create_schwabdev_manager(str(current_user.id))
        order_result = manager.place_order(account_number, order_data)
        
        return jsonify(order_result)
    
    except Exception as e:
        logger.error(f"Error placing Schwab order: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schwabdev_bp.route('/api/schwabdev/orders/<order_id>', methods=['DELETE'])
@login_required
def cancel_schwab_order(order_id):
    """Cancel a Schwab order"""
    try:
        account_number = request.args.get('account_number')
        
        if not account_number:
            return jsonify({
                'success': False,
                'error': 'Account number is required'
            }), 400
        
        manager = create_schwabdev_manager(str(current_user.id))
        cancel_result = manager.cancel_order(account_number, order_id)
        
        return jsonify(cancel_result)
    
    except Exception as e:
        logger.error(f"Error cancelling Schwab order {order_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schwabdev_bp.route('/api/schwabdev/watchlists', methods=['GET'])
@login_required
def get_schwab_watchlists():
    """Get Schwab watchlists"""
    try:
        account_number = request.args.get('account_number')
        
        if not account_number:
            return jsonify({
                'success': False,
                'error': 'Account number is required'
            }), 400
        
        manager = create_schwabdev_manager(str(current_user.id))
        watchlists_result = manager.get_watchlists(account_number)
        
        return jsonify(watchlists_result)
    
    except Exception as e:
        logger.error(f"Error getting Schwab watchlists: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schwabdev_bp.route('/api/schwabdev/test-connection', methods=['POST'])
@login_required
def test_schwab_connection():
    """Run full connection diagnostics against the Schwab API"""
    try:
        manager = create_schwabdev_manager(str(current_user.id))
        test_result = manager.test_connection()

        return jsonify({
            'success': True,
            'test_results': test_result
        })

    except Exception as e:
        logger.error(f"Error testing Schwab connection: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schwabdev_bp.route('/api/schwabdev/price-history/<symbol>', methods=['GET'])
@login_required
def get_schwab_price_history(symbol):
    """Get historical price data for a symbol (useful for ML training)"""
    try:
        period_type = request.args.get('period_type', 'month')
        period = int(request.args.get('period', 3))
        frequency_type = request.args.get('frequency_type', 'daily')
        frequency = int(request.args.get('frequency', 1))

        manager = create_schwabdev_manager(str(current_user.id))
        history_result = manager.get_price_history(
            symbol=symbol.upper(),
            period_type=period_type,
            period=period,
            frequency_type=frequency_type,
            frequency=frequency
        )

        return jsonify(history_result)

    except Exception as e:
        logger.error(f"Error getting price history for {symbol}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schwabdev_bp.route('/api/schwabdev/demo', methods=['POST'])
@login_required
def demo_schwabdev_integration():
    """
    Comprehensive demo of Schwabdev integration capabilities
    Shows connection status, account data, and market data retrieval
    """
    try:
        manager = create_schwabdev_manager(str(current_user.id))
        
        demo_results = []
        
        # Test 1: Connection status
        connection_status = manager.get_connection_status()
        demo_results.append({
            'test': 'connection_status',
            'result': connection_status
        })
        
        # Test 2: Authorization URL (if not authenticated)
        if not connection_status.get('has_access_token'):
            auth_result = manager.get_authorization_url()
            demo_results.append({
                'test': 'authorization_url',
                'result': auth_result
            })
        
        # Test 3: Account info (if authenticated)
        if connection_status.get('has_access_token'):
            account_result = manager.get_account_info()
            demo_results.append({
                'test': 'account_info',
                'result': {
                    'success': account_result.get('success'),
                    'has_data': bool(account_result.get('account_info')),
                    'error': account_result.get('error')
                }
            })
            
            # Test 4: Market data
            market_result = manager.get_market_data('AAPL')
            demo_results.append({
                'test': 'market_data',
                'result': {
                    'success': market_result.get('success'),
                    'symbol': 'AAPL',
                    'has_data': bool(market_result.get('market_data')),
                    'error': market_result.get('error')
                }
            })
        
        return jsonify({
            'success': True,
            'message': 'Schwabdev integration demo completed',
            'demo_results': demo_results,
            'tests_completed': len(demo_results)
        })
    
    except Exception as e:
        logger.error(f"Error in Schwabdev demo: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@schwabdev_bp.route('/api/schwabdev/setup-guide', methods=['GET'])
def get_schwabdev_setup_guide():
    """Get Schwabdev setup guide and instructions"""
    try:
        setup_guide = {
            'prerequisites': [
                'Schwab brokerage account with API access enabled',
                'Registered Schwab developer application',
                'Valid app key and app secret from Schwab'
            ],
            'environment_variables': [
                {
                    'name': 'SCHWAB_APP_KEY',
                    'description': 'Your Schwab application key',
                    'required': True
                },
                {
                    'name': 'SCHWAB_APP_SECRET', 
                    'description': 'Your Schwab application secret',
                    'required': True
                },
                {
                    'name': 'SCHWAB_CALLBACK_URL',
                    'description': 'OAuth callback URL (default: https://127.0.0.1)',
                    'required': False
                }
            ],
            'setup_steps': [
                {
                    'step': 1,
                    'title': 'Register with Schwab Developer',
                    'description': 'Create a developer account and register your application',
                    'url': 'https://developer.schwab.com/'
                },
                {
                    'step': 2,
                    'title': 'Get API Credentials',
                    'description': 'Obtain your app key and app secret from the developer portal'
                },
                {
                    'step': 3,
                    'title': 'Set Environment Variables',
                    'description': 'Add SCHWAB_APP_KEY and SCHWAB_APP_SECRET to your environment'
                },
                {
                    'step': 4,
                    'title': 'Start OAuth Flow',
                    'description': 'Use /api/schwabdev/auth/start to begin authorization'
                },
                {
                    'step': 5,
                    'title': 'Complete Authorization',
                    'description': 'Follow the authorization URL and submit the code to /api/schwabdev/auth/callback'
                }
            ],
            'api_endpoints': [
                'GET /api/schwabdev/info - Integration information',
                'GET /api/schwabdev/status - Connection status',
                'POST /api/schwabdev/auth/start - Start OAuth flow',
                'POST /api/schwabdev/auth/callback - Handle OAuth callback',
                'POST /api/schwabdev/auth/refresh - Refresh tokens',
                'GET /api/schwabdev/accounts - Get account information',
                'GET /api/schwabdev/quotes/<symbol> - Get single quote',
                'POST /api/schwabdev/quotes - Get multiple quotes',
                'GET /api/schwabdev/orders - Get order history',
                'POST /api/schwabdev/orders - Place order',
                'DELETE /api/schwabdev/orders/<id> - Cancel order',
                'GET /api/schwabdev/watchlists - Get watchlists',
                'POST /api/schwabdev/test-connection - Run connection diagnostics',
                'GET /api/schwabdev/price-history/<symbol> - Get historical price data'
            ],
            'troubleshooting': {
                'library_not_available': {
                    'issue': 'Schwabdev library not installed',
                    'solution': 'Install with: pip install schwabdev'
                },
                'credentials_missing': {
                    'issue': 'Schwab API credentials not configured',
                    'solution': 'Set SCHWAB_APP_KEY and SCHWAB_APP_SECRET environment variables'
                },
                'authentication_failed': {
                    'issue': 'OAuth authentication failed',
                    'solution': 'Verify app credentials and complete OAuth flow properly'
                },
                'token_expired': {
                    'issue': 'Access token expired',
                    'solution': 'Use refresh endpoint to get new access token'
                }
            }
        }
        
        return jsonify({
            'success': True,
            'setup_guide': setup_guide
        })
    
    except Exception as e:
        logger.error(f"Error getting setup guide: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500