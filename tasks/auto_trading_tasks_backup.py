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
import json

class AutoTradingEngine:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.market_data = MarketDataProvider()
        self.risk_manager = RiskManager()
        
    def log_system_event(self, level, message, module='auto_trading', user_id=None):
        """Log system events to database"""
        try:
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
            # Decrypt credentials
            credentials = decrypt_credentials(user_creds.encrypted_credentials)
            
            # Initialize appropriate connector
            if 'access_token' in credentials:
                # OAuth credentials - use Schwab API client
                try:
                    from utils.schwab_api import SchwabAPIClient
                    connector = SchwabAPIClient(user_id=user_id)
                except ImportError:
                    self.log_system_event('warning', f'SchwabAPIClient not available for user {user_id}')
                    return False
            else:
                # Legacy API key credentials
                connector = SchwabConnector(
                    credentials.get('api_key', ''),
                    credentials.get('secret', '')
                )
            
            # Test connection first
            try:
                account_info = connector.get_account()
                if not account_info:
                    self.log_system_event('warning', f'Could not get account info for user {user_id}')
                    return False
            except Exception as e:
                self.log_system_event('error', f'Connection test failed for user {user_id}: {str(e)}')
                return False
            
            # Get current positions
            positions = connector.get_positions() if hasattr(connector, 'get_positions') else []
            
            # Execute wheel strategy for each symbol in watchlist
            trades_executed = 0
            
            for symbol in params['watchlist']:
                try:
                    # Get current stock price
                    stock_price = self.market_data.get_current_price(symbol)
                    if not stock_price:
                        continue
                    
                    # Check if we already have a position
                    existing_position = next((p for p in positions if p.get('symbol') == symbol), None)
                    
                    if existing_position and existing_position.get('quantity', 0) > 0:
                        # If we own stock, sell covered calls
                        if self.sell_covered_call(connector, account_info.get('accountId'), symbol, params['target_delta'], params['target_dte'], user_id, simulation_mode):
                            trades_executed += 1
                    else:
                        # If no position, sell cash-secured puts
                        if self.sell_cash_secured_put(connector, account_info.get('accountId'), symbol, params['target_delta'], params['target_dte'], user_id, simulation_mode):
                            trades_executed += 1
                
                except Exception as e:
                    self.log_system_event('error', f'Error processing {symbol} for wheel strategy: {str(e)}')
                    continue
            
            self.log_system_event('info', f'Wheel strategy executed {trades_executed} trades for user {user_id}')
            return trades_executed > 0
            
        except Exception as e:
            self.log_system_event('error', f'Error in wheel strategy execution for user {user_id}: {str(e)}')
            return False
    
    def sell_covered_call(self, connector, account_id, symbol, delta, dte, user_id, simulation_mode):
        """Sell covered call for wheel strategy"""
        try:
            # Create a covered call trade record
            trade = Trade(
                user_id=user_id,
                provider='schwab',
                symbol=symbol,
                side='sell',
                quantity=1,  # 1 options contract
                trade_type='covered_call',
                strategy='wheel',
                status='pending',
                is_simulation=simulation_mode
            )
            
            if simulation_mode:
                # Simulate the trade
                trade.status = 'executed'
                trade.executed_at = datetime.utcnow()
                trade.execution_details = f'Simulated covered call on {symbol} with delta {delta}'
                
                db.session.add(trade)
                db.session.commit()
                
                self.log_system_event('info', f'Simulated covered call executed for user {user_id}: {symbol}')
                return True
            else:
                # Execute actual trade (placeholder for real implementation)
                # In a real implementation, this would use the connector to place an actual options trade
                self.log_system_event('info', f'Live covered call would be executed for user {user_id}: {symbol}')
                return True
                
        except Exception as e:
            self.log_system_event('error', f'Error selling covered call: {str(e)}')
            return False
    
    def sell_cash_secured_put(self, connector, account_id, symbol, delta, dte, user_id, simulation_mode):
        """Sell cash-secured put for wheel strategy"""
        try:
            # Create a cash-secured put trade record
            trade = Trade(
                user_id=user_id,
                provider='schwab',
                symbol=symbol,
                side='sell',
                quantity=1,  # 1 options contract
                trade_type='cash_secured_put',
                strategy='wheel',
                status='pending',
                is_simulation=simulation_mode
            )
            
            if simulation_mode:
                # Simulate the trade
                trade.status = 'executed'
                trade.executed_at = datetime.utcnow()
                trade.execution_details = f'Simulated cash-secured put on {symbol} with delta {delta}'
                
                db.session.add(trade)
                db.session.commit()
                
                self.log_system_event('info', f'Simulated cash-secured put executed for user {user_id}: {symbol}')
                return True
            else:
                # Execute actual trade (placeholder for real implementation)
                # In a real implementation, this would use the connector to place an actual options trade
                self.log_system_event('info', f'Live cash-secured put would be executed for user {user_id}: {symbol}')
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
                    result = self.execute_collar_logic(creds, collar_params, user.id, simulation_mode)
                    if result:
                        successful_executions += 1
                    
                except Exception as e:
                    self.log_system_event('error', f'Error in collar strategy for user {user.id}: {str(e)}')
                    continue
            
            self.log_system_event('info', f'Collar strategy execution completed. Successful executions: {successful_executions}')
            
        except Exception as e:
            self.log_system_event('error', f'Error in collar strategy: {str(e)}')
            logging.error(f"Error in collar strategy: {str(e)}")
    
    def execute_collar_logic(self, user_creds, params, user_id, simulation_mode):
        """Execute collar strategy logic"""
        try:
            # Create collar trades (buy put, sell call)
            trades_executed = 0
            
            for symbol in params['watchlist']:
                try:
                    # Buy protective put
                    put_trade = Trade(
                        user_id=user_id,
                        provider='schwab',
                        symbol=symbol,
                        side='buy',
                        quantity=1,
                        trade_type='protective_put',
                        strategy='collar',
                        status='executed' if simulation_mode else 'pending',
                        is_simulation=simulation_mode,
                        executed_at=datetime.utcnow() if simulation_mode else None,
                        execution_details=f'Collar protective put on {symbol}' if simulation_mode else None
                    )
                    
                    # Sell covered call
                    call_trade = Trade(
                        user_id=user_id,
                        provider='schwab',
                        symbol=symbol,
                        side='sell',
                        quantity=1,
                        trade_type='covered_call',
                        strategy='collar',
                        status='executed' if simulation_mode else 'pending',
                        is_simulation=simulation_mode,
                        executed_at=datetime.utcnow() if simulation_mode else None,
                        execution_details=f'Collar covered call on {symbol}' if simulation_mode else None
                    )
                    
                    db.session.add(put_trade)
                    db.session.add(call_trade)
                    db.session.commit()
                    
                    trades_executed += 2
                    
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
                    result = self.execute_ai_logic(openai_creds, user.id, simulation_mode)
                    if result:
                        successful_executions += 1
                    
                except Exception as e:
                    self.log_system_event('error', f'Error in AI strategy for user {user.id}: {str(e)}')
                    continue
            
            self.log_system_event('info', f'AI strategy execution completed. Successful executions: {successful_executions}')
            
        except Exception as e:
            self.log_system_event('error', f'Error in AI strategy: {str(e)}')
            logging.error(f"Error in AI strategy: {str(e)}")
    
    def execute_ai_logic(self, openai_creds, user_id, simulation_mode):
        """Execute AI-driven strategy logic"""
        try:
            # Decrypt OpenAI credentials
            credentials = decrypt_credentials(openai_creds.encrypted_credentials)
            api_key = credentials.get('api_key')
            
            if not api_key:
                self.log_system_event('error', f'No OpenAI API key found for user {user_id}')
                return False
            
            # Initialize OpenAI trader
            trader = OpenAITrader(user_id=user_id)
            
            # Generate AI-driven trading instruction
            market_analysis = "Current market showing bullish momentum. Consider long positions in tech stocks."
            
            # Execute AI trade
            result = trader.execute_trade(
                market_analysis,
                user_id,
                is_simulation=simulation_mode
            )
            
            if result['success']:
                self.log_system_event('info', f'AI strategy executed for user {user_id}: {result["message"]}')
                return True
            else:
                self.log_system_event('error', f'AI strategy failed for user {user_id}: {result["message"]}')
                return False
                
        except Exception as e:
            self.log_system_event('error', f'Error in AI strategy execution: {str(e)}')
            return False

def run_auto_trading():
    """Main function to run auto-trading cycle"""
    engine = AutoTradingEngine()
    engine.run_auto_trading_cycle()

# End of AutoTradingEngine class
        """Execute wheel strategy logic"""
        try:
            # Default wheel strategy parameters
            symbol = params.get('symbol', 'SPY')
            cash_secured_put_delta = params.get('csp_delta', 0.3)
            covered_call_delta = params.get('cc_delta', 0.3)
            dte_target = params.get('dte', 30)
            
            # Get accounts
            accounts = connector.get_accounts()
            if not accounts:
                return {'success': False, 'message': 'No accounts found'}
            
            account_id = accounts[0]['accountId']
            
            # Get current positions
            positions = connector.get_positions(account_id)
            
            # Check if we own the underlying stock
            stock_position = None
            for pos in positions:
                if pos['instrument']['symbol'] == symbol:
                    stock_position = pos
                    break
            
            if stock_position and int(stock_position['quantity']) >= 100:
                # We own 100+ shares, sell covered calls
                result = self.sell_covered_call(connector, account_id, symbol, covered_call_delta, dte_target, user_id, simulation_mode)
            else:
                # We don't own enough shares, sell cash-secured puts
                result = self.sell_cash_secured_put(connector, account_id, symbol, cash_secured_put_delta, dte_target, user_id, simulation_mode)
            
            return result
        
        except Exception as e:
            return {'success': False, 'message': f'Wheel logic error: {str(e)}'}
    
    def sell_covered_call(self, connector, account_id, symbol, delta, dte, user_id, simulation_mode):
        """Sell covered call for wheel strategy"""
        try:
            # Get current market data
            current_price = connector.get_current_price(symbol)
            if not current_price:
                return {'success': False, 'message': 'Could not get current price'}
            
            # Get option chain to find appropriate strike
            option_chain = self.market_data.get_option_chain(symbol)
            if not option_chain:
                # Fallback to simple calculation if option chain not available
                strike_price = round(current_price * 1.02, 2)
            else:
                # Find strike closest to target delta
                calls = option_chain['calls']
                target_strike = None
                min_delta_diff = float('inf')
                
                for call in calls:
                    delta_diff = abs(call.get('delta', 0) - delta)
                    if delta_diff < min_delta_diff and call['strike'] > current_price:
                        min_delta_diff = delta_diff
                        target_strike = call['strike']
                
                strike_price = target_strike or round(current_price * 1.02, 2)
            
            # Validate trade against risk parameters
            estimated_premium = current_price * 0.02  # Rough estimate
            is_valid, message = self.risk_manager.validate_trade_limits(
                user_id, estimated_premium * 100, symbol
            )
            
            if not is_valid and not simulation_mode:
                return {'success': False, 'message': f'Risk validation failed: {message}'}
            
            # Calculate expiration date
            expiration = (datetime.utcnow() + timedelta(days=dte)).strftime('%Y-%m-%d')
            
            # Place the order
            result = connector.place_option_order(
                account_id=account_id,
                symbol=symbol,
                quantity=1,
                side='SELL_TO_OPEN',
                option_type='CALL',
                strike=strike_price,
                expiration=expiration,
                user_id=user_id,
                is_simulation=simulation_mode
            )
            
            # Log the trade attempt
            self.log_system_event(
                'info',
                f'Covered call order placed for {symbol} at ${strike_price} strike, exp: {expiration}',
                user_id=user_id
            )
            
            return result
        
        except Exception as e:
            self.logger.error(f"Error in covered call execution: {str(e)}")
            return {'success': False, 'message': f'Covered call error: {str(e)}'}
    
    def sell_cash_secured_put(self, connector, account_id, symbol, delta, dte, user_id, simulation_mode):
        """Sell cash-secured put for wheel strategy"""
        try:
            # This is a simplified implementation
            current_price = connector.get_current_price(symbol)
            if not current_price:
                return {'success': False, 'message': 'Could not get current price'}
            
            # Calculate approximate strike price (current price - 2%)
            strike_price = round(current_price * 0.98, 2)
            
            # Mock expiration date
            expiration = (datetime.utcnow() + timedelta(days=dte)).strftime('%Y-%m-%d')
            
            result = connector.place_option_order(
                account_id=account_id,
                symbol=symbol,
                quantity=1,
                side='SELL_TO_OPEN',
                option_type='PUT',
                strike=strike_price,
                expiration=expiration,
                user_id=user_id,
                is_simulation=simulation_mode
            )
            
            return result
        
        except Exception as e:
            return {'success': False, 'message': f'Cash-secured put error: {str(e)}'}
    
    def run_collar_strategy(self, simulation_mode=True):
        """Run collar strategy"""
        try:
            self.log_system_event('info', 'Running collar strategy')
            
            # Get active collar strategies
            collar_strategies = Strategy.query.filter_by(
                strategy_type='collar',
                is_active=True
            ).all()
            
            for strategy in collar_strategies:
                try:
                    # Get strategy parameters
                    params = strategy.get_parameters()
                    
                    # Get user's credentials
                    user_cred = APICredential.query.filter_by(
                        user_id=strategy.created_by,
                        provider='schwab',
                        is_active=True
                    ).first()
                    
                    if not user_cred:
                        continue
                    
                    # Execute collar strategy logic
                    result = self.execute_collar_logic(user_cred, params, strategy.created_by, simulation_mode)
                    
                    if result['success']:
                        self.log_system_event('info', f'Collar strategy {strategy.id} executed: {result["message"]}')
                    else:
                        self.log_system_event('error', f'Collar strategy {strategy.id} failed: {result["message"]}')
                
                except Exception as e:
                    self.log_system_event('error', f'Error in collar strategy {strategy.id}: {str(e)}')
        
        except Exception as e:
            self.logger.error(f"Error running collar strategy: {str(e)}")
            self.log_system_event('error', f'Collar strategy failed: {str(e)}')
    
    def execute_collar_logic(self, user_cred, params, user_id, simulation_mode):
        """Execute collar strategy logic"""
        try:
            # Simplified collar strategy implementation
            # In production, this would:
            # 1. Check current stock positions
            # 2. Buy protective puts
            # 3. Sell covered calls
            # 4. Monitor and adjust positions
            
            return {
                'success': True,
                'message': 'Collar strategy executed (simulated)'
            }
        
        except Exception as e:
            return {'success': False, 'message': f'Collar logic error: {str(e)}'}
    
    def run_ai_strategy(self, simulation_mode=True):
        """Run AI-driven strategy"""
        try:
            self.log_system_event('info', 'Running AI strategy')
            
            # Get users with AI strategies enabled
            ai_strategies = Strategy.query.filter_by(
                strategy_type='ai',
                is_active=True
            ).all()
            
            for strategy in ai_strategies:
                try:
                    # Get strategy parameters
                    params = strategy.get_parameters()
                    
                    # Get user's OpenAI credentials
                    openai_cred = APICredential.query.filter_by(
                        user_id=strategy.created_by,
                        provider='openai',
                        is_active=True
                    ).first()
                    
                    if not openai_cred:
                        continue
                    
                    # Execute AI strategy logic
                    result = self.execute_ai_logic(openai_cred, params, strategy.created_by, simulation_mode)
                    
                    if result['success']:
                        self.log_system_event('info', f'AI strategy {strategy.id} executed: {result["message"]}')
                    else:
                        self.log_system_event('error', f'AI strategy {strategy.id} failed: {result["message"]}')
                
                except Exception as e:
                    self.log_system_event('error', f'Error in AI strategy {strategy.id}: {str(e)}')
        
        except Exception as e:
            self.logger.error(f"Error running AI strategy: {str(e)}")
            self.log_system_event('error', f'AI strategy failed: {str(e)}')
    
    def execute_ai_logic(self, openai_cred, params, user_id, simulation_mode):
        """Execute AI-driven strategy logic"""
        try:
            # Decrypt OpenAI credentials
            credentials = decrypt_credentials(openai_cred.encrypted_credentials)
            
            # Initialize OpenAI trader
            trader = OpenAITrader(user_id=user_id)
            
            # Get market analysis from AI
            symbols = params.get('symbols', ['SPY', 'QQQ'])
            trades_executed = 0
            
            for symbol in symbols:
                try:
                    # Get comprehensive market data
                    market_quote = self.market_data.get_stock_quote(symbol)
                    technical_indicators = self.market_data.calculate_technical_indicators(symbol)
                    sentiment = self.market_data.get_market_sentiment(symbol)
                    
                    if not market_quote:
                        continue
                    
                    # Create comprehensive analysis prompt
                    analysis_prompt = f"""
                    Analyze {symbol} for trading opportunities using this data:
                    
                    Current Price: ${market_quote.get('price', 0):.2f}
                    Change: {market_quote.get('change_percent', 0):.2f}%
                    Volume: {market_quote.get('volume', 0):,}
                    
                    Technical Indicators:
                    - RSI: {technical_indicators.get('rsi', 0):.2f}
                    - SMA 20: ${technical_indicators.get('sma_20', 0):.2f}
                    - SMA 50: ${technical_indicators.get('sma_50', 0):.2f}
                    - MACD: {technical_indicators.get('macd', 0):.2f}
                    - MACD Signal: {technical_indicators.get('macd_signal', 0):.2f}
                    
                    Market Sentiment: {sentiment.get('sentiment_score', 50):.1f}% positive
                    
                    Provide a trading recommendation with high confidence only if conditions are favorable.
                    """
                    
                    analysis = trader.analyze_market_conditions(symbol, analysis_prompt)
                    
                    # Only execute trades with high confidence
                    if analysis['recommendation'] in ['buy', 'sell'] and analysis['confidence'] > 0.75:
                        # Calculate position size based on risk management
                        current_price = market_quote['price']
                        stop_loss_price = current_price * 0.98 if analysis['recommendation'] == 'buy' else current_price * 1.02
                        
                        # Get estimated account balance (simplified)
                        account_balance = 10000  # This would come from broker API
                        position_size = self.risk_manager.calculate_position_size(
                            account_balance, 2.0, current_price, stop_loss_price
                        )
                        
                        if position_size > 0:
                            # Validate trade limits
                            trade_amount = position_size * current_price
                            is_valid, message = self.risk_manager.validate_trade_limits(
                                user_id, trade_amount, symbol
                            )
                            
                            if is_valid or simulation_mode:
                                # Create trade prompt
                                trade_prompt = f"{analysis['recommendation']} {position_size} shares of {symbol} at market price. Reasoning: {analysis['reasoning']}"
                                
                                trade_instruction = trader.parse_trading_prompt(trade_prompt)
                                result = trader.execute_trade(trade_instruction, user_id, simulation_mode)
                                
                                if result['success']:
                                    trades_executed += 1
                                    self.log_system_event(
                                        'info',
                                        f'AI trade executed for {symbol}: {result["message"]} (Confidence: {analysis["confidence"]:.2f})',
                                        user_id=user_id
                                    )
                                else:
                                    self.log_system_event(
                                        'error',
                                        f'AI trade failed for {symbol}: {result["message"]}',
                                        user_id=user_id
                                    )
                            else:
                                self.log_system_event(
                                    'warning',
                                    f'AI trade for {symbol} blocked by risk management: {message}',
                                    user_id=user_id
                                )
                        else:
                            self.log_system_event(
                                'warning',
                                f'AI trade for {symbol} skipped: position size calculated as 0',
                                user_id=user_id
                            )
                    else:
                        self.log_system_event(
                            'info',
                            f'AI analysis for {symbol}: {analysis["recommendation"]} with {analysis["confidence"]:.2f} confidence (below threshold)',
                            user_id=user_id
                        )
                
                except Exception as e:
                    self.logger.error(f"Error in AI analysis for {symbol}: {str(e)}")
                    continue
            
            return {
                'success': True,
                'message': f'AI strategy completed. Executed {trades_executed} trades.'
            }
        
        except Exception as e:
            return {'success': False, 'message': f'AI logic error: {str(e)}'}

# Main function to run auto-trading
def run_auto_trading():
    """Main function to run auto-trading cycle"""
    try:
        engine = AutoTradingEngine()
        engine.run_auto_trading_cycle()
    except Exception as e:
        logging.error(f"Auto-trading execution failed: {str(e)}")

# This can be called by a scheduler (Heroku Scheduler, cron, etc.)
if __name__ == '__main__':
    run_auto_trading()
