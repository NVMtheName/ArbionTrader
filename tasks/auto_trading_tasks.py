import os
import logging
from datetime import datetime, timedelta
from models import User, APICredential, Strategy, AutoTradingSettings, Trade, SystemLog
from app import db
from utils.encryption import decrypt_credentials
from utils.coinbase_connector import CoinbaseConnector
from utils.schwab_connector import SchwabConnector
from utils.openai_trader import OpenAITrader
from utils.market_data import MarketDataProvider
from utils.risk_management import RiskManager
from utils.options_trading import WheelStrategy, CollarStrategy, AIStrategyHelper, OptionsCalculator
import json
import asyncio
import random

class AutoTradingEngine:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.market_data = MarketDataProvider()
        self.risk_manager = RiskManager()

        # Initialize strategy helpers
        self.wheel_strategy = WheelStrategy()
        self.collar_strategy = CollarStrategy()
        self.ai_helper = AIStrategyHelper()
        self.options_calc = OptionsCalculator()
        
    def log_system_event(self, level, message, module='auto_trading', user_id=None):
        """Log system events to database"""
        try:
            from app import app
            with app.app_context():
                log_entry = SystemLog(
                    level=level,
                    message=message,
                    module=module,
                    user_id=user_id
                )
                db.session.add(log_entry)
                db.session.commit()
        except Exception as e:
            self.logger.error(f"Failed to log system event: {str(e)}")
    
    def run_auto_trading_cycle(self):
        """Main auto-trading cycle"""
        try:
            from app import app
            with app.app_context():
                self.log_system_event('info', 'Starting auto-trading cycle')
                
                # Get auto-trading settings
                settings = AutoTradingSettings.get_settings()
                
                if not settings.is_enabled:
                    self.log_system_event('info', 'Auto-trading is disabled')
                    return
                
                # Run enabled strategies
                if settings.wheel_enabled:
                    self.run_wheel_strategy(settings.simulation_mode)
                
                if settings.collar_enabled:
                    self.run_collar_strategy(settings.simulation_mode)
                
                if settings.ai_enabled:
                    self.run_ai_strategy(settings.simulation_mode)
                
                # Update last run time
                settings.last_run = datetime.utcnow()
                db.session.commit()
                
                self.log_system_event('info', 'Auto-trading cycle completed')
        
        except Exception as e:
            self.logger.error(f"Error in auto-trading cycle: {str(e)}")
            self.log_system_event('error', f'Auto-trading cycle failed: {str(e)}')
    
    def run_wheel_strategy(self, simulation_mode=True):
        """Run the wheel options strategy with multi-user support"""
        try:
            self.log_system_event('info', 'Starting wheel strategy execution')
            
            # Get wheel parameters
            wheel_params = {
                'target_delta': 0.30,
                'target_dte': 30,
                'profit_target': 0.50,
                'max_positions': 5,
                'watchlist': ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA']
            }
            
            # Get users with active credentials
            users = User.query.filter_by(is_active=True).all()
            successful_executions = 0
            
            for user in users:
                try:
                    # Get user's API credentials
                    creds = APICredential.query.filter_by(
                        user_id=user.id,
                        provider='schwab',
                        is_active=True
                    ).first()
                    
                    if not creds:
                        self.log_system_event('warning', f'No Schwab credentials found for user {user.id}')
                        continue
                    
                    # Execute wheel strategy
                    result = self.execute_wheel_logic(creds, wheel_params, user.id, simulation_mode)
                    if result:
                        successful_executions += 1
                    
                except Exception as e:
                    self.log_system_event('error', f'Error in wheel strategy for user {user.id}: {str(e)}')
                    continue
            
            self.log_system_event('info', f'Wheel strategy execution completed. Successful executions: {successful_executions}')
            
        except Exception as e:
            self.log_system_event('error', f'Error in wheel strategy: {str(e)}')
            logging.error(f"Error in wheel strategy: {str(e)}")
    
    def execute_wheel_logic(self, user_creds, params, user_id, simulation_mode):
        """Execute wheel strategy logic with enhanced multi-user support"""
        try:
            # Execute wheel strategy for each symbol in watchlist
            trades_executed = 0

            for symbol in params['watchlist']:
                try:
                    # Get current stock price (simulated for now)
                    stock_price = self._get_simulated_stock_price(symbol)

                    # Check if user has existing position in this stock
                    has_shares = self._check_user_has_shares(user_id, symbol)

                    # Wheel strategy logic:
                    # 1. If we own shares, sell covered calls
                    # 2. If we don't own shares, sell cash-secured puts

                    if has_shares:
                        # Sell covered call on existing shares
                        if self.sell_covered_call(
                            user_id, symbol, stock_price,
                            params['target_delta'], params['target_dte'],
                            simulation_mode
                        ):
                            trades_executed += 1
                    else:
                        # Sell cash-secured put to potentially acquire shares
                        if self.sell_cash_secured_put(
                            user_id, symbol, stock_price,
                            params['target_delta'], params['target_dte'],
                            simulation_mode
                        ):
                            trades_executed += 1

                except Exception as e:
                    self.log_system_event('error', f'Error processing {symbol} for wheel strategy: {str(e)}')
                    continue

            self.log_system_event('info', f'Wheel strategy executed {trades_executed} trades for user {user_id}')
            return trades_executed > 0

        except Exception as e:
            self.log_system_event('error', f'Error in wheel strategy execution for user {user_id}: {str(e)}')
            return False
    
    def sell_covered_call(self, user_id, symbol, stock_price, delta, dte, simulation_mode):
        """Sell covered call for wheel strategy"""
        try:
            # Get covered call details using options calculator
            cc_details = self.wheel_strategy.get_covered_call_details(
                symbol=symbol,
                stock_price=stock_price,
                target_delta=delta,
                dte=dte,
                shares_owned=100
            )

            if not cc_details:
                self.log_system_event('warning', f'Could not generate covered call details for {symbol}')
                return False

            # Create detailed execution summary
            execution_details = {
                'strategy_type': 'covered_call',
                'stock_price': cc_details['stock_price'],
                'strike': cc_details['strike'],
                'delta': cc_details['delta'],
                'premium': cc_details['premium'],
                'premium_collected': cc_details['premium_collected'],
                'expiration_date': cc_details['expiration_date'],
                'days_to_expiration': cc_details['days_to_expiration'],
                'annualized_return': cc_details['annualized_return'],
                'upside_capped_at': cc_details['upside_capped_at'],
                'total_return_if_called': cc_details['total_return_if_called']
            }

            # Create a covered call trade record
            trade = Trade(
                user_id=user_id,
                provider='schwab',
                symbol=symbol,
                side='sell',
                quantity=1,  # 1 options contract
                price=cc_details['premium'],
                trade_type='covered_call',
                strategy='wheel',
                status='executed' if simulation_mode else 'pending',
                is_simulation=simulation_mode,
                executed_at=datetime.utcnow() if simulation_mode else None,
                execution_details=json.dumps(execution_details)
            )

            db.session.add(trade)
            db.session.commit()

            self.log_system_event(
                'info',
                f'Covered call executed for user {user_id}: {symbol} ${cc_details["strike"]} strike, '
                f'${cc_details["premium_collected"]:.2f} premium, {cc_details["annualized_return"]:.1f}% annual return'
            )
            return True

        except Exception as e:
            self.log_system_event('error', f'Error selling covered call: {str(e)}')
            return False
    
    def sell_cash_secured_put(self, user_id, symbol, stock_price, delta, dte, simulation_mode):
        """Sell cash-secured put for wheel strategy"""
        try:
            # Get cash-secured put details using options calculator
            csp_details = self.wheel_strategy.get_cash_secured_put_details(
                symbol=symbol,
                stock_price=stock_price,
                target_delta=delta,
                dte=dte
            )

            if not csp_details:
                self.log_system_event('warning', f'Could not generate cash-secured put details for {symbol}')
                return False

            # Create detailed execution summary
            execution_details = {
                'strategy_type': 'cash_secured_put',
                'stock_price': csp_details['stock_price'],
                'strike': csp_details['strike'],
                'delta': csp_details['delta'],
                'premium': csp_details['premium'],
                'premium_collected': csp_details['premium_collected'],
                'expiration_date': csp_details['expiration_date'],
                'days_to_expiration': csp_details['days_to_expiration'],
                'cash_required': csp_details['cash_required'],
                'annualized_return': csp_details['annualized_return'],
                'breakeven': csp_details['breakeven'],
                'max_profit': csp_details['max_profit']
            }

            # Create a cash-secured put trade record
            trade = Trade(
                user_id=user_id,
                provider='schwab',
                symbol=symbol,
                side='sell',
                quantity=1,  # 1 options contract
                price=csp_details['premium'],
                trade_type='cash_secured_put',
                strategy='wheel',
                status='executed' if simulation_mode else 'pending',
                is_simulation=simulation_mode,
                executed_at=datetime.utcnow() if simulation_mode else None,
                execution_details=json.dumps(execution_details)
            )

            db.session.add(trade)
            db.session.commit()

            self.log_system_event(
                'info',
                f'Cash-secured put executed for user {user_id}: {symbol} ${csp_details["strike"]} strike, '
                f'${csp_details["premium_collected"]:.2f} premium, {csp_details["annualized_return"]:.1f}% annual return'
            )
            return True

        except Exception as e:
            self.log_system_event('error', f'Error selling cash-secured put: {str(e)}')
            return False
    
    def run_collar_strategy(self, simulation_mode=True):
        """Run collar strategy with multi-user support"""
        try:
            self.log_system_event('info', 'Starting collar strategy execution')
            
            # Get collar parameters
            collar_params = {
                'protection_delta': 0.20,  # Put delta for downside protection
                'call_delta': 0.30,        # Call delta for upside cap
                'target_dte': 30,
                'watchlist': ['SPY', 'QQQ', 'IWM']  # ETFs for collar strategy
            }
            
            # Get users with active credentials
            users = User.query.filter_by(is_active=True).all()
            successful_executions = 0
            
            for user in users:
                try:
                    # Get user's API credentials
                    creds = APICredential.query.filter_by(
                        user_id=user.id,
                        provider='schwab',
                        is_active=True
                    ).first()
                    
                    if not creds:
                        continue
                    
                    # Execute collar strategy
                    result = self.execute_collar_logic(user.id, collar_params, simulation_mode)
                    if result:
                        successful_executions += 1
                    
                except Exception as e:
                    self.log_system_event('error', f'Error in collar strategy for user {user.id}: {str(e)}')
                    continue
            
            self.log_system_event('info', f'Collar strategy execution completed. Successful executions: {successful_executions}')
            
        except Exception as e:
            self.log_system_event('error', f'Error in collar strategy: {str(e)}')
            logging.error(f"Error in collar strategy: {str(e)}")
    
    def execute_collar_logic(self, user_id, params, simulation_mode):
        """Execute collar strategy logic"""
        try:
            # Create collar trades (buy put, sell call)
            trades_executed = 0

            for symbol in params['watchlist']:
                try:
                    # Get current stock price
                    stock_price = self._get_simulated_stock_price(symbol)

                    # Check if user has shares (collar requires owning stock)
                    has_shares = self._check_user_has_shares(user_id, symbol)

                    if not has_shares:
                        self.log_system_event('info', f'Skipping {symbol} - collar requires owning shares')
                        continue

                    # Get collar strategy details
                    collar_details = self.collar_strategy.get_collar_details(
                        symbol=symbol,
                        stock_price=stock_price,
                        shares_owned=100,
                        put_delta=params['protection_delta'],
                        call_delta=params['call_delta'],
                        dte=params['target_dte']
                    )

                    if not collar_details:
                        self.log_system_event('warning', f'Could not generate collar details for {symbol}')
                        continue

                    # Create comprehensive execution details
                    execution_details = {
                        'strategy_type': 'collar',
                        'stock_price': collar_details['stock_price'],
                        'put_strike': collar_details['put_strike'],
                        'call_strike': collar_details['call_strike'],
                        'put_delta': collar_details['put_delta'],
                        'call_delta': collar_details['call_delta'],
                        'put_cost': collar_details['put_cost'],
                        'call_credit': collar_details['call_credit'],
                        'net_cost': collar_details['net_cost'],
                        'net_debit_credit': collar_details['net_debit_credit'],
                        'expiration_date': collar_details['expiration_date'],
                        'protected_range': collar_details['protected_range'],
                        'max_loss': collar_details['max_loss'],
                        'max_gain': collar_details['max_gain'],
                        'risk_reward_ratio': collar_details['risk_reward_ratio']
                    }

                    # Buy protective put
                    put_trade = Trade(
                        user_id=user_id,
                        provider='schwab',
                        symbol=symbol,
                        side='buy',
                        quantity=1,
                        price=collar_details['put_premium'],
                        trade_type='protective_put',
                        strategy='collar',
                        status='executed' if simulation_mode else 'pending',
                        is_simulation=simulation_mode,
                        executed_at=datetime.utcnow() if simulation_mode else None,
                        execution_details=json.dumps({
                            **execution_details,
                            'leg': 'protective_put'
                        })
                    )

                    # Sell covered call
                    call_trade = Trade(
                        user_id=user_id,
                        provider='schwab',
                        symbol=symbol,
                        side='sell',
                        quantity=1,
                        price=collar_details['call_premium'],
                        trade_type='covered_call',
                        strategy='collar',
                        status='executed' if simulation_mode else 'pending',
                        is_simulation=simulation_mode,
                        executed_at=datetime.utcnow() if simulation_mode else None,
                        execution_details=json.dumps({
                            **execution_details,
                            'leg': 'covered_call'
                        })
                    )

                    db.session.add(put_trade)
                    db.session.add(call_trade)
                    db.session.commit()

                    trades_executed += 2

                    self.log_system_event(
                        'info',
                        f'Collar executed for user {user_id}: {symbol} protected ${collar_details["put_strike"]}-${collar_details["call_strike"]}, '
                        f'net {"credit" if collar_details["net_cost"] < 0 else "debit"} ${abs(collar_details["net_cost"]):.2f}'
                    )

                except Exception as e:
                    self.log_system_event('error', f'Error processing collar for {symbol}: {str(e)}')
                    continue

            self.log_system_event('info', f'Collar strategy executed {trades_executed} trades for user {user_id}')
            return trades_executed > 0

        except Exception as e:
            self.log_system_event('error', f'Error in collar strategy execution: {str(e)}')
            return False
    
    def run_ai_strategy(self, simulation_mode=True):
        """Run AI-driven strategy with multi-user support"""
        try:
            self.log_system_event('info', 'Starting AI strategy execution')
            
            # Get users with active credentials
            users = User.query.filter_by(is_active=True).all()
            successful_executions = 0
            
            for user in users:
                try:
                    # Get user's OpenAI credentials
                    openai_creds = APICredential.query.filter_by(
                        user_id=user.id,
                        provider='openai',
                        is_active=True
                    ).first()
                    
                    if not openai_creds:
                        continue
                    
                    # Execute AI strategy
                    result = self.execute_ai_logic(user.id, simulation_mode)
                    if result:
                        successful_executions += 1
                    
                except Exception as e:
                    self.log_system_event('error', f'Error in AI strategy for user {user.id}: {str(e)}')
                    continue
            
            self.log_system_event('info', f'AI strategy execution completed. Successful executions: {successful_executions}')
            
        except Exception as e:
            self.log_system_event('error', f'Error in AI strategy: {str(e)}')
            logging.error(f"Error in AI strategy: {str(e)}")
    
    def execute_ai_logic(self, user_id, simulation_mode):
        """Execute AI-driven strategy logic using OpenAI"""
        try:
            # Initialize OpenAI trader for this user
            openai_trader = OpenAITrader(user_id=user_id)

            # Test OpenAI connection first
            connection_test = openai_trader.test_connection()
            if not connection_test.get('success'):
                self.log_system_event(
                    'warning',
                    f'OpenAI API not available for user {user_id}: {connection_test.get("message")}'
                )
                return False

            # Define AI strategy watchlist
            ai_watchlist = ['AAPL', 'GOOGL', 'MSFT', 'NVDA', 'TSLA']
            trades_executed = 0

            for symbol in ai_watchlist:
                try:
                    # Get current market data
                    stock_price = self._get_simulated_stock_price(symbol)
                    market_data = {
                        'price': stock_price,
                        'change': random.uniform(-5, 5),
                        'change_percent': random.uniform(-2, 2),
                        'volume': random.randint(1000000, 10000000)
                    }

                    # Analyze market conditions using AI helper
                    analysis = self.ai_helper.analyze_market_conditions(symbol, market_data)

                    # Use OpenAI to generate trading strategy recommendation
                    strategy_prompt = f"""Analyze {symbol} trading opportunity:

Current Price: ${stock_price:.2f}
Trend: {analysis['trend']}
Volume Signal: {analysis['volume_signal']}
Momentum Score: {analysis['momentum_score']}

Provide a trading recommendation (BUY/SELL/HOLD) with reasoning."""

                    # Parse trading recommendation using OpenAI
                    recommendation_result = openai_trader.parse_trading_prompt(strategy_prompt)

                    if recommendation_result.get('success'):
                        instruction = recommendation_result.get('instruction', {})
                        action = instruction.get('action', 'HOLD').upper()
                        confidence = instruction.get('confidence', 0.5)

                        # Only execute if confidence is high enough
                        if action in ['BUY', 'SELL'] and confidence >= 0.7:
                            # Determine quantity based on AI recommendation
                            quantity = instruction.get('quantity', 10)

                            # Create comprehensive execution details
                            execution_details = {
                                'strategy_type': 'ai_driven',
                                'symbol': symbol,
                                'stock_price': stock_price,
                                'action': action,
                                'confidence': confidence,
                                'quantity': quantity,
                                'market_analysis': analysis,
                                'ai_reasoning': instruction.get('conditions', ''),
                                'trend': analysis['trend'],
                                'momentum_score': analysis['momentum_score']
                            }

                            # Create AI-driven trade record
                            trade = Trade(
                                user_id=user_id,
                                provider='schwab',  # Assuming trades execute through Schwab
                                symbol=symbol,
                                side=action.lower(),
                                quantity=quantity,
                                price=stock_price,
                                trade_type='ai_recommendation',
                                strategy='ai',
                                status='executed' if simulation_mode else 'pending',
                                is_simulation=simulation_mode,
                                executed_at=datetime.utcnow() if simulation_mode else None,
                                execution_details=json.dumps(execution_details)
                            )

                            db.session.add(trade)
                            db.session.commit()

                            trades_executed += 1

                            self.log_system_event(
                                'info',
                                f'AI strategy executed for user {user_id}: {action} {quantity} shares of {symbol} '
                                f'at ${stock_price:.2f} (confidence: {confidence:.1%})'
                            )

                except Exception as e:
                    self.log_system_event('error', f'Error processing AI strategy for {symbol}: {str(e)}')
                    continue

            self.log_system_event('info', f'AI strategy completed {trades_executed} trades for user {user_id}')
            return trades_executed > 0

        except Exception as e:
            self.log_system_event('error', f'Error in AI strategy execution: {str(e)}')
            return False

    def _get_simulated_stock_price(self, symbol: str) -> float:
        """
        Get simulated stock price for testing
        In production, this would fetch real market data
        """
        # Base prices for common symbols
        base_prices = {
            'AAPL': 175.0,
            'MSFT': 380.0,
            'GOOGL': 140.0,
            'TSLA': 240.0,
            'NVDA': 480.0,
            'AMZN': 145.0,
            'META': 310.0,
            'SPY': 450.0,
            'QQQ': 385.0,
            'IWM': 195.0
        }

        base_price = base_prices.get(symbol, 100.0)

        # Add some random variation (+/- 2%)
        variation = random.uniform(-0.02, 0.02)
        current_price = base_price * (1 + variation)

        return round(current_price, 2)

    def _check_user_has_shares(self, user_id: int, symbol: str) -> bool:
        """
        Check if user has shares of a given symbol
        In production, this would check actual portfolio holdings

        For simulation:
        - Assume users have shares of SPY, QQQ, IWM (ETFs for collar)
        - Randomly assign shares for other symbols (50% chance)
        """
        # ETFs are commonly held for collar strategies
        if symbol in ['SPY', 'QQQ', 'IWM']:
            return True

        # For other symbols, use deterministic "random" based on user_id and symbol
        # This ensures consistent behavior across runs
        import hashlib
        hash_input = f"{user_id}:{symbol}"
        hash_value = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)

        return hash_value % 2 == 0  # 50% chance of having shares


def run_auto_trading():
    """Main function to run auto-trading cycle"""
    engine = AutoTradingEngine()
    engine.run_auto_trading_cycle()