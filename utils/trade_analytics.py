"""
Comprehensive Trade Analytics Engine for Arbion Trading Platform
Calculates performance metrics, risk analytics, and trading insights
"""

import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Union
from sqlalchemy import func, and_, or_
import numpy as np
import pandas as pd
from app import db
from models import Trade, TradeAnalytics, Portfolio, PerformanceBenchmark, User

class TradeAnalyticsEngine:
    """Advanced trade analytics and performance calculation engine"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.logger = logging.getLogger(__name__)
    
    def calculate_portfolio_metrics(self, provider: str = None) -> Dict:
        """Calculate comprehensive portfolio metrics"""
        try:
            # Build query for user's trades
            query = Trade.query.filter_by(user_id=self.user_id, status='executed')
            if provider:
                query = query.filter_by(provider=provider)
            
            trades = query.all()
            
            if not trades:
                return self._empty_metrics()
            
            # Calculate basic metrics
            total_trades = len(trades)
            winning_trades = len([t for t in trades if (t.realized_pnl or 0) > 0])
            losing_trades = len([t for t in trades if (t.realized_pnl or 0) < 0])
            
            total_pnl = sum([(t.realized_pnl or 0) for t in trades])
            total_volume = sum([(t.amount or 0) for t in trades])
            total_fees = sum([(t.fees or 0) + (t.commission or 0) for t in trades])
            
            # Calculate win rate and profit metrics
            win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
            
            winning_amounts = [t.realized_pnl for t in trades if (t.realized_pnl or 0) > 0]
            losing_amounts = [abs(t.realized_pnl) for t in trades if (t.realized_pnl or 0) < 0]
            
            avg_win = np.mean(winning_amounts) if winning_amounts else 0
            avg_loss = np.mean(losing_amounts) if losing_amounts else 0
            
            # Calculate profit factor
            gross_profit = sum(winning_amounts) if winning_amounts else 0
            gross_loss = sum(losing_amounts) if losing_amounts else 1  # Avoid division by zero
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            
            # Calculate returns and Sharpe ratio
            returns = [self._calculate_trade_return(t) for t in trades if t.price and t.quantity]
            returns = [r for r in returns if r != 0]  # Remove zero returns
            
            if returns:
                avg_return = np.mean(returns)
                return_std = np.std(returns) if len(returns) > 1 else 0
                sharpe_ratio = (avg_return / return_std) if return_std > 0 else 0
                max_drawdown = self._calculate_max_drawdown(trades)
            else:
                avg_return = 0
                sharpe_ratio = 0
                max_drawdown = 0
            
            # Calculate strategy breakdown
            strategy_breakdown = {}
            for strategy in ['manual', 'ai', 'wheel', 'collar']:
                strategy_trades = [t for t in trades if t.strategy == strategy]
                strategy_breakdown[strategy] = {
                    'count': len(strategy_trades),
                    'pnl': sum([(t.realized_pnl or 0) for t in strategy_trades]),
                    'volume': sum([(t.amount or 0) for t in strategy_trades])
                }
            
            # Calculate recent performance (last 30 days)
            recent_date = datetime.utcnow() - timedelta(days=30)
            recent_trades = [t for t in trades if t.executed_at and t.executed_at >= recent_date]
            recent_pnl = sum([(t.realized_pnl or 0) for t in recent_trades])
            recent_trades_count = len(recent_trades)
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': round(win_rate, 2),
                'total_pnl': round(total_pnl, 2),
                'total_volume': round(total_volume, 2),
                'total_fees': round(total_fees, 2),
                'net_pnl': round(total_pnl - total_fees, 2),
                'avg_win': round(avg_win, 2),
                'avg_loss': round(avg_loss, 2),
                'profit_factor': round(profit_factor, 2),
                'avg_return': round(avg_return, 2),
                'sharpe_ratio': round(sharpe_ratio, 2),
                'max_drawdown': round(max_drawdown, 2),
                'strategy_breakdown': strategy_breakdown,
                'recent_performance': {
                    'trades_count': recent_trades_count,
                    'pnl': round(recent_pnl, 2)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio metrics: {str(e)}")
            return self._empty_metrics()
    
    def calculate_daily_analytics(self, target_date: Optional[date] = None) -> Dict:
        """Calculate analytics for a specific date"""
        if not target_date:
            target_date = date.today()
        
        try:
            # Get trades for the specific date
            start_datetime = datetime.combine(target_date, datetime.min.time())
            end_datetime = datetime.combine(target_date, datetime.max.time())
            
            trades = Trade.query.filter(
                Trade.user_id == self.user_id,
                Trade.executed_at.between(start_datetime, end_datetime),
                Trade.status == 'executed'
            ).all()
            
            if not trades:
                return self._empty_daily_metrics()
            
            # Calculate daily metrics
            total_trades = len(trades)
            winning_trades = len([t for t in trades if (t.realized_pnl or 0) > 0])
            losing_trades = len([t for t in trades if (t.realized_pnl or 0) < 0])
            
            total_pnl = sum([(t.realized_pnl or 0) for t in trades])
            total_volume = sum([(t.amount or 0) for t in trades])
            
            win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
            
            # Strategy breakdown
            strategy_counts = {}
            for strategy in ['manual', 'ai', 'wheel', 'collar']:
                strategy_counts[f'{strategy}_trades'] = len([t for t in trades if t.strategy == strategy])
            
            return {
                'date': target_date.isoformat(),
                'trades_count': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': round(win_rate, 2),
                'total_pnl': round(total_pnl, 2),
                'total_volume': round(total_volume, 2),
                **strategy_counts
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating daily analytics: {str(e)}")
            return self._empty_daily_metrics()
    
    def get_performance_timeline(self, days: int = 30) -> List[Dict]:
        """Get performance timeline for the last N days"""
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            timeline = []
            current_date = start_date
            cumulative_pnl = 0
            
            while current_date <= end_date:
                daily_analytics = self.calculate_daily_analytics(current_date)
                cumulative_pnl += daily_analytics.get('total_pnl', 0)
                
                timeline.append({
                    'date': current_date.isoformat(),
                    'daily_pnl': daily_analytics.get('total_pnl', 0),
                    'cumulative_pnl': round(cumulative_pnl, 2),
                    'trades_count': daily_analytics.get('trades_count', 0),
                    'win_rate': daily_analytics.get('win_rate', 0)
                })
                
                current_date += timedelta(days=1)
            
            return timeline
            
        except Exception as e:
            self.logger.error(f"Error getting performance timeline: {str(e)}")
            return []
    
    def get_symbol_performance(self, limit: int = 10) -> List[Dict]:
        """Get top performing symbols"""
        try:
            # Group trades by symbol and calculate metrics
            symbol_data = {}
            
            trades = Trade.query.filter_by(user_id=self.user_id, status='executed').all()
            
            for trade in trades:
                symbol = trade.symbol
                if symbol not in symbol_data:
                    symbol_data[symbol] = {
                        'symbol': symbol,
                        'trades_count': 0,
                        'total_pnl': 0,
                        'total_volume': 0,
                        'winning_trades': 0,
                        'losing_trades': 0
                    }
                
                symbol_data[symbol]['trades_count'] += 1
                symbol_data[symbol]['total_pnl'] += (trade.realized_pnl or 0)
                symbol_data[symbol]['total_volume'] += (trade.amount or 0)
                
                if (trade.realized_pnl or 0) > 0:
                    symbol_data[symbol]['winning_trades'] += 1
                elif (trade.realized_pnl or 0) < 0:
                    symbol_data[symbol]['losing_trades'] += 1
            
            # Calculate additional metrics
            for symbol, data in symbol_data.items():
                total_trades = data['trades_count']
                data['win_rate'] = (data['winning_trades'] / total_trades * 100) if total_trades > 0 else 0
                data['avg_pnl'] = data['total_pnl'] / total_trades if total_trades > 0 else 0
                data['total_pnl'] = round(data['total_pnl'], 2)
                data['total_volume'] = round(data['total_volume'], 2)
                data['win_rate'] = round(data['win_rate'], 2)
                data['avg_pnl'] = round(data['avg_pnl'], 2)
            
            # Sort by total P&L and return top performers
            sorted_symbols = sorted(symbol_data.values(), key=lambda x: x['total_pnl'], reverse=True)
            return sorted_symbols[:limit]
            
        except Exception as e:
            self.logger.error(f"Error getting symbol performance: {str(e)}")
            return []
    
    def calculate_risk_metrics(self) -> Dict:
        """Calculate comprehensive risk metrics"""
        try:
            trades = Trade.query.filter_by(user_id=self.user_id, status='executed').all()
            
            if not trades:
                return {'error': 'No trades found'}
            
            # Calculate returns for risk metrics
            returns = []
            for trade in trades:
                if trade.price and trade.quantity and trade.amount:
                    trade_return = self._calculate_trade_return(trade)
                    if trade_return != 0:
                        returns.append(trade_return)
            
            if not returns:
                return {'error': 'No valid returns found'}
            
            returns = np.array(returns)
            
            # Calculate risk metrics
            portfolio_volatility = np.std(returns) * np.sqrt(252)  # Annualized
            var_95 = np.percentile(returns, 5)  # 95% Value at Risk
            var_99 = np.percentile(returns, 1)  # 99% Value at Risk
            
            # Expected Shortfall (Conditional VaR)
            es_95 = np.mean(returns[returns <= var_95]) if len(returns[returns <= var_95]) > 0 else 0
            es_99 = np.mean(returns[returns <= var_99]) if len(returns[returns <= var_99]) > 0 else 0
            
            # Maximum consecutive losses
            consecutive_losses = self._calculate_consecutive_losses(trades)
            
            # Current portfolio concentration (top 5 positions)
            concentration = self._calculate_portfolio_concentration()
            
            return {
                'portfolio_volatility': round(portfolio_volatility * 100, 2),
                'value_at_risk_95': round(var_95 * 100, 2),
                'value_at_risk_99': round(var_99 * 100, 2),
                'expected_shortfall_95': round(es_95 * 100, 2),
                'expected_shortfall_99': round(es_99 * 100, 2),
                'max_consecutive_losses': consecutive_losses,
                'portfolio_concentration': concentration,
                'total_trades_analyzed': len(returns)
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating risk metrics: {str(e)}")
            return {'error': str(e)}
    
    def _calculate_trade_return(self, trade: Trade) -> float:
        """Calculate return percentage for a single trade"""
        if not trade.price or not trade.quantity or not trade.amount:
            return 0.0
        
        if trade.realized_pnl is not None:
            return (trade.realized_pnl / trade.amount) if trade.amount > 0 else 0.0
        
        return 0.0
    
    def _calculate_max_drawdown(self, trades: List[Trade]) -> float:
        """Calculate maximum drawdown"""
        if not trades:
            return 0.0
        
        # Sort trades by execution date
        sorted_trades = sorted([t for t in trades if t.executed_at], key=lambda x: x.executed_at)
        
        if not sorted_trades:
            return 0.0
        
        # Calculate running P&L
        running_pnl = 0
        peak = 0
        max_drawdown = 0
        
        for trade in sorted_trades:
            running_pnl += (trade.realized_pnl or 0)
            
            if running_pnl > peak:
                peak = running_pnl
            
            drawdown = (peak - running_pnl) / peak if peak > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)
        
        return max_drawdown * 100
    
    def _calculate_consecutive_losses(self, trades: List[Trade]) -> int:
        """Calculate maximum consecutive losing trades"""
        if not trades:
            return 0
        
        # Sort trades by execution date
        sorted_trades = sorted([t for t in trades if t.executed_at and t.realized_pnl is not None], 
                             key=lambda x: x.executed_at)
        
        max_consecutive = 0
        current_consecutive = 0
        
        for trade in sorted_trades:
            if (trade.realized_pnl or 0) < 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
        
        return max_consecutive
    
    def _calculate_portfolio_concentration(self) -> Dict:
        """Calculate portfolio concentration metrics"""
        try:
            # Get current open positions (simplified - assumes latest trades per symbol)
            latest_trades = {}
            trades = Trade.query.filter_by(user_id=self.user_id, status='executed').all()
            
            for trade in trades:
                symbol = trade.symbol
                if symbol not in latest_trades or trade.executed_at > latest_trades[symbol].executed_at:
                    latest_trades[symbol] = trade
            
            if not latest_trades:
                return {'top_5_concentration': 0, 'symbols_count': 0}
            
            # Calculate position values (simplified)
            positions = []
            total_value = 0
            
            for symbol, trade in latest_trades.items():
                position_value = abs(trade.amount or 0)
                total_value += position_value
                positions.append({'symbol': symbol, 'value': position_value})
            
            # Sort by value and get top 5
            positions.sort(key=lambda x: x['value'], reverse=True)
            top_5_value = sum([p['value'] for p in positions[:5]])
            
            concentration = (top_5_value / total_value * 100) if total_value > 0 else 0
            
            return {
                'top_5_concentration': round(concentration, 2),
                'symbols_count': len(positions),
                'largest_position': positions[0]['symbol'] if positions else None
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio concentration: {str(e)}")
            return {'top_5_concentration': 0, 'symbols_count': 0}
    
    def _empty_metrics(self) -> Dict:
        """Return empty metrics structure"""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'total_volume': 0,
            'total_fees': 0,
            'net_pnl': 0,
            'avg_win': 0,
            'avg_loss': 0,
            'profit_factor': 0,
            'avg_return': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'strategy_breakdown': {},
            'recent_performance': {'trades_count': 0, 'pnl': 0}
        }
    
    def _empty_daily_metrics(self) -> Dict:
        """Return empty daily metrics structure"""
        return {
            'date': date.today().isoformat(),
            'trades_count': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_pnl': 0,
            'total_volume': 0,
            'manual_trades': 0,
            'ai_trades': 0,
            'wheel_trades': 0,
            'collar_trades': 0
        }

class BenchmarkComparison:
    """Compare user performance against market benchmarks"""
    
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.logger = logging.getLogger(__name__)
    
    def compare_to_benchmark(self, benchmark_symbol: str = 'SPY', period_days: int = 30) -> Dict:
        """Compare user performance to benchmark"""
        try:
            # Import market data provider safely
            try:
                from utils.enhanced_market_data import ComprehensiveMarketDataProvider
                market_data = ComprehensiveMarketDataProvider()
            except ImportError:
                # Fallback if enhanced market data is not available
                return {'error': 'Market data provider not available'}
            
            # Get user performance
            analytics = TradeAnalyticsEngine(self.user_id)
            user_metrics = analytics.calculate_portfolio_metrics()
            
            # Get benchmark data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)
            
            benchmark_data = market_data.get_historical_data(benchmark_symbol, f'{period_days}d')
            
            if not benchmark_data or 'Close' not in benchmark_data:
                return {'error': f'Unable to fetch benchmark data for {benchmark_symbol}'}
            
            # Calculate benchmark return
            prices = list(benchmark_data['Close'].values())
            if len(prices) < 2:
                return {'error': 'Insufficient benchmark data'}
            
            start_price = prices[0]
            end_price = prices[-1]
            benchmark_return = ((end_price - start_price) / start_price) * 100
            
            # Calculate user return (simplified)
            user_return = user_metrics.get('avg_return', 0)
            
            # Calculate alpha (excess return)
            alpha = user_return - benchmark_return
            
            return {
                'benchmark_symbol': benchmark_symbol,
                'period_days': period_days,
                'user_return': round(user_return, 2),
                'benchmark_return': round(benchmark_return, 2),
                'alpha': round(alpha, 2),
                'outperforming': alpha > 0,
                'user_sharpe': user_metrics.get('sharpe_ratio', 0),
                'user_max_drawdown': user_metrics.get('max_drawdown', 0)
            }
            
        except Exception as e:
            self.logger.error(f"Error comparing to benchmark: {str(e)}")
            return {'error': str(e)}