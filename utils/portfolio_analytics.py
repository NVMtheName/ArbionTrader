import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import func, and_, or_
from models import User, Trade, APICredential
from app import db
import numpy as np

logger = logging.getLogger(__name__)

class PortfolioAnalytics:
    """Advanced portfolio analytics and performance tracking"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def get_portfolio_overview(self, user_id: int, period_days: int = 30) -> Dict:
        """Get comprehensive portfolio overview for user"""
        try:
            from app import app
            with app.app_context():
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=period_days)
                
                # Get all trades for the period
                trades = Trade.query.filter(
                    and_(
                        Trade.user_id == user_id,
                        Trade.created_at >= start_date,
                        Trade.status == 'executed'
                    )
                ).order_by(Trade.created_at.desc()).all()
                
                # Calculate performance metrics
                total_pnl = 0
                winning_trades = 0
                losing_trades = 0
                total_volume = 0
                strategy_performance = {}
                provider_performance = {}
                daily_pnl = {}
                
                for trade in trades:
                    # Extract P&L from execution details
                    pnl = self._extract_pnl(trade)
                    total_pnl += pnl
                    total_volume += trade.amount or 0
                    
                    # Track wins/losses
                    if pnl > 0:
                        winning_trades += 1
                    elif pnl < 0:
                        losing_trades += 1
                    
                    # Strategy performance breakdown
                    strategy = trade.strategy or 'manual'
                    if strategy not in strategy_performance:
                        strategy_performance[strategy] = {'trades': 0, 'pnl': 0, 'volume': 0}
                    strategy_performance[strategy]['trades'] += 1
                    strategy_performance[strategy]['pnl'] += pnl
                    strategy_performance[strategy]['volume'] += trade.amount or 0
                    
                    # Provider performance breakdown
                    provider = trade.provider
                    if provider not in provider_performance:
                        provider_performance[provider] = {'trades': 0, 'pnl': 0, 'volume': 0}
                    provider_performance[provider]['trades'] += 1
                    provider_performance[provider]['pnl'] += pnl
                    provider_performance[provider]['volume'] += trade.amount or 0
                    
                    # Daily P&L tracking
                    date_key = trade.created_at.strftime('%Y-%m-%d')
                    if date_key not in daily_pnl:
                        daily_pnl[date_key] = 0
                    daily_pnl[date_key] += pnl
                
                # Calculate key metrics
                total_trades = len(trades)
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                avg_win = sum(self._extract_pnl(t) for t in trades if self._extract_pnl(t) > 0) / winning_trades if winning_trades > 0 else 0
                avg_loss = sum(self._extract_pnl(t) for t in trades if self._extract_pnl(t) < 0) / losing_trades if losing_trades > 0 else 0
                profit_factor = abs(avg_win * winning_trades / (avg_loss * losing_trades)) if losing_trades > 0 and avg_loss != 0 else 0
                
                # Calculate Sharpe ratio (simplified)
                daily_returns = list(daily_pnl.values())
                sharpe_ratio = self._calculate_sharpe_ratio(daily_returns) if len(daily_returns) > 1 else 0
                
                # Calculate max drawdown
                max_drawdown = self._calculate_max_drawdown(daily_returns)
                
                return {
                    'period_days': period_days,
                    'total_trades': total_trades,
                    'total_pnl': round(total_pnl, 2),
                    'total_volume': round(total_volume, 2),
                    'win_rate': round(win_rate, 1),
                    'winning_trades': winning_trades,
                    'losing_trades': losing_trades,
                    'avg_win': round(avg_win, 2),
                    'avg_loss': round(avg_loss, 2),
                    'profit_factor': round(profit_factor, 2),
                    'sharpe_ratio': round(sharpe_ratio, 2),
                    'max_drawdown': round(max_drawdown, 2),
                    'strategy_performance': strategy_performance,
                    'provider_performance': provider_performance,
                    'daily_pnl': daily_pnl,
                    'last_updated': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting portfolio overview: {str(e)}")
            return {
                'error': f'Failed to get portfolio overview: {str(e)}',
                'total_trades': 0,
                'total_pnl': 0
            }
    
    def get_strategy_comparison(self, user_id: int, period_days: int = 90) -> Dict:
        """Compare performance across different trading strategies"""
        try:
            from app import app
            with app.app_context():
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=period_days)
                
                strategies = db.session.query(Trade.strategy).filter(
                    and_(
                        Trade.user_id == user_id,
                        Trade.created_at >= start_date,
                        Trade.status == 'executed',
                        Trade.strategy.isnot(None)
                    )
                ).distinct().all()
                
                strategy_data = {}
                
                for (strategy_name,) in strategies:
                    if not strategy_name:
                        continue
                        
                    strategy_trades = Trade.query.filter(
                        and_(
                            Trade.user_id == user_id,
                            Trade.strategy == strategy_name,
                            Trade.created_at >= start_date,
                            Trade.status == 'executed'
                        )
                    ).all()
                    
                    # Calculate strategy metrics
                    pnls = [self._extract_pnl(trade) for trade in strategy_trades]
                    total_pnl = sum(pnls)
                    winning_pnls = [p for p in pnls if p > 0]
                    losing_pnls = [p for p in pnls if p < 0]
                    
                    win_rate = len(winning_pnls) / len(pnls) * 100 if pnls else 0
                    avg_trade = total_pnl / len(pnls) if pnls else 0
                    volatility = np.std(pnls) if len(pnls) > 1 else 0
                    
                    strategy_data[strategy_name] = {
                        'total_trades': len(strategy_trades),
                        'total_pnl': round(total_pnl, 2),
                        'win_rate': round(win_rate, 1),
                        'avg_trade': round(avg_trade, 2),
                        'volatility': round(volatility, 2),
                        'winning_trades': len(winning_pnls),
                        'losing_trades': len(losing_pnls),
                        'best_trade': round(max(pnls), 2) if pnls else 0,
                        'worst_trade': round(min(pnls), 2) if pnls else 0
                    }
                
                return {
                    'period_days': period_days,
                    'strategies': strategy_data,
                    'last_updated': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting strategy comparison: {str(e)}")
            return {'error': f'Failed to compare strategies: {str(e)}'}
    
    def get_risk_metrics(self, user_id: int) -> Dict:
        """Calculate comprehensive risk metrics"""
        try:
            from app import app
            with app.app_context():
                # Get recent trades (last 90 days)
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=90)
                
                trades = Trade.query.filter(
                    and_(
                        Trade.user_id == user_id,
                        Trade.created_at >= start_date,
                        Trade.status == 'executed'
                    )
                ).all()
                
                if not trades:
                    return {'error': 'No trades found for risk analysis'}
                
                # Position analysis
                positions = {}
                total_exposure = 0
                
                for trade in trades:
                    symbol = trade.symbol
                    if symbol not in positions:
                        positions[symbol] = {'quantity': 0, 'exposure': 0}
                    
                    # Calculate net position
                    multiplier = 1 if trade.side == 'buy' else -1
                    positions[symbol]['quantity'] += trade.quantity * multiplier
                    positions[symbol]['exposure'] += (trade.amount or 0) * multiplier
                    total_exposure += abs(trade.amount or 0)
                
                # Calculate concentration risk
                max_position_exposure = max([abs(pos['exposure']) for pos in positions.values()]) if positions else 0
                concentration_risk = (max_position_exposure / total_exposure * 100) if total_exposure > 0 else 0
                
                # Sector exposure (simplified mapping)
                sector_map = {
                    'AAPL': 'Technology', 'MSFT': 'Technology', 'GOOGL': 'Technology', 'NVDA': 'Technology',
                    'AMZN': 'Consumer Discretionary', 'TSLA': 'Consumer Discretionary',
                    'JPM': 'Financial', 'BAC': 'Financial', 'WFC': 'Financial',
                    'JNJ': 'Healthcare', 'PFE': 'Healthcare', 'UNH': 'Healthcare',
                    'SPY': 'ETF', 'QQQ': 'ETF', 'IWM': 'ETF',
                    'BTC-USD': 'Cryptocurrency', 'ETH-USD': 'Cryptocurrency'
                }
                
                sector_exposure = {}
                for symbol, position in positions.items():
                    sector = sector_map.get(symbol, 'Other')
                    if sector not in sector_exposure:
                        sector_exposure[sector] = 0
                    sector_exposure[sector] += abs(position['exposure'])
                
                # Normalize sector exposure to percentages
                for sector in sector_exposure:
                    sector_exposure[sector] = round(sector_exposure[sector] / total_exposure * 100, 1) if total_exposure > 0 else 0
                
                # Calculate VaR (Value at Risk) - simplified 5% VaR
                daily_pnls = []
                current_date = start_date
                while current_date <= end_date:
                    day_trades = [t for t in trades if t.created_at.date() == current_date.date()]
                    daily_pnl = sum(self._extract_pnl(trade) for trade in day_trades)
                    if daily_pnl != 0:
                        daily_pnls.append(daily_pnl)
                    current_date += timedelta(days=1)
                
                var_5 = np.percentile(daily_pnls, 5) if daily_pnls else 0
                
                return {
                    'total_positions': len([p for p in positions.values() if p['quantity'] != 0]),
                    'total_exposure': round(total_exposure, 2),
                    'concentration_risk': round(concentration_risk, 1),
                    'max_position_exposure': round(max_position_exposure, 2),
                    'sector_exposure': sector_exposure,
                    'var_5_percent': round(var_5, 2),
                    'positions': {k: v for k, v in positions.items() if v['quantity'] != 0},
                    'last_updated': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error calculating risk metrics: {str(e)}")
            return {'error': f'Failed to calculate risk metrics: {str(e)}'}
    
    def get_performance_timeline(self, user_id: int, period_days: int = 30) -> Dict:
        """Get detailed performance timeline data for charts"""
        try:
            from app import app
            with app.app_context():
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=period_days)
                
                trades = Trade.query.filter(
                    and_(
                        Trade.user_id == user_id,
                        Trade.created_at >= start_date,
                        Trade.status == 'executed'
                    )
                ).order_by(Trade.created_at.asc()).all()
                
                # Generate daily timeline
                timeline_data = []
                cumulative_pnl = 0
                current_date = start_date
                
                while current_date <= end_date:
                    day_trades = [t for t in trades if t.created_at.date() == current_date.date()]
                    daily_pnl = sum(self._extract_pnl(trade) for trade in day_trades)
                    cumulative_pnl += daily_pnl
                    
                    timeline_data.append({
                        'date': current_date.strftime('%Y-%m-%d'),
                        'daily_pnl': round(daily_pnl, 2),
                        'cumulative_pnl': round(cumulative_pnl, 2),
                        'trade_count': len(day_trades),
                        'volume': round(sum(trade.amount or 0 for trade in day_trades), 2)
                    })
                    
                    current_date += timedelta(days=1)
                
                return {
                    'period_days': period_days,
                    'timeline': timeline_data,
                    'last_updated': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Error getting performance timeline: {str(e)}")
            return {'error': f'Failed to get performance timeline: {str(e)}'}
    
    def _extract_pnl(self, trade: Trade) -> float:
        """Extract P&L from trade execution details"""
        try:
            if trade.execution_details:
                details = json.loads(trade.execution_details)
                return float(details.get('pnl', 0))
            return 0
        except:
            return 0
    
    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio for returns"""
        try:
            if len(returns) < 2:
                return 0
            
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            
            if std_return == 0:
                return 0
            
            # Assuming risk-free rate of 0 for simplicity
            return avg_return / std_return * np.sqrt(252)  # Annualized
        except:
            return 0
    
    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown"""
        try:
            if not returns:
                return 0
            
            cumulative = np.cumsum(returns)
            peak = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - peak)
            
            return float(np.min(drawdown))
        except:
            return 0