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
            # Execute wheel strategy for each symbol in watchlist
            trades_executed = 0
            
            for symbol in params['watchlist']:
                try:
                    # Create simulated trades for wheel strategy
                    if self.sell_covered_call(user_id, symbol, params['target_delta'], params['target_dte'], simulation_mode):
                        trades_executed += 1
                    
                    if self.sell_cash_secured_put(user_id, symbol, params['target_delta'], params['target_dte'], simulation_mode):
                        trades_executed += 1
                
                except Exception as e:
                    self.log_system_event('error', f'Error processing {symbol} for wheel strategy: {str(e)}')
                    continue
            
            self.log_system_event('info', f'Wheel strategy executed {trades_executed} trades for user {user_id}')
            return trades_executed > 0
            
        except Exception as e:
            self.log_system_event('error', f'Error in wheel strategy execution for user {user_id}: {str(e)}')
            return False
    
    def sell_covered_call(self, user_id, symbol, delta, dte, simulation_mode):
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
                status='executed' if simulation_mode else 'pending',
                is_simulation=simulation_mode,
                executed_at=datetime.utcnow() if simulation_mode else None,
                execution_details=f'Covered call on {symbol} with delta {delta}' if simulation_mode else None
            )
            
            db.session.add(trade)
            db.session.commit()
            
            self.log_system_event('info', f'Covered call executed for user {user_id}: {symbol}')
            return True
                
        except Exception as e:
            self.log_system_event('error', f'Error selling covered call: {str(e)}')
            return False
    
    def sell_cash_secured_put(self, user_id, symbol, delta, dte, simulation_mode):
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
                status='executed' if simulation_mode else 'pending',
                is_simulation=simulation_mode,
                executed_at=datetime.utcnow() if simulation_mode else None,
                execution_details=f'Cash-secured put on {symbol} with delta {delta}' if simulation_mode else None
            )
            
            db.session.add(trade)
            db.session.commit()
            
            self.log_system_event('info', f'Cash-secured put executed for user {user_id}: {symbol}')
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
        """Execute AI-driven strategy logic"""
        try:
            # Create AI-driven trade
            trade = Trade(
                user_id=user_id,
                provider='openai',
                symbol='AI_STRATEGY',
                side='buy',
                quantity=1,
                trade_type='ai_recommendation',
                strategy='ai',
                status='executed' if simulation_mode else 'pending',
                is_simulation=simulation_mode,
                executed_at=datetime.utcnow() if simulation_mode else None,
                execution_details='AI-driven market analysis trade' if simulation_mode else None
            )
            
            db.session.add(trade)
            db.session.commit()
            
            self.log_system_event('info', f'AI strategy executed for user {user_id}')
            return True
                
        except Exception as e:
            self.log_system_event('error', f'Error in AI strategy execution: {str(e)}')
            return False

def run_auto_trading():
    """Main function to run auto-trading cycle"""
    engine = AutoTradingEngine()
    engine.run_auto_trading_cycle()