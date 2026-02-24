"""
Flask routes for the Coinbase Advanced Trade API.
Exposes accounts, orders, products, portfolios, fees, converts, and futures.
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import logging

logger = logging.getLogger(__name__)

coinbase_at_bp = Blueprint('coinbase_advanced_trade', __name__)


def _client():
    from utils.coinbase_advanced_trade import CoinbaseAdvancedTradeClient
    return CoinbaseAdvancedTradeClient(user_id=str(current_user.id))


# ------------------------------------------------------------------
# Credentials
# ------------------------------------------------------------------

@coinbase_at_bp.route('/api/coinbase-at/save-credentials', methods=['POST'])
@login_required
def save_credentials():
    """Save Coinbase Advanced Trade API key + secret."""
    try:
        data = request.get_json()
        api_key = data.get('api_key')
        api_secret = data.get('api_secret')
        if not api_key or not api_secret:
            return jsonify({'success': False, 'error': 'api_key and api_secret required'}), 400
        client = _client()
        client.save_credentials(api_key, api_secret)
        return jsonify({'success': True, 'message': 'Credentials saved'})
    except Exception as e:
        logger.error("Error saving AT credentials: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/test-connection', methods=['GET'])
@login_required
def test_connection():
    try:
        return jsonify(_client().test_connection())
    except Exception as e:
        logger.error("Error testing AT connection: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/key-permissions', methods=['GET'])
@login_required
def key_permissions():
    try:
        return jsonify({'success': True, 'permissions': _client().get_api_key_permissions()})
    except Exception as e:
        logger.error("Error getting key permissions: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# Accounts
# ------------------------------------------------------------------

@coinbase_at_bp.route('/api/coinbase-at/accounts', methods=['GET'])
@login_required
def list_accounts():
    try:
        limit = request.args.get('limit', 49, type=int)
        cursor = request.args.get('cursor')
        result = _client().list_accounts(limit=limit, cursor=cursor)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error listing AT accounts: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/accounts/<account_uuid>', methods=['GET'])
@login_required
def get_account(account_uuid):
    try:
        return jsonify({'success': True, 'account': _client().get_account(account_uuid)})
    except Exception as e:
        logger.error("Error getting AT account: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# Products (market data)
# ------------------------------------------------------------------

@coinbase_at_bp.route('/api/coinbase-at/products', methods=['GET'])
@login_required
def list_products():
    try:
        product_type = request.args.get('product_type')
        limit = request.args.get('limit', type=int)
        offset = request.args.get('offset', type=int)
        result = _client().list_products(product_type=product_type, limit=limit, offset=offset)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error listing products: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/products/<product_id>', methods=['GET'])
@login_required
def get_product(product_id):
    try:
        return jsonify({'success': True, 'product': _client().get_product(product_id)})
    except Exception as e:
        logger.error("Error getting product: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/products/<product_id>/candles', methods=['GET'])
@login_required
def get_product_candles(product_id):
    try:
        start = request.args.get('start')
        end = request.args.get('end')
        granularity = request.args.get('granularity', 'ONE_HOUR')
        if not start or not end:
            return jsonify({'success': False, 'error': 'start and end timestamps required'}), 400
        result = _client().get_product_candles(product_id, start, end, granularity)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error getting candles: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/products/<product_id>/trades', methods=['GET'])
@login_required
def get_market_trades(product_id):
    try:
        limit = request.args.get('limit', 100, type=int)
        result = _client().get_market_trades(product_id, limit=limit)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error getting market trades: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/product-book', methods=['GET'])
@login_required
def get_product_book():
    try:
        product_id = request.args.get('product_id')
        if not product_id:
            return jsonify({'success': False, 'error': 'product_id required'}), 400
        limit = request.args.get('limit', type=int)
        result = _client().get_product_book(product_id, limit=limit)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error getting product book: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/best-bid-ask', methods=['GET'])
@login_required
def get_best_bid_ask():
    try:
        product_ids = request.args.getlist('product_ids')
        result = _client().get_best_bid_ask(product_ids=product_ids or None)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error getting best bid/ask: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# Orders
# ------------------------------------------------------------------

@coinbase_at_bp.route('/api/coinbase-at/orders', methods=['POST'])
@login_required
def create_order():
    """Generic order creation. Body must contain full order_configuration."""
    try:
        data = request.get_json()
        required = ['product_id', 'side', 'order_configuration']
        for field in required:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        import uuid as _uuid
        client_order_id = data.get('client_order_id', str(_uuid.uuid4()))
        result = _client().create_order(
            client_order_id, data['product_id'], data['side'], data['order_configuration']
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error creating order: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/orders/market', methods=['POST'])
@login_required
def create_market_order():
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        side = data.get('side')
        if not product_id or not side:
            return jsonify({'success': False, 'error': 'product_id and side required'}), 400
        result = _client().create_market_order(
            product_id=product_id,
            side=side,
            quote_size=data.get('quote_size'),
            base_size=data.get('base_size'),
            user_id=current_user.id,
            is_simulation=data.get('is_simulation', False),
        )
        return jsonify(result)
    except Exception as e:
        logger.error("Error creating market order: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/orders/limit', methods=['POST'])
@login_required
def create_limit_order():
    try:
        data = request.get_json()
        for field in ['product_id', 'side', 'base_size', 'limit_price']:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        result = _client().create_limit_order(
            product_id=data['product_id'],
            side=data['side'],
            base_size=data['base_size'],
            limit_price=data['limit_price'],
            post_only=data.get('post_only', False),
            end_time=data.get('end_time'),
            user_id=current_user.id,
            is_simulation=data.get('is_simulation', False),
        )
        return jsonify(result)
    except Exception as e:
        logger.error("Error creating limit order: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/orders/stop-limit', methods=['POST'])
@login_required
def create_stop_limit_order():
    try:
        data = request.get_json()
        for field in ['product_id', 'side', 'base_size', 'limit_price', 'stop_price']:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        result = _client().create_stop_limit_order(
            product_id=data['product_id'],
            side=data['side'],
            base_size=data['base_size'],
            limit_price=data['limit_price'],
            stop_price=data['stop_price'],
            end_time=data.get('end_time'),
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error creating stop-limit order: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/orders/bracket', methods=['POST'])
@login_required
def create_bracket_order():
    try:
        data = request.get_json()
        for field in ['product_id', 'side', 'base_size', 'limit_price', 'stop_trigger_price']:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        result = _client().create_bracket_order(
            product_id=data['product_id'],
            side=data['side'],
            base_size=data['base_size'],
            limit_price=data['limit_price'],
            stop_trigger_price=data['stop_trigger_price'],
            end_time=data.get('end_time'),
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error creating bracket order: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/orders/cancel', methods=['POST'])
@login_required
def cancel_orders():
    try:
        data = request.get_json()
        order_ids = data.get('order_ids', [])
        if not order_ids:
            return jsonify({'success': False, 'error': 'order_ids required'}), 400
        result = _client().cancel_orders(order_ids)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error cancelling orders: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/orders', methods=['GET'])
@login_required
def list_orders():
    try:
        result = _client().list_orders(
            product_id=request.args.get('product_id'),
            order_status=request.args.getlist('order_status') or None,
            limit=request.args.get('limit', type=int),
            start_date=request.args.get('start_date'),
            end_date=request.args.get('end_date'),
            order_type=request.args.get('order_type'),
            order_side=request.args.get('order_side'),
            cursor=request.args.get('cursor'),
            product_type=request.args.get('product_type'),
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error listing orders: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/orders/<order_id>', methods=['GET'])
@login_required
def get_order(order_id):
    try:
        return jsonify({'success': True, 'order': _client().get_order(order_id)})
    except Exception as e:
        logger.error("Error getting order: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/orders/fills', methods=['GET'])
@login_required
def list_fills():
    try:
        result = _client().list_fills(
            order_id=request.args.get('order_id'),
            product_id=request.args.get('product_id'),
            limit=request.args.get('limit', type=int),
            cursor=request.args.get('cursor'),
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error listing fills: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/orders/edit', methods=['POST'])
@login_required
def edit_order():
    try:
        data = request.get_json()
        order_id = data.get('order_id')
        if not order_id:
            return jsonify({'success': False, 'error': 'order_id required'}), 400
        result = _client().edit_order(
            order_id, price=data.get('price'), size=data.get('size')
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error editing order: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/orders/preview', methods=['POST'])
@login_required
def preview_order():
    try:
        data = request.get_json()
        for field in ['product_id', 'side', 'order_configuration']:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        result = _client().preview_order(
            data['product_id'], data['side'], data['order_configuration']
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error previewing order: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/orders/close-position', methods=['POST'])
@login_required
def close_position():
    try:
        data = request.get_json()
        import uuid as _uuid
        client_order_id = data.get('client_order_id', str(_uuid.uuid4()))
        product_id = data.get('product_id')
        if not product_id:
            return jsonify({'success': False, 'error': 'product_id required'}), 400
        result = _client().close_position(client_order_id, product_id, data.get('size'))
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error closing position: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# Portfolios
# ------------------------------------------------------------------

@coinbase_at_bp.route('/api/coinbase-at/portfolios', methods=['GET'])
@login_required
def list_portfolios():
    try:
        result = _client().list_portfolios(
            portfolio_type=request.args.get('portfolio_type')
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error listing portfolios: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/portfolios', methods=['POST'])
@login_required
def create_portfolio():
    try:
        data = request.get_json()
        name = data.get('name')
        if not name:
            return jsonify({'success': False, 'error': 'name required'}), 400
        result = _client().create_portfolio(name)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error creating portfolio: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/portfolios/<portfolio_uuid>', methods=['GET'])
@login_required
def get_portfolio_breakdown(portfolio_uuid):
    try:
        currency = request.args.get('currency')
        result = _client().get_portfolio_breakdown(portfolio_uuid, currency=currency)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error getting portfolio breakdown: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/portfolios/<portfolio_uuid>', methods=['PUT'])
@login_required
def edit_portfolio(portfolio_uuid):
    try:
        data = request.get_json()
        name = data.get('name')
        if not name:
            return jsonify({'success': False, 'error': 'name required'}), 400
        result = _client().edit_portfolio(portfolio_uuid, name)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error editing portfolio: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/portfolios/<portfolio_uuid>', methods=['DELETE'])
@login_required
def delete_portfolio(portfolio_uuid):
    try:
        result = _client().delete_portfolio(portfolio_uuid)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error deleting portfolio: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/portfolios/move-funds', methods=['POST'])
@login_required
def move_portfolio_funds():
    try:
        data = request.get_json()
        for field in ['funds_value', 'funds_currency', 'source_portfolio_uuid', 'target_portfolio_uuid']:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        result = _client().move_portfolio_funds(
            data['funds_value'], data['funds_currency'],
            data['source_portfolio_uuid'], data['target_portfolio_uuid'],
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error moving portfolio funds: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# Converts
# ------------------------------------------------------------------

@coinbase_at_bp.route('/api/coinbase-at/convert/quote', methods=['POST'])
@login_required
def create_convert_quote():
    try:
        data = request.get_json()
        for field in ['from_account', 'to_account', 'amount']:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        result = _client().create_convert_quote(
            data['from_account'], data['to_account'], data['amount'],
            data.get('trade_incentive_metadata'),
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error creating convert quote: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/convert/trade/<trade_id>', methods=['POST'])
@login_required
def commit_convert_trade(trade_id):
    try:
        data = request.get_json()
        for field in ['from_account', 'to_account']:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        result = _client().commit_convert_trade(trade_id, data['from_account'], data['to_account'])
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error committing convert trade: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/convert/trade/<trade_id>', methods=['GET'])
@login_required
def get_convert_trade(trade_id):
    try:
        from_account = request.args.get('from_account')
        to_account = request.args.get('to_account')
        if not from_account or not to_account:
            return jsonify({'success': False, 'error': 'from_account and to_account required'}), 400
        result = _client().get_convert_trade(trade_id, from_account, to_account)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error getting convert trade: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# Fees
# ------------------------------------------------------------------

@coinbase_at_bp.route('/api/coinbase-at/transaction-summary', methods=['GET'])
@login_required
def get_transaction_summary():
    try:
        result = _client().get_transaction_summary(
            start_date=request.args.get('start_date'),
            end_date=request.args.get('end_date'),
            user_native_currency=request.args.get('user_native_currency', 'USD'),
            product_type=request.args.get('product_type'),
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error getting transaction summary: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# Payment Methods
# ------------------------------------------------------------------

@coinbase_at_bp.route('/api/coinbase-at/payment-methods', methods=['GET'])
@login_required
def list_payment_methods():
    try:
        result = _client().list_payment_methods()
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error listing payment methods: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/payment-methods/<payment_method_id>', methods=['GET'])
@login_required
def get_payment_method(payment_method_id):
    try:
        result = _client().get_payment_method(payment_method_id)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error getting payment method: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# Perpetuals / Futures
# ------------------------------------------------------------------

@coinbase_at_bp.route('/api/coinbase-at/perpetuals/<portfolio_uuid>/summary', methods=['GET'])
@login_required
def get_perpetuals_summary(portfolio_uuid):
    try:
        result = _client().get_perpetuals_portfolio_summary(portfolio_uuid)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error getting perpetuals summary: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/perpetuals/<portfolio_uuid>/positions', methods=['GET'])
@login_required
def list_perpetuals_positions(portfolio_uuid):
    try:
        result = _client().list_perpetuals_positions(portfolio_uuid)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error listing perpetuals positions: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/futures/balance-summary', methods=['GET'])
@login_required
def get_futures_balance_summary():
    try:
        result = _client().get_futures_balance_summary()
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error getting futures balance summary: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/futures/positions', methods=['GET'])
@login_required
def list_futures_positions():
    try:
        result = _client().list_futures_positions()
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error listing futures positions: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/futures/sweeps', methods=['GET'])
@login_required
def list_futures_sweeps():
    try:
        result = _client().list_futures_sweeps()
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error listing futures sweeps: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/futures/sweeps/schedule', methods=['POST'])
@login_required
def schedule_futures_sweep():
    try:
        data = request.get_json() or {}
        result = _client().schedule_futures_sweep(usd_amount=data.get('usd_amount'))
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error scheduling futures sweep: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/futures/sweeps', methods=['DELETE'])
@login_required
def cancel_futures_sweep():
    try:
        result = _client().cancel_pending_futures_sweep()
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error cancelling futures sweep: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_at_bp.route('/api/coinbase-at/server-time', methods=['GET'])
@login_required
def get_server_time():
    try:
        result = _client().get_server_time()
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error getting server time: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500
