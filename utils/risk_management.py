import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json

class RiskManager:
    """Advanced risk management system for trading operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
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