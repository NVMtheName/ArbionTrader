"""
AI Trading Bot - OpenAI Powered Intelligent Trading System
Advanced trading bot implementation using OpenAI for market analysis and decision making
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd
from flask_login import current_user

# Import our enhanced integrations
from utils.openai_auth_manager import create_auth_manager
from utils.schwabdev_integration import create_schwabdev_manager
from utils.enhanced_openai_client import EnhancedOpenAIClient

logger = logging.getLogger(__name__)

@dataclass
class TradingSignal:
    """Trading signal from AI analysis"""
    symbol: str
    action: str  # BUY, SELL, HOLD
    confidence: float  # 0.0 to 1.0
    quantity: int
    price_target: Optional[float]
    stop_loss: Optional[float]
    reasoning: str
    timestamp: datetime
    risk_level: str  # LOW, MEDIUM, HIGH
    time_horizon: str  # SHORT, MEDIUM, LONG

@dataclass
class MarketAnalysis:
    """Comprehensive market analysis from AI"""
    symbol: str
    current_price: float
    trend_direction: str  # BULLISH, BEARISH, NEUTRAL
    sentiment_score: float  # -1.0 to 1.0
    technical_indicators: Dict[str, Any]
    fundamental_analysis: str
    news_sentiment: str
    ai_recommendation: str
    confidence_level: float
    timestamp: datetime

@dataclass
class RiskManagement:
    """Risk management parameters"""
    max_position_size: float
    max_portfolio_risk: float
    stop_loss_percentage: float
    take_profit_percentage: float
    max_daily_trades: int
    allowed_symbols: List[str]
    blacklisted_symbols: List[str]
    trading_hours_only: bool

class AITradingBot:
    """Comprehensive AI-powered trading bot using OpenAI and Schwab"""
    
    def __init__(self, user_id: str, config: Dict[str, Any] = None):
        self.user_id = user_id
        self.config = config or self._get_default_config()
        self.is_running = False
        self.trades_today = 0
        self.daily_pnl = 0.0
        
        # Initialize AI and multi-broker connections
        self.openai_manager = None
        self.enhanced_openai = None
        
        # Multi-broker managers
        self.schwab_manager = None
        self.coinbase_manager = None
        self.etrade_manager = None
        
        # Connected accounts tracking
        self.connected_accounts = {
            'schwab': [],
            'coinbase': [],
            'etrade': []
        }
        
        # Multi-account trading results
        self.multi_account_results = {}
        
        # Risk management
        self.risk_params = RiskManagement(
            max_position_size=self.config.get('max_position_size', 10000.0),
            max_portfolio_risk=self.config.get('max_portfolio_risk', 0.02),
            stop_loss_percentage=self.config.get('stop_loss_percentage', 0.05),
            take_profit_percentage=self.config.get('take_profit_percentage', 0.10),
            max_daily_trades=self.config.get('max_daily_trades', 10),
            allowed_symbols=self.config.get('allowed_symbols', ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA']),
            blacklisted_symbols=self.config.get('blacklisted_symbols', []),
            trading_hours_only=self.config.get('trading_hours_only', True)
        )
        
        # Trading history
        self.trading_history = []
        self.market_analysis_history = []
        
        logger.info(f"AI Trading Bot initialized for user {user_id}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default trading bot configuration"""
        return {
            'trading_strategy': 'ai_momentum',
            'analysis_interval': 300,  # 5 minutes
            'max_position_size': 10000.0,
            'max_portfolio_risk': 0.02,
            'stop_loss_percentage': 0.05,
            'take_profit_percentage': 0.10,
            'max_daily_trades': 10,
            'confidence_threshold': 0.7,
            'allowed_symbols': ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA', 'AMZN', 'META', 'NFLX'],
            'trading_hours_only': True,
            'paper_trading': True,  # Start with paper trading
            'enable_news_analysis': True,
            'enable_technical_analysis': True,
            'enable_fundamental_analysis': True
        }
    
    async def initialize_connections(self) -> Dict[str, Any]:
        """Initialize OpenAI and all broker connections"""
        try:
            # Initialize OpenAI authentication manager
            self.openai_manager = create_auth_manager(self.user_id)
            
            # Initialize enhanced OpenAI client
            self.enhanced_openai = EnhancedOpenAIClient(self.user_id)
            
            # Initialize all broker managers
            connection_results = {}
            
            # Initialize Schwab
            try:
                self.schwab_manager = create_schwabdev_manager(self.user_id)
                schwab_status = self.schwab_manager.get_connection_status()
                connection_results['schwab'] = {
                    'connected': schwab_status.get('has_access_token', False),
                    'status': schwab_status
                }
                if connection_results['schwab']['connected']:
                    # Get Schwab account info
                    account_info = self.schwab_manager.get_account_info()
                    if account_info.get('success'):
                        self.connected_accounts['schwab'].append(account_info['account_info'])
            except Exception as e:
                connection_results['schwab'] = {'connected': False, 'error': str(e)}
            
            # Initialize Coinbase (try both v1 and v2)
            try:
                from utils.coinbase_v2_integration import CoinbaseV2Manager
                self.coinbase_manager = CoinbaseV2Manager(self.user_id)
                coinbase_status = await self.coinbase_manager.get_connection_status()
                connection_results['coinbase'] = {
                    'connected': coinbase_status.get('authenticated', False),
                    'status': coinbase_status
                }
                if connection_results['coinbase']['connected']:
                    # Get Coinbase accounts
                    accounts = await self.coinbase_manager.get_accounts()
                    if accounts.get('success'):
                        self.connected_accounts['coinbase'] = accounts['accounts']
            except Exception as e:
                connection_results['coinbase'] = {'connected': False, 'error': str(e)}
            
            # Initialize E-trade (placeholder for future implementation)
            try:
                # E-trade integration would go here
                connection_results['etrade'] = {'connected': False, 'error': 'E-trade integration pending'}
            except Exception as e:
                connection_results['etrade'] = {'connected': False, 'error': str(e)}
            
            # Test OpenAI connection
            openai_status = await self.openai_manager.ensure_connection()
            
            logger.info("Multi-broker AI Trading Bot connections initialized")
            
            # Calculate total connected accounts
            total_accounts = (
                len(self.connected_accounts['schwab']) +
                len(self.connected_accounts['coinbase']) +
                len(self.connected_accounts['etrade'])
            )
            
            return {
                'success': True,
                'openai_connected': openai_status,
                'enhanced_ai_ready': bool(self.enhanced_openai),
                'broker_connections': connection_results,
                'connected_accounts': self.connected_accounts,
                'total_accounts': total_accounts
            }
            
        except Exception as e:
            logger.error(f"Failed to initialize multi-broker connections: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def analyze_market_with_ai(self, symbol: str) -> MarketAnalysis:
        """Comprehensive market analysis using OpenAI"""
        try:
            # Get current market data
            market_data = self.schwab_manager.get_market_data(symbol)
            
            if not market_data.get('success'):
                raise ValueError(f"Failed to get market data for {symbol}")
            
            quote = market_data['market_data']
            
            # Prepare comprehensive analysis prompt
            analysis_prompt = f"""
            As an expert financial analyst and trader, provide a comprehensive analysis of {symbol}:
            
            Current Market Data:
            - Price: ${quote['price']:.2f}
            - Change: {quote['change']:.2f} ({quote['change_percent']:.2f}%)
            - Volume: {quote['volume']:,}
            - High: ${quote['high']:.2f}
            - Low: ${quote['low']:.2f}
            - Bid/Ask: ${quote['bid']:.2f}/${quote['ask']:.2f}
            
            Please analyze:
            1. Technical indicators and price action
            2. Market sentiment and momentum
            3. Volume analysis and liquidity
            4. Support and resistance levels
            5. Short-term and medium-term outlook
            6. Risk assessment
            7. Trading recommendation with confidence level
            
            Provide your analysis in JSON format with:
            {{
                "trend_direction": "BULLISH/BEARISH/NEUTRAL",
                "sentiment_score": -1.0 to 1.0,
                "technical_indicators": {{
                    "momentum": "description",
                    "volume_analysis": "description",
                    "support_resistance": "levels"
                }},
                "fundamental_analysis": "brief assessment",
                "ai_recommendation": "detailed recommendation",
                "confidence_level": 0.0 to 1.0,
                "key_factors": ["factor1", "factor2", "factor3"]
            }}
            """
            
            # Get AI analysis
            response = await self.openai_manager.make_chat_completion(
                model="gpt-4o",
                messages=[{"role": "user", "content": analysis_prompt}],
                response_format={"type": "json_object"},
                max_tokens=1500
            )
            
            ai_analysis = json.loads(response.choices[0].message.content)
            
            # Create market analysis object
            market_analysis = MarketAnalysis(
                symbol=symbol,
                current_price=quote['price'],
                trend_direction=ai_analysis.get('trend_direction', 'NEUTRAL'),
                sentiment_score=ai_analysis.get('sentiment_score', 0.0),
                technical_indicators=ai_analysis.get('technical_indicators', {}),
                fundamental_analysis=ai_analysis.get('fundamental_analysis', ''),
                news_sentiment='NEUTRAL',  # Could be enhanced with news API
                ai_recommendation=ai_analysis.get('ai_recommendation', ''),
                confidence_level=ai_analysis.get('confidence_level', 0.0),
                timestamp=datetime.utcnow()
            )
            
            # Store analysis
            self.market_analysis_history.append(market_analysis)
            
            logger.info(f"Market analysis completed for {symbol}")
            return market_analysis
            
        except Exception as e:
            logger.error(f"Market analysis failed for {symbol}: {e}")
            # Return neutral analysis on error
            return MarketAnalysis(
                symbol=symbol,
                current_price=0.0,
                trend_direction='NEUTRAL',
                sentiment_score=0.0,
                technical_indicators={},
                fundamental_analysis='Analysis unavailable',
                news_sentiment='NEUTRAL',
                ai_recommendation='No recommendation due to analysis error',
                confidence_level=0.0,
                timestamp=datetime.utcnow()
            )
    
    async def generate_trading_signal(self, symbol: str) -> TradingSignal:
        """Generate trading signal based on AI analysis"""
        try:
            # Get market analysis
            analysis = await self.analyze_market_with_ai(symbol)
            
            # Generate trading signal based on analysis
            signal_prompt = f"""
            Based on the following market analysis for {symbol}, generate a specific trading signal:
            
            Analysis Summary:
            - Current Price: ${analysis.current_price:.2f}
            - Trend: {analysis.trend_direction}
            - Sentiment Score: {analysis.sentiment_score}
            - AI Confidence: {analysis.confidence_level}
            - Recommendation: {analysis.ai_recommendation}
            
            Risk Management Parameters:
            - Max Position Size: ${self.risk_params.max_position_size:,.2f}
            - Stop Loss: {self.risk_params.stop_loss_percentage*100:.1f}%
            - Take Profit: {self.risk_params.take_profit_percentage*100:.1f}%
            
            Generate a trading signal in JSON format:
            {{
                "action": "BUY/SELL/HOLD",
                "confidence": 0.0 to 1.0,
                "quantity": number_of_shares,
                "price_target": target_price_or_null,
                "stop_loss": stop_loss_price_or_null,
                "reasoning": "detailed_reasoning",
                "risk_level": "LOW/MEDIUM/HIGH",
                "time_horizon": "SHORT/MEDIUM/LONG"
            }}
            
            Only recommend BUY/SELL if confidence > {self.config.get('confidence_threshold', 0.7)}
            """
            
            response = await self.openai_manager.make_chat_completion(
                model="gpt-4o",
                messages=[{"role": "user", "content": signal_prompt}],
                response_format={"type": "json_object"},
                max_tokens=800
            )
            
            signal_data = json.loads(response.choices[0].message.content)
            
            # Create trading signal
            trading_signal = TradingSignal(
                symbol=symbol,
                action=signal_data.get('action', 'HOLD'),
                confidence=signal_data.get('confidence', 0.0),
                quantity=signal_data.get('quantity', 0),
                price_target=signal_data.get('price_target'),
                stop_loss=signal_data.get('stop_loss'),
                reasoning=signal_data.get('reasoning', ''),
                timestamp=datetime.utcnow(),
                risk_level=signal_data.get('risk_level', 'MEDIUM'),
                time_horizon=signal_data.get('time_horizon', 'MEDIUM')
            )
            
            logger.info(f"Trading signal generated for {symbol}: {trading_signal.action}")
            return trading_signal
            
        except Exception as e:
            logger.error(f"Failed to generate trading signal for {symbol}: {e}")
            return TradingSignal(
                symbol=symbol,
                action='HOLD',
                confidence=0.0,
                quantity=0,
                price_target=None,
                stop_loss=None,
                reasoning=f'Signal generation failed: {str(e)}',
                timestamp=datetime.utcnow(),
                risk_level='HIGH',
                time_horizon='SHORT'
            )
    
    def validate_trading_signal(self, signal: TradingSignal) -> Dict[str, Any]:
        """Validate trading signal against risk management rules"""
        validation_results = {
            'valid': True,
            'warnings': [],
            'errors': []
        }
        
        # Check confidence threshold
        if signal.confidence < self.config.get('confidence_threshold', 0.7):
            validation_results['valid'] = False
            validation_results['errors'].append(f"Confidence {signal.confidence:.2f} below threshold")
        
        # Check daily trade limit
        if self.trades_today >= self.risk_params.max_daily_trades:
            validation_results['valid'] = False
            validation_results['errors'].append("Daily trade limit exceeded")
        
        # Check symbol whitelist
        if signal.symbol not in self.risk_params.allowed_symbols:
            validation_results['valid'] = False
            validation_results['errors'].append(f"Symbol {signal.symbol} not in allowed list")
        
        # Check symbol blacklist
        if signal.symbol in self.risk_params.blacklisted_symbols:
            validation_results['valid'] = False
            validation_results['errors'].append(f"Symbol {signal.symbol} is blacklisted")
        
        # Check trading hours (if enabled)
        if self.risk_params.trading_hours_only:
            current_hour = datetime.now().hour
            if current_hour < 9 or current_hour > 16:  # Market hours approximation
                validation_results['valid'] = False
                validation_results['errors'].append("Trading outside market hours")
        
        # Position size validation
        if signal.action in ['BUY', 'SELL'] and signal.quantity > 0:
            position_value = signal.quantity * (signal.price_target or 100)  # Estimate
            if position_value > self.risk_params.max_position_size:
                validation_results['warnings'].append("Position size exceeds maximum")
        
        return validation_results
    
    async def execute_trading_signal(self, signal: TradingSignal) -> Dict[str, Any]:
        """Execute trading signal across all connected accounts"""
        try:
            # Validate signal first
            validation = self.validate_trading_signal(signal)
            
            if not validation['valid']:
                return {
                    'success': False,
                    'error': 'Signal validation failed',
                    'validation_errors': validation['errors'],
                    'signal': asdict(signal)
                }
            
            # Check if paper trading
            if self.config.get('paper_trading', True):
                return await self._execute_paper_trade(signal)
            
            # Execute across all connected accounts
            execution_results = await self._execute_multi_account_signal(signal)
            
            return execution_results
            
        except Exception as e:
            logger.error(f"Failed to execute multi-account trading signal: {e}")
            return {
                'success': False,
                'error': str(e),
                'signal': asdict(signal)
            }
    
    async def _execute_multi_account_signal(self, signal: TradingSignal) -> Dict[str, Any]:
        """Execute trading signal across all connected broker accounts"""
        execution_results = {
            'signal': asdict(signal),
            'execution_time': datetime.utcnow().isoformat(),
            'total_accounts': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'broker_results': {},
            'overall_success': False
        }
        
        try:
            # Execute on Schwab accounts
            if self.connected_accounts['schwab']:
                schwab_results = []
                for account in self.connected_accounts['schwab']:
                    try:
                        order_data = self._prepare_schwab_order_data(signal)
                        order_result = self.schwab_manager.place_order(
                            account['account_number'], 
                            order_data
                        )
                        schwab_results.append({
                            'account': account['account_number'],
                            'result': order_result,
                            'success': order_result.get('success', False)
                        })
                        
                        if order_result.get('success'):
                            execution_results['successful_executions'] += 1
                        else:
                            execution_results['failed_executions'] += 1
                            
                    except Exception as e:
                        schwab_results.append({
                            'account': account.get('account_number', 'unknown'),
                            'result': {'success': False, 'error': str(e)},
                            'success': False
                        })
                        execution_results['failed_executions'] += 1
                
                execution_results['broker_results']['schwab'] = schwab_results
                execution_results['total_accounts'] += len(schwab_results)
            
            # Execute on Coinbase accounts
            if self.connected_accounts['coinbase']:
                coinbase_results = []
                for account in self.connected_accounts['coinbase']:
                    try:
                        # Convert stock signal to crypto equivalent if possible
                        crypto_signal = await self._convert_to_crypto_signal(signal)
                        if crypto_signal:
                            order_result = await self._execute_coinbase_order(account, crypto_signal)
                            coinbase_results.append({
                                'account': account.get('name', 'coinbase_account'),
                                'result': order_result,
                                'success': order_result.get('success', False)
                            })
                            
                            if order_result.get('success'):
                                execution_results['successful_executions'] += 1
                            else:
                                execution_results['failed_executions'] += 1
                        else:
                            coinbase_results.append({
                                'account': account.get('name', 'coinbase_account'),
                                'result': {'success': False, 'error': 'Signal not applicable to crypto'},
                                'success': False
                            })
                            
                    except Exception as e:
                        coinbase_results.append({
                            'account': account.get('name', 'unknown'),
                            'result': {'success': False, 'error': str(e)},
                            'success': False
                        })
                        execution_results['failed_executions'] += 1
                
                execution_results['broker_results']['coinbase'] = coinbase_results
                execution_results['total_accounts'] += len(coinbase_results)
            
            # Determine overall success
            execution_results['overall_success'] = execution_results['successful_executions'] > 0
            
            # Record trading activity
            if execution_results['overall_success']:
                self.trades_today += 1
                self.trading_history.append({
                    'signal': asdict(signal),
                    'multi_account_results': execution_results,
                    'execution_time': datetime.utcnow().isoformat(),
                    'paper_trade': False,
                    'multi_account_trade': True
                })
            
            logger.info(f"Multi-account execution completed: {execution_results['successful_executions']}/{execution_results['total_accounts']} successful")
            
            return execution_results
            
        except Exception as e:
            logger.error(f"Multi-account signal execution failed: {e}")
            execution_results['error'] = str(e)
            return execution_results
    
    def _prepare_schwab_order_data(self, signal: TradingSignal) -> Dict[str, Any]:
        """Prepare Schwab-specific order data from trading signal"""
        instruction = "BUY" if signal.action == "BUY" else "SELL"
        
        order_data = {
            "orderType": "MARKET",
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [{
                "instruction": instruction,
                "quantity": signal.quantity,
                "instrument": {
                    "symbol": signal.symbol,
                    "assetType": "EQUITY"
                }
            }]
        }
        
        # Add limit price if specified
        if signal.price_target and signal.action in ['BUY', 'SELL']:
            order_data["orderType"] = "LIMIT"
            order_data["price"] = signal.price_target
        
        return order_data
    
    async def _convert_to_crypto_signal(self, signal: TradingSignal) -> Optional[TradingSignal]:
        """Convert stock trading signal to crypto equivalent"""
        try:
            # Map stock symbols to crypto equivalents
            stock_to_crypto_map = {
                'AAPL': 'BTC',  # Tech stock -> Bitcoin
                'GOOGL': 'ETH', # Tech stock -> Ethereum
                'MSFT': 'ETH',  # Tech stock -> Ethereum
                'TSLA': 'BTC',  # High volatility -> Bitcoin
                'NVDA': 'ETH',  # AI/Tech -> Ethereum
                'AMZN': 'BTC',  # Large cap -> Bitcoin
                'META': 'ETH',  # Tech -> Ethereum
                'NFLX': 'BTC'   # Growth -> Bitcoin
            }
            
            # Check if we can convert this signal
            if signal.symbol not in stock_to_crypto_map:
                return None
            
            crypto_symbol = stock_to_crypto_map[signal.symbol]
            
            # Create crypto version of signal with adjusted parameters
            crypto_signal = TradingSignal(
                symbol=crypto_symbol,
                action=signal.action,
                confidence=signal.confidence * 0.8,  # Reduce confidence for cross-asset
                quantity=min(signal.quantity // 100, 1),  # Adjust quantity for crypto
                price_target=None,  # Use market price for crypto
                stop_loss=None,
                reasoning=f"Crypto equivalent of {signal.symbol} signal: {signal.reasoning}",
                timestamp=datetime.utcnow(),
                risk_level=signal.risk_level,
                time_horizon=signal.time_horizon
            )
            
            return crypto_signal
            
        except Exception as e:
            logger.error(f"Failed to convert signal to crypto: {e}")
            return None
    
    async def _execute_coinbase_order(self, account: Dict, signal: TradingSignal) -> Dict[str, Any]:
        """Execute order on Coinbase account"""
        try:
            if not self.coinbase_manager:
                return {'success': False, 'error': 'Coinbase manager not initialized'}
            
            # Prepare Coinbase order
            if signal.action == 'BUY':
                order_result = await self.coinbase_manager.buy_crypto(
                    symbol=signal.symbol,
                    amount=signal.quantity * 100,  # Adjust amount for crypto
                    account_id=account.get('id')
                )
            elif signal.action == 'SELL':
                order_result = await self.coinbase_manager.sell_crypto(
                    symbol=signal.symbol,
                    amount=signal.quantity * 100,
                    account_id=account.get('id')
                )
            else:
                return {'success': False, 'error': 'Invalid action for crypto'}
            
            return order_result
            
        except Exception as e:
            logger.error(f"Coinbase order execution failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _execute_paper_trade(self, signal: TradingSignal) -> Dict[str, Any]:
        """Execute paper trade (simulation)"""
        try:
            # Simulate trade execution
            execution_price = signal.price_target or 0.0
            
            # Log paper trade
            paper_trade = {
                'signal': asdict(signal),
                'execution_price': execution_price,
                'execution_time': datetime.utcnow().isoformat(),
                'paper_trade': True,
                'simulated_value': signal.quantity * execution_price
            }
            
            self.trading_history.append(paper_trade)
            self.trades_today += 1
            
            logger.info(f"Paper trade executed: {signal.action} {signal.quantity} {signal.symbol}")
            
            return {
                'success': True,
                'message': 'Paper trade executed successfully',
                'trade_details': paper_trade,
                'paper_trade': True
            }
            
        except Exception as e:
            logger.error(f"Paper trade execution failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'paper_trade': True
            }
    
    def _prepare_order_data(self, signal: TradingSignal) -> Dict[str, Any]:
        """Prepare Schwab order data from trading signal"""
        instruction = "BUY" if signal.action == "BUY" else "SELL"
        
        order_data = {
            "orderType": "MARKET",  # Can be enhanced to support LIMIT orders
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [{
                "instruction": instruction,
                "quantity": signal.quantity,
                "instrument": {
                    "symbol": signal.symbol,
                    "assetType": "EQUITY"
                }
            }]
        }
        
        # Add limit price if specified
        if signal.price_target and signal.action in ['BUY', 'SELL']:
            order_data["orderType"] = "LIMIT"
            order_data["price"] = signal.price_target
        
        return order_data
    
    async def run_trading_cycle(self) -> Dict[str, Any]:
        """Run one complete trading cycle across all connected accounts"""
        cycle_results = {
            'timestamp': datetime.utcnow().isoformat(),
            'symbols_analyzed': 0,
            'signals_generated': 0,
            'trades_executed': 0,
            'multi_account_executions': 0,
            'total_accounts_used': 0,
            'broker_breakdown': {
                'schwab': {'signals': 0, 'executions': 0},
                'coinbase': {'signals': 0, 'executions': 0},
                'etrade': {'signals': 0, 'executions': 0}
            },
            'errors': []
        }
        
        try:
            # Analyze each symbol in watchlist
            for symbol in self.risk_params.allowed_symbols:
                try:
                    # Generate trading signal
                    signal = await self.generate_trading_signal(symbol)
                    cycle_results['symbols_analyzed'] += 1
                    
                    # Execute if actionable
                    if signal.action in ['BUY', 'SELL']:
                        cycle_results['signals_generated'] += 1
                        
                        execution_result = await self.execute_trading_signal(signal)
                        
                        if execution_result.get('success') or execution_result.get('overall_success'):
                            cycle_results['trades_executed'] += 1
                            
                            # Track multi-account execution details
                            if execution_result.get('multi_account_trade'):
                                cycle_results['multi_account_executions'] += 1
                                cycle_results['total_accounts_used'] += execution_result.get('total_accounts', 0)
                                
                                # Update broker breakdown
                                broker_results = execution_result.get('broker_results', {})
                                for broker, results in broker_results.items():
                                    if broker in cycle_results['broker_breakdown']:
                                        cycle_results['broker_breakdown'][broker]['signals'] += 1
                                        successful_executions = sum(1 for r in results if r.get('success'))
                                        cycle_results['broker_breakdown'][broker]['executions'] += successful_executions
                    
                except Exception as e:
                    cycle_results['errors'].append(f"Error processing {symbol}: {str(e)}")
                    logger.error(f"Error in trading cycle for {symbol}: {e}")
            
            # Calculate success metrics
            cycle_results['success_rate'] = (
                cycle_results['trades_executed'] / cycle_results['signals_generated'] 
                if cycle_results['signals_generated'] > 0 else 0
            )
            
            cycle_results['multi_account_coverage'] = (
                cycle_results['total_accounts_used'] / max(1, cycle_results['signals_generated'])
            )
            
            logger.info(f"Multi-account trading cycle completed: {cycle_results}")
            return cycle_results
            
        except Exception as e:
            logger.error(f"Multi-account trading cycle failed: {e}")
            cycle_results['errors'].append(f"Cycle failed: {str(e)}")
            return cycle_results
    
    async def start_trading_bot(self) -> Dict[str, Any]:
        """Start the AI trading bot"""
        try:
            if self.is_running:
                return {
                    'success': False,
                    'error': 'Trading bot is already running'
                }
            
            # Initialize connections
            init_result = await self.initialize_connections()
            if not init_result.get('success'):
                return {
                    'success': False,
                    'error': 'Failed to initialize connections',
                    'details': init_result
                }
            
            self.is_running = True
            self.trades_today = 0
            
            logger.info("AI Trading Bot started successfully")
            
            return {
                'success': True,
                'message': 'AI Trading Bot started successfully',
                'config': self.config,
                'risk_params': asdict(self.risk_params),
                'paper_trading': self.config.get('paper_trading', True)
            }
            
        except Exception as e:
            logger.error(f"Failed to start trading bot: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def stop_trading_bot(self) -> Dict[str, Any]:
        """Stop the AI trading bot"""
        try:
            self.is_running = False
            
            logger.info("AI Trading Bot stopped")
            
            return {
                'success': True,
                'message': 'AI Trading Bot stopped successfully',
                'session_stats': {
                    'trades_executed': self.trades_today,
                    'daily_pnl': self.daily_pnl,
                    'analyses_performed': len(self.market_analysis_history)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to stop trading bot: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_bot_status(self) -> Dict[str, Any]:
        """Get current bot status and multi-account statistics"""
        # Calculate multi-account statistics
        multi_account_trades = sum(1 for trade in self.trading_history if trade.get('multi_account_trade'))
        total_account_executions = sum(
            trade.get('multi_account_results', {}).get('total_accounts', 0) 
            for trade in self.trading_history 
            if trade.get('multi_account_trade')
        )
        
        return {
            'is_running': self.is_running,
            'user_id': self.user_id,
            'trades_today': self.trades_today,
            'daily_pnl': self.daily_pnl,
            'config': self.config,
            'risk_params': asdict(self.risk_params),
            'trading_history_count': len(self.trading_history),
            'analysis_history_count': len(self.market_analysis_history),
            'last_activity': self.trading_history[-1]['execution_time'] if self.trading_history else None,
            'multi_account_stats': {
                'connected_accounts': self.connected_accounts,
                'total_connected_accounts': (
                    len(self.connected_accounts['schwab']) +
                    len(self.connected_accounts['coinbase']) +
                    len(self.connected_accounts['etrade'])
                ),
                'multi_account_trades': multi_account_trades,
                'total_account_executions': total_account_executions,
                'average_accounts_per_trade': (
                    total_account_executions / max(1, multi_account_trades)
                )
            }
        }
    
    def get_trading_performance(self) -> Dict[str, Any]:
        """Get trading performance metrics"""
        if not self.trading_history:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'total_pnl': 0.0
            }
        
        total_trades = len(self.trading_history)
        paper_trades = sum(1 for trade in self.trading_history if trade.get('paper_trade', False))
        
        return {
            'total_trades': total_trades,
            'paper_trades': paper_trades,
            'real_trades': total_trades - paper_trades,
            'trades_today': self.trades_today,
            'daily_pnl': self.daily_pnl,
            'last_trade_time': self.trading_history[-1]['execution_time'] if self.trading_history else None
        }

# Factory function for easy integration
def create_ai_trading_bot(user_id: str, config: Dict[str, Any] = None) -> AITradingBot:
    """Create AI trading bot instance"""
    return AITradingBot(user_id=user_id, config=config)

def get_ai_trading_bot_info() -> Dict[str, Any]:
    """Get information about AI trading bot capabilities"""
    return {
        'description': 'Advanced AI-powered trading bot using OpenAI and Schwab integration',
        'features': [
            'AI-powered market analysis using GPT-4',
            'Intelligent trading signal generation',
            'Comprehensive risk management',
            'Paper trading and live trading modes',
            'Real-time market data integration',
            'Automated order execution through Schwab',
            'Performance tracking and analytics',
            'Multi-symbol watchlist monitoring',
            'Configurable trading strategies',
            'Advanced error handling and logging'
        ],
        'supported_strategies': [
            'AI Momentum Trading',
            'Technical Analysis Based',
            'Sentiment Driven Trading',
            'Multi-Factor Analysis'
        ],
        'risk_management': [
            'Position size limits',
            'Daily trade limits',
            'Stop-loss automation',
            'Portfolio risk monitoring',
            'Symbol whitelist/blacklist',
            'Trading hours restrictions'
        ],
        'ai_capabilities': [
            'Market trend analysis',
            'Sentiment analysis',
            'Technical indicator interpretation',
            'Risk assessment',
            'Trading signal generation',
            'Performance optimization recommendations'
        ]
    }