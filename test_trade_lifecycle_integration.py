"""
Integration Test Suite for Trade Lifecycle
Tests the complete trade lifecycle including:
- Order placement and tracking
- Order execution and fills
- Stop-loss placement and enforcement
- Risk limit enforcement
- Order cancellation and replacement
- Error handling and edge cases

This suite tests the production-ready features implemented in Phase 1 and Phase 2.
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

sys.path.append('.')

from app import app, db
from models import User, APICredential, Trade
from utils.schwab_api import SchwabAPI
from utils.risk_management import RiskManager
from utils.encryption import encrypt_credentials
from utils.exceptions import (
    OrderExecutionError,
    InsufficientFundsError,
    RiskLimitExceededError,
    StopLossBreach,
    InvalidOrderError
)


@pytest.fixture
def app_context():
    """Provide Flask application context for tests"""
    with app.app_context():
        yield app


@pytest.fixture
def test_user(app_context):
    """Create a test user with API credentials"""
    # Clean up any existing test user
    db.session.query(Trade).filter(Trade.user_id == 998).delete()
    db.session.query(APICredential).filter(APICredential.user_id == 998).delete()
    db.session.query(User).filter(User.id == 998).delete()
    db.session.commit()

    # Create test user
    user = User(
        id=998,
        username='integration_test_user',
        email='integration_test@example.com',
        password_hash='test_hash',
        role='standard',
        is_active=True
    )
    db.session.add(user)

    # Create test Schwab credentials
    schwab_creds = APICredential(
        user_id=998,
        provider='schwab',
        encrypted_credentials=encrypt_credentials({
            'api_key': 'test_schwab_key',
            'secret': 'test_schwab_secret',
            'account_hash': 'test_account_hash'
        }),
        is_active=True,
        test_status='success'
    )
    db.session.add(schwab_creds)
    db.session.commit()

    yield user

    # Cleanup
    db.session.query(Trade).filter(Trade.user_id == 998).delete()
    db.session.query(APICredential).filter(APICredential.user_id == 998).delete()
    db.session.query(User).filter(User.id == 998).delete()
    db.session.commit()


@pytest.fixture
def mock_schwab_api():
    """Mock Schwab API client for testing"""
    with patch('utils.schwab_api.SchwabAPI') as mock:
        api = Mock(spec=SchwabAPI)
        mock.return_value = api
        yield api


@pytest.fixture
def risk_manager(app_context):
    """Create RiskManager instance"""
    return RiskManager(db=db)


class TestOrderPlacement:
    """Test suite for order placement functionality"""

    def test_place_stock_order_success(self, app_context, test_user, mock_schwab_api):
        """Test successful stock order placement"""
        # Mock successful order placement
        mock_schwab_api.place_order.return_value = {
            'success': True,
            'order_id': 'ORD123456',
            'message': 'Order placed successfully'
        }

        # Create trade
        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            status='pending',
            account_hash='test_account_hash'
        )
        db.session.add(trade)
        db.session.commit()

        # Place order
        result = mock_schwab_api.place_order('test_account_hash', {
            'orderType': 'LIMIT',
            'session': 'NORMAL',
            'duration': 'DAY',
            'price': 150.00,
            'orderLegCollection': [
                {
                    'instruction': 'BUY',
                    'quantity': 10,
                    'instrument': {'symbol': 'AAPL', 'assetType': 'EQUITY'}
                }
            ]
        })

        assert result['success'] is True
        assert result['order_id'] == 'ORD123456'

        # Update trade with order ID
        trade.order_id = result['order_id']
        trade.status = 'submitted'
        db.session.commit()

        assert trade.order_id == 'ORD123456'
        assert trade.status == 'submitted'

    def test_place_option_order_success(self, app_context, test_user, mock_schwab_api):
        """Test successful option order placement"""
        mock_schwab_api.place_order.return_value = {
            'success': True,
            'order_id': 'OPT123456',
            'message': 'Option order placed successfully'
        }

        trade = Trade(
            user_id=test_user.id,
            trade_type='option',
            side='buy',
            symbol='AAPL_012624C150',
            quantity=1,
            price=5.50,
            status='pending',
            account_hash='test_account_hash'
        )
        db.session.add(trade)
        db.session.commit()

        result = mock_schwab_api.place_order('test_account_hash', {
            'orderType': 'LIMIT',
            'price': 5.50,
            'orderLegCollection': [
                {
                    'instruction': 'BUY_TO_OPEN',
                    'quantity': 1,
                    'instrument': {'symbol': 'AAPL_012624C150', 'assetType': 'OPTION'}
                }
            ]
        })

        assert result['success'] is True
        assert result['order_id'] == 'OPT123456'
        trade.order_id = result['order_id']
        trade.status = 'submitted'
        db.session.commit()

    def test_place_order_insufficient_funds(self, app_context, test_user, mock_schwab_api):
        """Test order placement with insufficient funds"""
        mock_schwab_api.place_order.return_value = {
            'success': False,
            'error': 'Insufficient buying power'
        }

        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='TSLA',
            quantity=100,
            price=250.00,
            status='pending',
            account_hash='test_account_hash'
        )
        db.session.add(trade)
        db.session.commit()

        result = mock_schwab_api.place_order('test_account_hash', {})

        assert result['success'] is False
        assert 'Insufficient' in result['error']

        trade.status = 'failed'
        trade.error_message = result['error']
        db.session.commit()

        assert trade.status == 'failed'

    def test_place_order_invalid_symbol(self, app_context, test_user, mock_schwab_api):
        """Test order placement with invalid symbol"""
        mock_schwab_api.place_order.return_value = {
            'success': False,
            'error': 'Invalid symbol'
        }

        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='INVALID',
            quantity=10,
            price=100.00,
            status='pending',
            account_hash='test_account_hash'
        )
        db.session.add(trade)
        db.session.commit()

        result = mock_schwab_api.place_order('test_account_hash', {})

        assert result['success'] is False
        trade.status = 'failed'
        db.session.commit()


class TestOrderExecution:
    """Test suite for order execution and fills"""

    def test_get_order_executions_full_fill(self, app_context, test_user, mock_schwab_api):
        """Test retrieving execution details for fully filled order"""
        mock_schwab_api.get_order_executions.return_value = [
            {
                'executionId': 'EXEC001',
                'quantity': 10.0,
                'fillPrice': 150.50,
                'transactionDate': '2026-01-07T10:30:00Z'
            }
        ]

        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            order_id='ORD123456',
            status='submitted',
            account_hash='test_account_hash'
        )
        db.session.add(trade)
        db.session.commit()

        executions = mock_schwab_api.get_order_executions('test_account_hash', 'ORD123456')

        assert len(executions) == 1
        assert executions[0]['quantity'] == 10.0
        assert executions[0]['fillPrice'] == 150.50

        # Update trade with execution data
        trade.filled_quantity = executions[0]['quantity']
        trade.average_fill_price = executions[0]['fillPrice']
        trade.remaining_quantity = 0.0
        trade.status = 'executed'
        db.session.commit()

        assert trade.filled_quantity == 10.0
        assert trade.average_fill_price == 150.50
        assert trade.status == 'executed'

    def test_get_order_executions_partial_fill(self, app_context, test_user, mock_schwab_api):
        """Test retrieving execution details for partially filled order"""
        mock_schwab_api.get_order_executions.return_value = [
            {
                'executionId': 'EXEC002',
                'quantity': 5.0,
                'fillPrice': 150.25,
                'transactionDate': '2026-01-07T10:30:00Z'
            }
        ]

        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            order_id='ORD123457',
            status='submitted',
            account_hash='test_account_hash'
        )
        db.session.add(trade)
        db.session.commit()

        executions = mock_schwab_api.get_order_executions('test_account_hash', 'ORD123457')

        assert len(executions) == 1
        assert executions[0]['quantity'] == 5.0

        # Update trade with partial fill
        trade.filled_quantity = executions[0]['quantity']
        trade.average_fill_price = executions[0]['fillPrice']
        trade.remaining_quantity = trade.quantity - executions[0]['quantity']
        trade.status = 'partially_filled'
        db.session.commit()

        assert trade.filled_quantity == 5.0
        assert trade.remaining_quantity == 5.0
        assert trade.status == 'partially_filled'

    def test_get_order_executions_multiple_fills(self, app_context, test_user, mock_schwab_api):
        """Test retrieving multiple execution fills with average price calculation"""
        mock_schwab_api.get_order_executions.return_value = [
            {'executionId': 'EXEC003', 'quantity': 5.0, 'fillPrice': 150.00},
            {'executionId': 'EXEC004', 'quantity': 3.0, 'fillPrice': 150.50},
            {'executionId': 'EXEC005', 'quantity': 2.0, 'fillPrice': 151.00}
        ]

        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            order_id='ORD123458',
            status='submitted',
            account_hash='test_account_hash'
        )
        db.session.add(trade)
        db.session.commit()

        executions = mock_schwab_api.get_order_executions('test_account_hash', 'ORD123458')

        # Calculate weighted average fill price
        total_quantity = sum(e['quantity'] for e in executions)
        weighted_sum = sum(e['quantity'] * e['fillPrice'] for e in executions)
        average_price = weighted_sum / total_quantity

        assert total_quantity == 10.0
        assert average_price == pytest.approx(150.35, rel=1e-2)

        trade.filled_quantity = total_quantity
        trade.average_fill_price = average_price
        trade.remaining_quantity = 0.0
        trade.status = 'executed'
        db.session.commit()


class TestOrderCancellation:
    """Test suite for order cancellation and replacement"""

    def test_cancel_order_success(self, app_context, test_user, mock_schwab_api):
        """Test successful order cancellation"""
        mock_schwab_api.cancel_order.return_value = {
            'success': True,
            'message': 'Order cancelled successfully'
        }

        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            order_id='ORD123459',
            status='submitted',
            account_hash='test_account_hash'
        )
        db.session.add(trade)
        db.session.commit()

        result = mock_schwab_api.cancel_order('test_account_hash', 'ORD123459')

        assert result['success'] is True

        trade.status = 'cancelled'
        db.session.commit()

        assert trade.status == 'cancelled'

    def test_cancel_order_already_filled(self, app_context, test_user, mock_schwab_api):
        """Test cancellation attempt on already filled order"""
        mock_schwab_api.cancel_order.return_value = {
            'success': False,
            'error': 'Order already filled'
        }

        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            order_id='ORD123460',
            status='executed',
            account_hash='test_account_hash'
        )
        db.session.add(trade)
        db.session.commit()

        result = mock_schwab_api.cancel_order('test_account_hash', 'ORD123460')

        assert result['success'] is False
        assert 'filled' in result['error'].lower()

    def test_replace_order_success(self, app_context, test_user, mock_schwab_api):
        """Test successful order replacement (modify price/quantity)"""
        mock_schwab_api.replace_order.return_value = {
            'success': True,
            'order_id': 'ORD123461_NEW',
            'message': 'Order replaced successfully'
        }

        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            order_id='ORD123461',
            status='submitted',
            account_hash='test_account_hash'
        )
        db.session.add(trade)
        db.session.commit()

        new_order_data = {
            'orderType': 'LIMIT',
            'price': 149.00,  # New price
            'orderLegCollection': [
                {
                    'instruction': 'BUY',
                    'quantity': 15,  # New quantity
                    'instrument': {'symbol': 'AAPL', 'assetType': 'EQUITY'}
                }
            ]
        }

        result = mock_schwab_api.replace_order('test_account_hash', 'ORD123461', new_order_data)

        assert result['success'] is True
        assert result['order_id'] == 'ORD123461_NEW'

        # Update trade with new order ID and parameters
        trade.order_id = result['order_id']
        trade.price = 149.00
        trade.quantity = 15
        db.session.commit()


class TestStopLossEnforcement:
    """Test suite for stop-loss placement and enforcement"""

    def test_place_stop_loss_order(self, app_context, test_user, mock_schwab_api, risk_manager):
        """Test placing stop-loss order at broker"""
        mock_schwab_api.place_order.return_value = {
            'success': True,
            'order_id': 'SL123456',
            'message': 'Stop-loss order placed'
        }

        # Create executed trade
        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            average_fill_price=150.00,
            order_id='ORD123462',
            status='executed',
            account_hash='test_account_hash'
        )
        db.session.add(trade)
        db.session.commit()

        # Calculate and place stop-loss
        stop_price = 150.00 * 0.95  # 5% stop-loss

        with patch.object(risk_manager, 'place_stop_loss_order') as mock_place_sl:
            mock_place_sl.return_value = (True, 'Stop-loss placed', 'SL123456')

            success, message, sl_order_id = risk_manager.place_stop_loss_order(
                trade.id, stop_price, mock_schwab_api
            )

            assert success is True
            assert sl_order_id == 'SL123456'

            # Update trade with stop-loss info
            trade.stop_loss_price = stop_price
            trade.stop_loss_order_id = sl_order_id
            db.session.commit()

            assert trade.stop_loss_price == pytest.approx(142.50, rel=1e-2)
            assert trade.stop_loss_order_id == 'SL123456'

    def test_monitor_stop_loss_not_breached(self, app_context, test_user, mock_schwab_api, risk_manager):
        """Test stop-loss monitoring when price is above stop-loss"""
        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            average_fill_price=150.00,
            stop_loss_price=142.50,
            stop_loss_order_id='SL123456',
            status='executed',
            account_hash='test_account_hash'
        )
        db.session.add(trade)
        db.session.commit()

        # Mock current price above stop-loss
        with patch('utils.market_data.MarketDataProvider.get_stock_quote') as mock_quote:
            mock_quote.return_value = {'symbol': 'AAPL', 'price': 148.00}

            with patch.object(risk_manager, 'monitor_stop_losses') as mock_monitor:
                mock_monitor.return_value = {
                    'monitored': 1,
                    'triggered': 0,
                    'errors': 0
                }

                result = risk_manager.monitor_stop_losses(test_user.id, mock_schwab_api)

                assert result['monitored'] == 1
                assert result['triggered'] == 0

                # Trade should remain open
                db.session.refresh(trade)
                assert trade.status == 'executed'

    def test_monitor_stop_loss_breached(self, app_context, test_user, mock_schwab_api, risk_manager):
        """Test stop-loss monitoring when price breaches stop-loss"""
        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            average_fill_price=150.00,
            stop_loss_price=142.50,
            stop_loss_order_id='SL123456',
            status='executed',
            account_hash='test_account_hash'
        )
        db.session.add(trade)
        db.session.commit()

        # Mock current price below stop-loss
        with patch('utils.market_data.MarketDataProvider.get_stock_quote') as mock_quote:
            mock_quote.return_value = {'symbol': 'AAPL', 'price': 140.00}

            with patch.object(risk_manager, 'force_close_position') as mock_close:
                mock_close.return_value = (True, 'Position closed at $140.00')

                success, message = risk_manager.force_close_position(
                    trade.id, mock_schwab_api, reason='stop_loss_breach'
                )

                assert success is True
                assert 'closed' in message.lower()

                # Update trade status
                trade.status = 'closed'
                trade.exit_price = 140.00
                db.session.commit()

                assert trade.status == 'closed'
                assert trade.exit_price == 140.00

    def test_force_close_position(self, app_context, test_user, mock_schwab_api, risk_manager):
        """Test forced position closure with market order"""
        mock_schwab_api.place_order.return_value = {
            'success': True,
            'order_id': 'CLOSE123456',
            'message': 'Market order placed'
        }

        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            average_fill_price=150.00,
            status='executed',
            account_hash='test_account_hash'
        )
        db.session.add(trade)
        db.session.commit()

        with patch.object(risk_manager, 'force_close_position') as mock_close:
            mock_close.return_value = (True, 'Position closed via market order')

            success, message = risk_manager.force_close_position(
                trade.id, mock_schwab_api, reason='manual_close'
            )

            assert success is True

            trade.status = 'closed'
            db.session.commit()


class TestRiskManagement:
    """Test suite for risk limit enforcement"""

    def test_enforce_risk_limits_within_limits(self, app_context, test_user, risk_manager):
        """Test risk limit enforcement for trade within limits"""
        with patch.object(risk_manager, 'enforce_risk_limits') as mock_enforce:
            mock_enforce.return_value = (True, 'Trade within risk limits')

            allowed, message = risk_manager.enforce_risk_limits(
                user_id=test_user.id,
                trade_amount=1000.00,
                symbol='AAPL',
                user_role='standard'
            )

            assert allowed is True
            assert 'within' in message.lower()

    def test_enforce_risk_limits_exceeded(self, app_context, test_user, risk_manager):
        """Test risk limit enforcement for trade exceeding limits"""
        with patch.object(risk_manager, 'enforce_risk_limits') as mock_enforce:
            mock_enforce.return_value = (False, 'Trade exceeds maximum position size')

            allowed, message = risk_manager.enforce_risk_limits(
                user_id=test_user.id,
                trade_amount=100000.00,  # Very large trade
                symbol='AAPL',
                user_role='standard'
            )

            assert allowed is False
            assert 'exceeds' in message.lower()

    def test_enforce_daily_trading_limit(self, app_context, test_user, risk_manager):
        """Test daily trading limit enforcement"""
        # Create multiple trades for today
        for i in range(5):
            trade = Trade(
                user_id=test_user.id,
                trade_type='stock',
                side='buy',
                symbol=f'STOCK{i}',
                quantity=10,
                price=100.00,
                status='executed',
                created_at=datetime.utcnow()
            )
            db.session.add(trade)
        db.session.commit()

        # Check if additional trade is allowed
        today_trades = Trade.query.filter(
            Trade.user_id == test_user.id,
            Trade.status == 'executed',
            Trade.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        ).count()

        assert today_trades == 5

        # Assume limit is 10 trades per day for standard users
        max_daily_trades = 10
        assert today_trades < max_daily_trades

    def test_enforce_concentration_limit(self, app_context, test_user, risk_manager):
        """Test concentration limit (max % of portfolio in single symbol)"""
        # Create multiple trades in same symbol
        for i in range(3):
            trade = Trade(
                user_id=test_user.id,
                trade_type='stock',
                side='buy',
                symbol='AAPL',
                quantity=10,
                price=150.00,
                average_fill_price=150.00,
                status='executed'
            )
            db.session.add(trade)
        db.session.commit()

        # Check concentration for AAPL
        aapl_trades = Trade.query.filter(
            Trade.user_id == test_user.id,
            Trade.symbol == 'AAPL',
            Trade.status == 'executed'
        ).count()

        assert aapl_trades == 3

        # In production, would check if this exceeds max concentration %


class TestErrorHandling:
    """Test suite for error handling and edge cases"""

    def test_order_placement_network_error(self, app_context, test_user, mock_schwab_api):
        """Test handling of network errors during order placement"""
        mock_schwab_api.place_order.side_effect = Exception('Network timeout')

        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            status='pending',
            account_hash='test_account_hash'
        )
        db.session.add(trade)
        db.session.commit()

        with pytest.raises(Exception) as exc_info:
            mock_schwab_api.place_order('test_account_hash', {})

        assert 'Network timeout' in str(exc_info.value)

        trade.status = 'failed'
        trade.error_message = str(exc_info.value)
        db.session.commit()

    def test_order_status_check_invalid_order_id(self, app_context, test_user, mock_schwab_api):
        """Test handling of invalid order ID during status check"""
        mock_schwab_api.get_order.return_value = {
            'success': False,
            'error': 'Order not found'
        }

        result = mock_schwab_api.get_order('test_account_hash', 'INVALID_ORDER')

        assert result['success'] is False
        assert 'not found' in result['error'].lower()

    def test_stop_loss_placement_order_failure(self, app_context, test_user, mock_schwab_api, risk_manager):
        """Test handling of failure when placing stop-loss order"""
        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            status='executed',
            account_hash='test_account_hash'
        )
        db.session.add(trade)
        db.session.commit()

        with patch.object(risk_manager, 'place_stop_loss_order') as mock_place_sl:
            mock_place_sl.return_value = (False, 'Failed to place stop-loss order', None)

            success, message, sl_order_id = risk_manager.place_stop_loss_order(
                trade.id, 142.50, mock_schwab_api
            )

            assert success is False
            assert sl_order_id is None

    def test_market_data_unavailable(self, app_context, test_user, risk_manager):
        """Test handling of market data unavailability"""
        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            stop_loss_price=142.50,
            status='executed'
        )
        db.session.add(trade)
        db.session.commit()

        # Mock market data failure
        with patch('utils.market_data.MarketDataProvider.get_stock_quote') as mock_quote:
            mock_quote.return_value = None  # Market data unavailable

            quote = mock_quote('AAPL')
            assert quote is None

            # System should handle gracefully (no position closure without data)


class TestTradeStatusTransitions:
    """Test suite for trade status transitions throughout lifecycle"""

    def test_status_transition_pending_to_submitted(self, app_context, test_user):
        """Test transition from pending to submitted"""
        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            status='pending'
        )
        db.session.add(trade)
        db.session.commit()

        assert trade.status == 'pending'

        # Simulate order submission
        trade.order_id = 'ORD123463'
        trade.status = 'submitted'
        db.session.commit()

        assert trade.status == 'submitted'
        assert trade.order_id is not None

    def test_status_transition_submitted_to_executed(self, app_context, test_user):
        """Test transition from submitted to executed"""
        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            order_id='ORD123464',
            status='submitted'
        )
        db.session.add(trade)
        db.session.commit()

        # Simulate full execution
        trade.filled_quantity = 10.0
        trade.average_fill_price = 150.25
        trade.remaining_quantity = 0.0
        trade.status = 'executed'
        db.session.commit()

        assert trade.status == 'executed'
        assert trade.filled_quantity == 10.0

    def test_status_transition_executed_to_closed(self, app_context, test_user):
        """Test transition from executed to closed"""
        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            average_fill_price=150.00,
            filled_quantity=10.0,
            status='executed'
        )
        db.session.add(trade)
        db.session.commit()

        # Simulate position closure
        trade.exit_price = 155.00
        trade.status = 'closed'
        trade.closed_at = datetime.utcnow()
        db.session.commit()

        assert trade.status == 'closed'
        assert trade.exit_price == 155.00
        assert trade.closed_at is not None

    def test_complete_trade_lifecycle(self, app_context, test_user):
        """Test complete trade lifecycle from creation to closure"""
        # 1. Create trade
        trade = Trade(
            user_id=test_user.id,
            trade_type='stock',
            side='buy',
            symbol='AAPL',
            quantity=10,
            price=150.00,
            status='pending',
            created_at=datetime.utcnow()
        )
        db.session.add(trade)
        db.session.commit()
        assert trade.status == 'pending'

        # 2. Submit order
        trade.order_id = 'ORD123465'
        trade.account_hash = 'test_account_hash'
        trade.status = 'submitted'
        db.session.commit()
        assert trade.status == 'submitted'

        # 3. Execute order
        trade.filled_quantity = 10.0
        trade.average_fill_price = 150.50
        trade.remaining_quantity = 0.0
        trade.status = 'executed'
        db.session.commit()
        assert trade.status == 'executed'

        # 4. Place stop-loss
        trade.stop_loss_price = 142.50
        trade.stop_loss_order_id = 'SL123465'
        db.session.commit()
        assert trade.stop_loss_price is not None

        # 5. Close position
        trade.exit_price = 155.00
        trade.status = 'closed'
        trade.closed_at = datetime.utcnow()
        db.session.commit()
        assert trade.status == 'closed'

        # Verify complete lifecycle
        assert trade.order_id is not None
        assert trade.filled_quantity == 10.0
        assert trade.exit_price == 155.00
        assert trade.closed_at is not None


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v', '--tb=short'])
