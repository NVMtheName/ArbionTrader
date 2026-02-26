"""
Schwab API Routes for Arbion Trading Platform
Flask endpoints for Schwab API integration using both schwab-py and schwabdev libraries
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
    """Get Schwab API setup guide and instructions"""
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
            'api_endpoints': {
                'auth': [
                    'POST /api/schwabdev/auth/start - Start OAuth flow',
                    'POST /api/schwabdev/auth/callback - Handle OAuth callback',
                    'POST /api/schwabdev/auth/refresh - Refresh tokens',
                ],
                'accounts': [
                    'GET /api/schwabdev/accounts - Get account information',
                    'GET /api/schwabdev/transactions - Get transaction history',
                    'GET /api/schwabdev/preferences - Get user preferences',
                ],
                'market_data': [
                    'GET /api/schwabdev/quotes/<symbol> - Get single quote',
                    'POST /api/schwabdev/quotes - Get multiple quotes',
                    'GET /api/schwabdev/price-history/<symbol> - Historical price data',
                    'GET /api/schwabdev/option-chain/<symbol> - Options chain data',
                    'GET /api/schwabdev/movers/<index> - Top market movers',
                    'GET /api/schwabdev/market-hours - Market hours',
                    'GET /api/schwabdev/instruments/search - Instrument search',
                ],
                'trading': [
                    'GET /api/schwabdev/orders - Get order history',
                    'POST /api/schwabdev/orders - Place order',
                    'PUT /api/schwabdev/orders/<id> - Replace order',
                    'DELETE /api/schwabdev/orders/<id> - Cancel order',
                    'POST /api/schwabdev/orders/build - Build order from params',
                    'POST /api/schwabdev/orders/build-bracket - Build bracket order',
                    'POST /api/schwabdev/orders/preview - Preview order',
                ],
                'streaming': [
                    'GET /api/schwabdev/streaming/status - Streaming status',
                    'POST /api/schwabdev/streaming/subscribe - Subscribe to streams',
                    'POST /api/schwabdev/streaming/unsubscribe - Unsubscribe',
                    'POST /api/schwabdev/streaming/start - Start streaming',
                    'POST /api/schwabdev/streaming/stop - Stop streaming',
                    'GET /api/schwabdev/streaming/data/<type> - Get buffered data',
                ],
                'diagnostics': [
                    'GET /api/schwabdev/info - Integration information',
                    'GET /api/schwabdev/status - Connection status',
                    'POST /api/schwabdev/test-connection - Run diagnostics',
                    'GET /api/schwabdev/setup-guide - This guide',
                ],
            },
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


# =============================================================================
# NEW: Market Movers Endpoint
# =============================================================================

@schwabdev_bp.route('/api/schwabdev/movers/<index>', methods=['GET'])
@login_required
def get_schwab_movers(index):
    """Get top market movers for an index (DJI, SPX, COMPX, NYSE, NASDAQ)"""
    try:
        sort_order = request.args.get('sort_order')
        frequency = request.args.get('frequency', type=int)

        manager = create_schwabdev_manager(str(current_user.id))
        result = manager.get_movers(index.upper(), sort_order, frequency)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting movers for {index}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# NEW: Market Hours Endpoint
# =============================================================================

@schwabdev_bp.route('/api/schwabdev/market-hours', methods=['GET'])
@login_required
def get_schwab_market_hours():
    """Get market hours for specified markets (EQUITY, OPTION, BOND, FUTURE, FOREX)"""
    try:
        markets_param = request.args.get('markets', 'EQUITY,OPTION')
        markets = [m.strip().upper() for m in markets_param.split(',')]
        date = request.args.get('date')

        manager = create_schwabdev_manager(str(current_user.id))
        result = manager.get_market_hours(markets, date)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting market hours: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# NEW: Instrument Search Endpoint
# =============================================================================

@schwabdev_bp.route('/api/schwabdev/instruments/search', methods=['GET'])
@login_required
def search_schwab_instruments():
    """Search for instruments by symbol or description"""
    try:
        query = request.args.get('query', '')
        projection = request.args.get('projection', 'SYMBOL_SEARCH')

        if not query:
            return jsonify({'success': False, 'error': 'Query parameter required'}), 400

        manager = create_schwabdev_manager(str(current_user.id))
        result = manager.search_instruments(query, projection)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error searching instruments: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# NEW: Transactions Endpoint
# =============================================================================

@schwabdev_bp.route('/api/schwabdev/transactions', methods=['GET'])
@login_required
def get_schwab_transactions():
    """Get transaction history"""
    try:
        account_number = request.args.get('account_number')
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        transaction_type = request.args.get('type')

        start_date = datetime.fromisoformat(start_date_str) if start_date_str else None
        end_date = datetime.fromisoformat(end_date_str) if end_date_str else None

        manager = create_schwabdev_manager(str(current_user.id))
        result = manager.get_transactions(account_number, start_date, end_date, transaction_type)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting transactions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# NEW: User Preferences Endpoint
# =============================================================================

@schwabdev_bp.route('/api/schwabdev/preferences', methods=['GET'])
@login_required
def get_schwab_preferences():
    """Get user preferences"""
    try:
        manager = create_schwabdev_manager(str(current_user.id))
        result = manager.get_user_preferences()
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting preferences: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# NEW: Option Chain Endpoint
# =============================================================================

@schwabdev_bp.route('/api/schwabdev/option-chain/<symbol>', methods=['GET'])
@login_required
def get_schwab_option_chain(symbol):
    """Get option chain data for a symbol"""
    try:
        contract_type = request.args.get('contract_type', 'ALL')
        strike_count = request.args.get('strike_count', 10, type=int)
        strategy = request.args.get('strategy', 'SINGLE')

        manager = create_schwabdev_manager(str(current_user.id))

        # Try schwab-py client first (has strategy support)
        if manager.schwab_py_client and manager.schwab_py_client.is_available:
            result = manager.schwab_py_client.get_option_chain(
                symbol.upper(), contract_type, strike_count, strategy
            )
            if result.get('success'):
                return jsonify(result)

        # Fallback to existing method
        result = manager.get_option_chain(symbol.upper(), contract_type, strike_count)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting option chain for {symbol}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# NEW: Order Builder Endpoints
# =============================================================================

@schwabdev_bp.route('/api/schwabdev/orders/build', methods=['POST'])
@login_required
def build_schwab_order():
    """Build an order using schwab-py order templates (does NOT place it)"""
    try:
        from utils.schwab_order_builder import create_order_builder

        data = request.get_json()
        builder = create_order_builder()

        if not builder.is_available:
            return jsonify({
                'success': False,
                'error': 'schwab-py order templates not available'
            }), 400

        order_type_param = data.get('instrument_type', 'equity').lower()

        if order_type_param == 'equity':
            result = builder.build_equity_order(
                symbol=data.get('symbol', ''),
                quantity=int(data.get('quantity', 0)),
                side=data.get('side', 'BUY'),
                order_type=data.get('order_type', 'MARKET'),
                price=data.get('price'),
                duration=data.get('duration', 'DAY'),
                session_type=data.get('session', 'NORMAL'),
            )

        elif order_type_param == 'option':
            result = builder.build_option_order(
                option_symbol=data.get('option_symbol', ''),
                quantity=int(data.get('quantity', 0)),
                action=data.get('action', 'BUY_TO_OPEN'),
                order_type=data.get('order_type', 'MARKET'),
                price=data.get('price'),
                duration=data.get('duration', 'DAY'),
                session_type=data.get('session', 'NORMAL'),
            )

        elif order_type_param == 'spread':
            result = builder.build_vertical_spread(
                spread_type=data.get('spread_type', ''),
                long_symbol=data.get('long_symbol', ''),
                short_symbol=data.get('short_symbol', ''),
                quantity=int(data.get('quantity', 0)),
                net_price=float(data.get('net_price', 0)),
                action=data.get('action', 'OPEN'),
            )

        elif order_type_param == 'natural_language':
            result = builder.build_from_natural_language(data.get('text', ''))

        else:
            return jsonify({
                'success': False,
                'error': f'Unknown instrument_type: {order_type_param}'
            }), 400

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error building order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@schwabdev_bp.route('/api/schwabdev/orders/build-bracket', methods=['POST'])
@login_required
def build_schwab_bracket_order():
    """Build a bracket order (entry + take-profit + stop-loss)"""
    try:
        from utils.schwab_order_builder import create_order_builder

        data = request.get_json()
        builder = create_order_builder()

        if not builder.is_available:
            return jsonify({
                'success': False,
                'error': 'schwab-py order templates not available'
            }), 400

        result = builder.build_bracket_order(
            symbol=data.get('symbol', ''),
            quantity=int(data.get('quantity', 0)),
            side=data.get('side', 'BUY'),
            entry_price=float(data.get('entry_price', 0)),
            take_profit_price=float(data.get('take_profit_price', 0)),
            stop_loss_price=float(data.get('stop_loss_price', 0)),
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error building bracket order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@schwabdev_bp.route('/api/schwabdev/orders/build-info', methods=['GET'])
@login_required
def get_order_builder_info():
    """Get order builder capabilities"""
    try:
        from utils.schwab_order_builder import get_order_builder_info as get_info
        return jsonify({'success': True, 'order_builder': get_info()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@schwabdev_bp.route('/api/schwabdev/orders/<order_id>', methods=['PUT'])
@login_required
def replace_schwab_order(order_id):
    """Replace an existing order"""
    try:
        data = request.get_json()
        account_number = data.get('account_number')
        order_data = data.get('order_data')

        if not account_number or not order_data:
            return jsonify({
                'success': False,
                'error': 'account_number and order_data are required'
            }), 400

        manager = create_schwabdev_manager(str(current_user.id))
        result = manager.replace_order(account_number, order_id, order_data)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error replacing order {order_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@schwabdev_bp.route('/api/schwabdev/orders/preview', methods=['POST'])
@login_required
def preview_schwab_order():
    """Preview an order before placing it"""
    try:
        data = request.get_json()
        account_number = data.get('account_number')
        order_data = data.get('order_data')

        if not account_number or not order_data:
            return jsonify({
                'success': False,
                'error': 'account_number and order_data are required'
            }), 400

        manager = create_schwabdev_manager(str(current_user.id))
        result = manager.preview_order(account_number, order_data)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error previewing order: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# NEW: Streaming Endpoints
# =============================================================================

@schwabdev_bp.route('/api/schwabdev/streaming/status', methods=['GET'])
@login_required
def get_streaming_status():
    """Get streaming service status"""
    try:
        from utils.schwab_streaming import get_streaming_service, get_streaming_info

        service = get_streaming_service(current_user.id)
        status = service.get_status()
        info = get_streaming_info()

        return jsonify({
            'success': True,
            'status': status,
            'capabilities': info,
        })

    except Exception as e:
        logger.error(f"Error getting streaming status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@schwabdev_bp.route('/api/schwabdev/streaming/subscribe', methods=['POST'])
@login_required
def subscribe_streaming():
    """Subscribe to a streaming data type"""
    try:
        from utils.schwab_streaming import get_streaming_service

        data = request.get_json()
        stream_type = data.get('stream_type', '')
        symbols = data.get('symbols', [])

        service = get_streaming_service(current_user.id)

        subscribe_methods = {
            'level_one_equity': service.subscribe_level_one_equity,
            'level_one_option': service.subscribe_level_one_option,
            'level_one_futures': service.subscribe_level_one_futures,
            'level_one_forex': service.subscribe_level_one_forex,
            'chart_equity': service.subscribe_chart_equity,
            'chart_futures': service.subscribe_chart_futures,
            'nyse_book': service.subscribe_nyse_book,
            'nasdaq_book': service.subscribe_nasdaq_book,
            'account_activity': service.subscribe_account_activity,
        }

        method = subscribe_methods.get(stream_type)
        if not method:
            return jsonify({
                'success': False,
                'error': f'Unknown stream type: {stream_type}',
                'available_types': list(subscribe_methods.keys()),
            }), 400

        if stream_type == 'account_activity':
            result = method()
        else:
            if not symbols:
                return jsonify({
                    'success': False,
                    'error': 'symbols list required for this stream type'
                }), 400
            result = method(symbols)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error subscribing to stream: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@schwabdev_bp.route('/api/schwabdev/streaming/unsubscribe', methods=['POST'])
@login_required
def unsubscribe_streaming():
    """Unsubscribe from a streaming data type"""
    try:
        from utils.schwab_streaming import get_streaming_service

        data = request.get_json()
        stream_type = data.get('stream_type', '')

        service = get_streaming_service(current_user.id)
        result = service.unsubscribe(stream_type)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error unsubscribing from stream: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@schwabdev_bp.route('/api/schwabdev/streaming/start', methods=['POST'])
@login_required
def start_streaming():
    """Start the streaming connection"""
    try:
        from utils.schwab_streaming import get_streaming_service

        data = request.get_json() or {}
        preferred_library = data.get('library', 'schwabdev')

        service = get_streaming_service(current_user.id, preferred_library)
        result = service.start()

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error starting stream: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@schwabdev_bp.route('/api/schwabdev/streaming/stop', methods=['POST'])
@login_required
def stop_streaming():
    """Stop the streaming connection"""
    try:
        from utils.schwab_streaming import get_streaming_service

        service = get_streaming_service(current_user.id)
        result = service.stop()

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error stopping stream: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@schwabdev_bp.route('/api/schwabdev/streaming/data/<stream_type>', methods=['GET'])
@login_required
def get_streaming_data(stream_type):
    """Get buffered streaming data for a stream type"""
    try:
        from utils.schwab_streaming import get_streaming_service

        count = request.args.get('count', 10, type=int)

        service = get_streaming_service(current_user.id)
        result = service.get_latest_data(stream_type, count)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting streaming data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# NEW: schwab-py Info Endpoint
# =============================================================================

@schwabdev_bp.route('/api/schwabdev/schwab-py/info', methods=['GET'])
@login_required
def get_schwab_py_info():
    """Get schwab-py library information and status"""
    try:
        from utils.schwab_py_client import get_schwab_py_info
        info = get_schwab_py_info()

        # Also get client status for this user
        try:
            from utils.schwab_py_client import create_schwab_py_client
            client = create_schwab_py_client(current_user.id)
            info['client_status'] = client.get_status()
        except Exception:
            info['client_status'] = {'error': 'Could not create client'}

        return jsonify({'success': True, 'schwab_py': info})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500