import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

class RiskManager:
    """Advanced risk management system for trading operations with stop-loss enforcement"""

    def __init__(self, db=None):
        self.logger = logging.getLogger(__name__)
        self.db = db  # Database session for trade updates
        
    def calculate_position_size(self, account_balance: float, risk_percentage: float, 
                              entry_price: float, stop_loss: float) -> int:
        """Calculate position size based on risk management rules"""
        try:
            if stop_loss >= entry_price:
                return 0
            
            # Calculate risk per share
            risk_per_share = abs(entry_price - stop_loss)
            
            # Calculate total risk amount
            total_risk = account_balance * (risk_percentage / 100)
            
            # Calculate position size
            position_size = int(total_risk / risk_per_share)
            
            # Ensure position size is reasonable
            max_position_value = account_balance * 0.2  # Max 20% of account
            max_shares = int(max_position_value / entry_price)
            
            return min(position_size, max_shares)
        
        except Exception as e:
            self.logger.error(f"Error calculating position size: {str(e)}")
            return 0
    
    def validate_trade_limits(self, user_id: int, trade_amount: float, 
                             symbol: str, user_role: str = 'standard') -> Tuple[bool, str]:
        """Validate trade against user limits and risk parameters"""
        try:
            # Set daily limits based on user role
            if user_role == 'superadmin':
                daily_limit = 1000000  # $1M
                trade_limit = 100000   # $100K per trade
            elif user_role == 'admin':
                daily_limit = 100000   # $100K
                trade_limit = 10000    # $10K per trade
            else:
                daily_limit = 10000    # $10K
                trade_limit = 1000     # $1K per trade
            
            # Check trade amount limit
            if trade_amount > trade_limit:
                return False, f"Trade amount exceeds limit of ${trade_limit:,.2f}"
            
            # For standalone operation without database, assume validation passes
            return True, "Trade validated successfully"
        
        except Exception as e:
            self.logger.error(f"Error validating trade limits: {str(e)}")
            return False, f"Validation error: {str(e)}"
    
    def calculate_portfolio_risk(self, user_id: int, mock_trades: List[Dict] = None) -> Dict:
        """Calculate overall portfolio risk metrics"""
        try:
            # Use mock trades for standalone operation
            if mock_trades is None:
                mock_trades = [
                    {'symbol': 'SPY', 'amount': 1000},
                    {'symbol': 'QQQ', 'amount': 800},
                    {'symbol': 'AAPL', 'amount': 500}
                ]
            
            if not mock_trades:
                return {
                    'total_exposure': 0,
                    'concentration_risk': 0,
                    'sector_exposure': {},
                    'risk_score': 0
                }
            
            # Calculate total exposure
            total_exposure = sum(trade.get('amount', 0) for trade in mock_trades)
            
            # Calculate concentration risk (max position as % of total)
            symbol_exposure = {}
            for trade in mock_trades:
                symbol = trade.get('symbol', '')
                if symbol not in symbol_exposure:
                    symbol_exposure[symbol] = 0
                symbol_exposure[symbol] += trade.get('amount', 0)
            
            max_position = max(symbol_exposure.values()) if symbol_exposure else 0
            concentration_risk = (max_position / total_exposure * 100) if total_exposure > 0 else 0
            
            # Simple sector mapping
            sector_map = {
                'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOGL': 'Technology',
                'AMZN': 'Consumer Discretionary', 'TSLA': 'Consumer Discretionary',
                'JPM': 'Financial', 'BAC': 'Financial', 'WFC': 'Financial',
                'JNJ': 'Healthcare', 'PFE': 'Healthcare', 'UNH': 'Healthcare',
                'SPY': 'ETF', 'QQQ': 'ETF', 'IWM': 'ETF',
                'BTC-USD': 'Cryptocurrency', 'ETH-USD': 'Cryptocurrency'
            }
            
            sector_exposure = {}
            for symbol, amount in symbol_exposure.items():
                sector = sector_map.get(symbol, 'Other')
                if sector not in sector_exposure:
                    sector_exposure[sector] = 0
                sector_exposure[sector] += amount
            
            # Calculate risk score (0-100)
            risk_score = 0
            
            # Concentration risk factor
            if concentration_risk > 50:
                risk_score += 30
            elif concentration_risk > 30:
                risk_score += 20
            elif concentration_risk > 20:
                risk_score += 10
            
            # Sector concentration factor
            max_sector_exposure = max(sector_exposure.values()) if sector_exposure else 0
            sector_concentration = (max_sector_exposure / total_exposure * 100) if total_exposure > 0 else 0
            
            if sector_concentration > 60:
                risk_score += 25
            elif sector_concentration > 40:
                risk_score += 15
            elif sector_concentration > 30:
                risk_score += 10
            
            # Number of positions factor
            num_positions = len(symbol_exposure)
            if num_positions < 3:
                risk_score += 20
            elif num_positions < 5:
                risk_score += 10
            
            return {
                'total_exposure': total_exposure,
                'concentration_risk': round(concentration_risk, 2),
                'sector_exposure': sector_exposure,
                'num_positions': num_positions,
                'risk_score': min(100, risk_score),
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            self.logger.error(f"Error calculating portfolio risk: {str(e)}")
            return {
                'total_exposure': 0,
                'concentration_risk': 0,
                'sector_exposure': {},
                'risk_score': 0,
                'error': str(e)
            }
    
    def check_margin_requirements(self, user_id: int, symbol: str, 
                                 quantity: int, price: float) -> Tuple[bool, str]:
        """Check if user has sufficient margin for the trade"""
        try:
            # This is a simplified margin check
            # In production, you'd integrate with broker APIs for real margin data
            
            trade_value = quantity * price
            
            # Get user's recent trades to estimate account balance
            recent_trades = Trade.query.filter(
                Trade.user_id == user_id,
                Trade.status == 'executed'
            ).order_by(Trade.created_at.desc()).limit(50).all()
            
            # Estimate available buying power (simplified)
            # This would come from broker API in production
            estimated_buying_power = 10000  # Default assumption
            
            # Calculate required margin (simplified)
            if symbol.endswith('-USD'):  # Crypto
                required_margin = trade_value  # 100% margin for crypto
            else:  # Stocks
                required_margin = trade_value * 0.5  # 50% margin for stocks
            
            if required_margin > estimated_buying_power:
                return False, f"Insufficient buying power. Required: ${required_margin:,.2f}, Available: ${estimated_buying_power:,.2f}"
            
            return True, "Margin requirements met"
        
        except Exception as e:
            self.logger.error(f"Error checking margin requirements: {str(e)}")
            return False, f"Margin check error: {str(e)}"
    
    def generate_risk_report(self, user_id: int) -> Dict:
        """Generate comprehensive risk report for user"""
        try:
            portfolio_risk = self.calculate_portfolio_risk(user_id)
            
            # Get recent trade performance
            recent_trades = Trade.query.filter(
                Trade.user_id == user_id,
                Trade.status == 'executed'
            ).order_by(Trade.created_at.desc()).limit(30).all()
            
            # Calculate win rate
            winning_trades = 0
            total_pnl = 0
            
            for trade in recent_trades:
                if trade.execution_details:
                    try:
                        details = json.loads(trade.execution_details)
                        pnl = details.get('pnl', 0)
                        total_pnl += pnl
                        if pnl > 0:
                            winning_trades += 1
                    except:
                        pass
            
            win_rate = (winning_trades / len(recent_trades) * 100) if recent_trades else 0
            
            # Risk recommendations
            recommendations = []
            
            if portfolio_risk['concentration_risk'] > 30:
                recommendations.append("Consider diversifying your portfolio to reduce concentration risk")
            
            if portfolio_risk['num_positions'] < 3:
                recommendations.append("Increase the number of positions to improve diversification")
            
            if win_rate < 40:
                recommendations.append("Review trading strategy as win rate is below 40%")
            
            if portfolio_risk['risk_score'] > 70:
                recommendations.append("Overall risk score is high. Consider reducing position sizes")
            
            return {
                'portfolio_risk': portfolio_risk,
                'win_rate': round(win_rate, 1),
                'total_pnl': round(total_pnl, 2),
                'num_trades': len(recent_trades),
                'recommendations': recommendations,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            self.logger.error(f"Error generating risk report: {str(e)}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def log_risk_event(self, user_id: int, event_type: str,
                      message: str, severity: str = 'info'):
        """Log risk management events"""
        try:
            # For standalone operation, just log to console
            self.logger.info(f"Risk Management - {event_type}: {message}")
        except Exception as e:
            self.logger.error(f"Error logging risk event: {str(e)}")

    def place_stop_loss_order(self, trade_id: int, stop_price: float,
                             api_client) -> Tuple[bool, str, Optional[str]]:
        """
        Place a stop-loss order at the broker for an open position

        Args:
            trade_id: Trade database ID
            stop_price: Stop loss trigger price
            api_client: Broker API client (SchwabAPIClient, CoinbaseConnector, etc.)

        Returns:
            Tuple of (success, message, stop_order_id)
        """
        try:
            from models import Trade

            trade = Trade.query.get(trade_id)
            if not trade:
                return False, f"Trade {trade_id} not found", None

            if trade.status != 'executed':
                return False, f"Trade {trade_id} is not executed (status: {trade.status})", None

            # Build stop-loss order based on provider
            if trade.provider == 'schwab':
                # Schwab stop-loss order structure
                stop_order = {
                    "orderType": "STOP",
                    "session": "NORMAL",
                    "duration": "GOOD_TILL_CANCEL",
                    "orderStrategyType": "SINGLE",
                    "stopPrice": stop_price,
                    "orderLegCollection": [
                        {
                            "instruction": "SELL" if trade.side == 'buy' else "BUY_TO_COVER",
                            "quantity": trade.quantity,
                            "instrument": {
                                "symbol": trade.symbol,
                                "assetType": "EQUITY"
                            }
                        }
                    ]
                }

                result = api_client.place_order(trade.account_hash, stop_order)

                if result.get('success'):
                    stop_order_id = result.get('order_id')

                    # Update trade with stop-loss info
                    trade.stop_loss_price = stop_price
                    trade.stop_loss_order_id = stop_order_id

                    if self.db:
                        self.db.session.commit()

                    self.logger.info(f"Placed stop-loss order {stop_order_id} for trade {trade_id} at ${stop_price}")
                    return True, f"Stop-loss order placed at ${stop_price}", stop_order_id
                else:
                    error_msg = result.get('message', 'Unknown error')
                    self.logger.error(f"Failed to place stop-loss for trade {trade_id}: {error_msg}")
                    return False, f"Failed to place stop-loss: {error_msg}", None

            elif trade.provider == 'coinbase':
                # Coinbase stop-loss order (using stop-limit)
                # Implementation would go here
                return False, "Coinbase stop-loss not yet implemented", None
            else:
                return False, f"Stop-loss not supported for provider: {trade.provider}", None

        except Exception as e:
            self.logger.error(f"Error placing stop-loss order: {str(e)}")
            return False, f"Stop-loss placement error: {str(e)}", None

    def monitor_stop_losses(self, user_id: int, api_client) -> Dict:
        """
        Monitor all open positions and enforce stop-losses
        CRITICAL: This should be called periodically (e.g., every minute via Celery task)

        Args:
            user_id: User ID to monitor positions for
            api_client: Broker API client

        Returns:
            Dict with monitoring results and actions taken
        """
        try:
            from models import Trade

            # Get all open positions with stop losses
            open_trades = Trade.query.filter(
                Trade.user_id == user_id,
                Trade.status == 'executed',
                Trade.stop_loss_price.isnot(None)
            ).all()

            results = {
                'trades_monitored': len(open_trades),
                'stop_losses_triggered': 0,
                'positions_closed': 0,
                'errors': [],
                'timestamp': datetime.utcnow().isoformat()
            }

            for trade in open_trades:
                try:
                    # Get current market price
                    if trade.provider == 'schwab':
                        market_data = api_client.get_market_data([trade.symbol])
                        if market_data and trade.symbol in market_data:
                            current_price = market_data[trade.symbol].get('mark', 0)
                        else:
                            self.logger.warning(f"Could not get market price for {trade.symbol}")
                            continue
                    else:
                        continue  # Skip non-Schwab for now

                    # Check if stop loss is breached
                    stop_triggered = False
                    if trade.side == 'buy' and current_price <= trade.stop_loss_price:
                        stop_triggered = True
                    elif trade.side == 'sell' and current_price >= trade.stop_loss_price:
                        stop_triggered = True

                    if stop_triggered:
                        self.logger.warning(
                            f"Stop loss triggered for trade {trade.id}: {trade.symbol} "
                            f"current=${current_price} stop=${trade.stop_loss_price}"
                        )
                        results['stop_losses_triggered'] += 1

                        # Force close the position
                        close_success, close_msg = self.force_close_position(trade.id, api_client,
                                                                             reason='stop_loss_triggered')
                        if close_success:
                            results['positions_closed'] += 1
                            self.log_risk_event(
                                user_id,
                                'STOP_LOSS_EXECUTED',
                                f"Position {trade.symbol} closed at ${current_price} (stop: ${trade.stop_loss_price})",
                                severity='warning'
                            )
                        else:
                            results['errors'].append({
                                'trade_id': trade.id,
                                'symbol': trade.symbol,
                                'error': close_msg
                            })

                except Exception as e:
                    self.logger.error(f"Error monitoring trade {trade.id}: {str(e)}")
                    results['errors'].append({
                        'trade_id': trade.id,
                        'error': str(e)
                    })

            return results

        except Exception as e:
            self.logger.error(f"Error in stop-loss monitoring: {str(e)}")
            return {
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }

    def force_close_position(self, trade_id: int, api_client,
                            reason: str = 'manual_close') -> Tuple[bool, str]:
        """
        Force close a position immediately with market order
        CRITICAL: Used for stop-loss enforcement and risk management

        Args:
            trade_id: Trade database ID to close
            api_client: Broker API client
            reason: Reason for closure (stop_loss_triggered, risk_limit_exceeded, manual_close)

        Returns:
            Tuple of (success, message)
        """
        try:
            from models import Trade

            trade = Trade.query.get(trade_id)
            if not trade:
                return False, f"Trade {trade_id} not found"

            if trade.status != 'executed':
                return False, f"Trade {trade_id} is not open (status: {trade.status})"

            # Cancel any existing stop-loss order first
            if trade.stop_loss_order_id and trade.provider == 'schwab':
                cancel_result = api_client.cancel_order(trade.account_hash, trade.stop_loss_order_id)
                if cancel_result.get('success'):
                    self.logger.info(f"Cancelled stop-loss order {trade.stop_loss_order_id}")

            # Build market order to close position
            if trade.provider == 'schwab':
                close_order = {
                    "orderType": "MARKET",
                    "session": "NORMAL",
                    "duration": "DAY",
                    "orderStrategyType": "SINGLE",
                    "orderLegCollection": [
                        {
                            "instruction": "SELL" if trade.side == 'buy' else "BUY_TO_COVER",
                            "quantity": trade.quantity,
                            "instrument": {
                                "symbol": trade.symbol,
                                "assetType": "EQUITY"
                            }
                        }
                    ]
                }

                result = api_client.place_order(trade.account_hash, close_order)

                if result.get('success'):
                    # Update trade status
                    trade.status = 'closed'
                    trade.exit_date = datetime.utcnow()

                    # Add note about closure reason
                    current_notes = trade.trade_notes or ''
                    trade.trade_notes = f"{current_notes}\nClosed by system: {reason} at {datetime.utcnow().isoformat()}"

                    if self.db:
                        self.db.session.commit()

                    self.logger.info(f"Successfully closed position for trade {trade_id} (reason: {reason})")
                    return True, f"Position closed successfully (reason: {reason})"
                else:
                    error_msg = result.get('message', 'Unknown error')
                    self.logger.error(f"Failed to close position for trade {trade_id}: {error_msg}")
                    return False, f"Failed to close position: {error_msg}"

            else:
                return False, f"Force close not supported for provider: {trade.provider}"

        except Exception as e:
            self.logger.error(f"Error force closing position: {str(e)}")
            return False, f"Force close error: {str(e)}"

    def enforce_risk_limits(self, user_id: int, trade_amount: float,
                           symbol: str, user_role: str = 'standard') -> Tuple[bool, str]:
        """
        ENFORCED risk limit check - blocks trades that exceed limits
        This is called BEFORE placing any trade

        Args:
            user_id: User ID
            trade_amount: Trade amount in dollars
            symbol: Trading symbol
            user_role: User's role (determines limits)

        Returns:
            Tuple of (allowed, message) - If allowed=False, trade MUST be blocked
        """
        # First check basic limits
        passed, message = self.validate_trade_limits(user_id, trade_amount, symbol, user_role)

        if not passed:
            self.logger.warning(f"Trade blocked for user {user_id}: {message}")
            self.log_risk_event(user_id, 'TRADE_BLOCKED', message, severity='warning')
            return False, message

        # Check daily trading limit
        try:
            from models import Trade

            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

            today_trades = Trade.query.filter(
                Trade.user_id == user_id,
                Trade.created_at >= today_start,
                Trade.status.in_(['executed', 'pending'])
            ).all()

            today_volume = sum(t.amount or 0 for t in today_trades)

            # Set daily limits based on role
            if user_role == 'superadmin':
                daily_limit = 1000000
            elif user_role == 'admin':
                daily_limit = 100000
            else:
                daily_limit = 10000

            if today_volume + trade_amount > daily_limit:
                message = f"Daily trading limit exceeded. Used: ${today_volume:,.2f}, Limit: ${daily_limit:,.2f}"
                self.logger.warning(f"Daily limit exceeded for user {user_id}: {message}")
                self.log_risk_event(user_id, 'DAILY_LIMIT_EXCEEDED', message, severity='error')
                return False, message

            return True, "Risk limits check passed"

        except Exception as e:
            self.logger.error(f"Error enforcing risk limits: {str(e)}")
            # FAIL CLOSED - if we can't verify limits, block the trade
            return False, f"Risk limit verification failed: {str(e)}"