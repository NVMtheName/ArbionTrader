"""
OpenAI Trading Engine - Advanced AI Trading Implementation
Integrates with the comprehensive OpenAI client to provide intelligent trading capabilities.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import json

from utils.comprehensive_openai_client import (
    ComprehensiveOpenAIClient, 
    TradingDecision, 
    MarketInsight, 
    PortfolioRecommendation
)
from models import Trade, APICredential
from app import db

logger = logging.getLogger(__name__)

@dataclass 
class TradingStrategy:
    """AI-generated trading strategy"""
    name: str
    description: str
    entry_conditions: List[str]
    exit_conditions: List[str]
    risk_parameters: Dict[str, Any]
    expected_return: float
    risk_level: str
    timeframe: str
    confidence_score: float

@dataclass
class TradingSignal:
    """Real-time trading signal from AI"""
    symbol: str
    signal_type: str  # buy, sell, hold
    strength: float  # 0.0 to 1.0
    price_target: Optional[float]
    stop_loss: Optional[float]
    confidence: float
    reasoning: str
    timestamp: datetime
    expires_at: Optional[datetime]

class OpenAITradingEngine:
    """Advanced AI-powered trading engine using OpenAI"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.openai_client = ComprehensiveOpenAIClient(user_id=user_id)
        
        # Initialize trading assistant
        self.assistant_id = self.openai_client.create_trading_assistant("Arbion Trading AI")
        self.thread_id = self.openai_client.create_conversation_thread(self.assistant_id)
        
        # Trading parameters
        self.risk_tolerance = "moderate"  # conservative, moderate, aggressive
        self.max_position_size = 0.05  # Max 5% of portfolio per position
        self.stop_loss_pct = 0.02  # 2% stop loss
        self.take_profit_pct = 0.06  # 6% take profit
        
        logger.info(f"OpenAI Trading Engine initialized for user {user_id}")
    
    async def process_natural_language_trade(self, command: str, is_simulation: bool = True) -> Dict[str, Any]:
        """Process natural language trading commands"""
        try:
            logger.info(f"Processing natural language trade: {command}")
            
            # Use the AI to parse the command
            trading_decision = await self.openai_client.process_trading_command(command)
            
            if trading_decision.action == "hold":
                return {
                    "success": True,
                    "action": "hold",
                    "message": trading_decision.reasoning,
                    "decision": trading_decision
                }
            
            # Execute the trade if it's buy or sell
            if trading_decision.action in ["buy", "sell"]:
                execution_result = await self._execute_ai_decision(trading_decision, is_simulation)
                return {
                    "success": execution_result.get("success", False),
                    "action": trading_decision.action,
                    "symbol": trading_decision.symbol,
                    "message": execution_result.get("message", ""),
                    "decision": trading_decision,
                    "execution": execution_result
                }
            
            return {
                "success": False,
                "message": "Invalid trading action",
                "decision": trading_decision
            }
            
        except Exception as e:
            logger.error(f"Natural language trade processing failed: {e}")
            return {
                "success": False,
                "message": f"Failed to process command: {str(e)}"
            }
    
    async def _execute_ai_decision(self, decision: TradingDecision, is_simulation: bool = True) -> Dict[str, Any]:
        """Execute a trading decision made by AI"""
        try:
            # Determine the best provider for this symbol
            provider = await self._select_optimal_provider(decision.symbol)
            
            if not provider:
                return {
                    "success": False,
                    "message": "No suitable trading provider found for this symbol"
                }
            
            # Calculate position size based on risk management
            position_size = await self._calculate_position_size(
                decision.symbol, 
                decision.quantity,
                provider
            )
            
            # Execute the trade through the AI client's tool system
            execution_params = {
                "symbol": decision.symbol,
                "side": decision.action,
                "quantity": position_size,
                "provider": provider,
                "order_type": "market",
                "is_simulation": is_simulation
            }
            
            # Add stop loss and take profit if specified
            if decision.stop_loss:
                execution_params["stop_loss"] = decision.stop_loss
            if decision.take_profit:
                execution_params["take_profit"] = decision.take_profit
            
            result = await self.openai_client._execute_trade_order(**execution_params)
            
            # Log the AI decision and execution
            await self._log_ai_trade(decision, result, is_simulation)
            
            return result
            
        except Exception as e:
            logger.error(f"AI decision execution failed: {e}")
            return {
                "success": False,
                "message": f"Execution failed: {str(e)}"
            }
    
    async def _select_optimal_provider(self, symbol: str) -> Optional[str]:
        """Select the best trading provider for a given symbol"""
        try:
            # Basic logic - can be enhanced with AI decision making
            if symbol.endswith("-USD") or symbol.startswith("BTC") or symbol.startswith("ETH"):
                return "coinbase"  # Crypto symbols
            else:
                return "schwab"  # Stock symbols
                
        except Exception as e:
            logger.error(f"Provider selection failed: {e}")
            return None
    
    async def _calculate_position_size(self, symbol: str, requested_quantity: Optional[float], provider: str) -> float:
        """Calculate optimal position size based on risk management"""
        try:
            # Get current portfolio balance
            portfolio_status = await self.openai_client._get_portfolio_status(provider)
            total_balance = portfolio_status.get("total_balance", 0)
            
            if total_balance <= 0:
                raise ValueError("Invalid portfolio balance")
            
            # Get current market price for the symbol
            market_data = await self.openai_client._analyze_market_data([symbol])
            current_price = market_data["data"][symbol]["current_price"]
            
            # Calculate maximum position value based on risk parameters
            max_position_value = total_balance * self.max_position_size
            max_quantity = max_position_value / current_price
            
            # Use requested quantity if specified and within limits
            if requested_quantity and requested_quantity <= max_quantity:
                return requested_quantity
            
            # Otherwise, use the maximum safe quantity
            return max_quantity
            
        except Exception as e:
            logger.error(f"Position size calculation failed: {e}")
            return 0.0
    
    async def _log_ai_trade(self, decision: TradingDecision, execution_result: Dict, is_simulation: bool):
        """Log AI trading decisions and executions"""
        try:
            trade_log = Trade(
                user_id=self.user_id,
                provider=execution_result.get("provider", "unknown"),
                symbol=decision.symbol,
                side=decision.action,
                quantity=execution_result.get("quantity", decision.quantity),
                price=execution_result.get("executed_price"),
                status="executed" if execution_result.get("success") else "failed",
                is_simulation=is_simulation,
                confidence_score=decision.confidence,
                trade_notes=f"AI Decision: {decision.reasoning}",
                ai_generated=True
            )
            
            db.session.add(trade_log)
            db.session.commit()
            
            logger.info(f"AI trade logged: {decision.symbol} {decision.action} - {'Success' if execution_result.get('success') else 'Failed'}")
            
        except Exception as e:
            logger.error(f"Trade logging failed: {e}")
    
    async def generate_trading_strategy(self, parameters: Dict[str, Any]) -> TradingStrategy:
        """Generate a custom trading strategy using AI"""
        try:
            strategy_prompt = f"""
            Create a comprehensive trading strategy based on these parameters:
            {json.dumps(parameters, indent=2)}
            
            The strategy should include:
            - Clear entry and exit conditions
            - Risk management parameters
            - Expected returns and timeframe
            - Specific implementation guidelines
            
            Consider the user's risk tolerance: {self.risk_tolerance}
            Maximum position size: {self.max_position_size * 100}%
            """
            
            messages = [
                {
                    "role": "system", 
                    "content": "You are a professional trading strategy developer with expertise in quantitative finance and risk management."
                },
                {"role": "user", "content": strategy_prompt}
            ]
            
            response = await self.openai_client.create_chat_completion(
                messages=messages,
                model="gpt-4o",
                response_format={"type": "json_object"}
            )
            
            strategy_data = json.loads(response.choices[0].message.content)
            
            return TradingStrategy(
                name=strategy_data.get("name", "AI Generated Strategy"),
                description=strategy_data.get("description", ""),
                entry_conditions=strategy_data.get("entry_conditions", []),
                exit_conditions=strategy_data.get("exit_conditions", []),
                risk_parameters=strategy_data.get("risk_parameters", {}),
                expected_return=strategy_data.get("expected_return", 0.0),
                risk_level=strategy_data.get("risk_level", "medium"),
                timeframe=strategy_data.get("timeframe", "medium-term"),
                confidence_score=strategy_data.get("confidence_score", 0.7)
            )
            
        except Exception as e:
            logger.error(f"Strategy generation failed: {e}")
            raise
    
    async def monitor_positions_and_generate_signals(self, symbols: List[str]) -> List[TradingSignal]:
        """Monitor positions and generate real-time trading signals"""
        try:
            signals = []
            
            # Get market insights for all symbols
            insights = await self.openai_client.generate_market_insights(symbols)
            
            for insight in insights:
                # Generate trading signals based on AI analysis
                signal_prompt = f"""
                Based on this market insight for {insight.symbol}, generate a trading signal:
                
                Sentiment: {insight.sentiment}
                Price Prediction: {insight.price_prediction}
                Volatility: {insight.volatility_forecast}
                Key Factors: {insight.key_factors}
                Confidence: {insight.confidence_score}
                
                Determine if this presents a trading opportunity (buy/sell/hold) and provide:
                - Signal strength (0.0-1.0)
                - Price targets
                - Stop loss levels
                - Expiration time for the signal
                - Detailed reasoning
                """
                
                messages = [
                    {"role": "system", "content": "You are a trading signal generator providing actionable trading recommendations."},
                    {"role": "user", "content": signal_prompt}
                ]
                
                response = await self.openai_client.create_chat_completion(
                    messages=messages,
                    model="gpt-4o",
                    response_format={"type": "json_object"}
                )
                
                signal_data = json.loads(response.choices[0].message.content)
                
                # Create trading signal
                signal = TradingSignal(
                    symbol=insight.symbol,
                    signal_type=signal_data.get("signal_type", "hold"),
                    strength=signal_data.get("strength", 0.5),
                    price_target=signal_data.get("price_target"),
                    stop_loss=signal_data.get("stop_loss"),
                    confidence=signal_data.get("confidence", 0.5),
                    reasoning=signal_data.get("reasoning", ""),
                    timestamp=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(hours=signal_data.get("expires_in_hours", 24))
                )
                
                signals.append(signal)
            
            return signals
            
        except Exception as e:
            logger.error(f"Signal generation failed: {e}")
            return []
    
    async def optimize_portfolio_with_ai(self) -> PortfolioRecommendation:
        """Use AI to optimize the entire portfolio"""
        try:
            # Get current portfolio positions
            portfolio_status = await self.openai_client._get_portfolio_status("all")
            
            if not portfolio_status.get("success"):
                raise ValueError("Could not retrieve portfolio status")
            
            current_positions = portfolio_status.get("accounts", [])
            
            # Generate AI-powered optimization recommendations
            recommendation = await self.openai_client.optimize_portfolio(current_positions)
            
            return recommendation
            
        except Exception as e:
            logger.error(f"Portfolio optimization failed: {e}")
            raise
    
    async def continuous_trading_assistant(self, message: str) -> str:
        """Interactive AI trading assistant for continuous conversations"""
        try:
            # Send message to the persistent thread
            response_generator = await self.openai_client.send_trading_message(
                thread_id=self.thread_id,
                message=message,
                assistant_id=self.assistant_id,
                stream=True
            )
            
            # Collect streaming response
            full_response = ""
            async for chunk in response_generator:
                full_response += chunk
            
            return full_response
            
        except Exception as e:
            logger.error(f"Trading assistant conversation failed: {e}")
            return f"I encountered an error: {str(e)}. Please try again."
    
    async def analyze_trading_performance(self, days: int = 30) -> Dict[str, Any]:
        """Analyze trading performance using AI"""
        try:
            # Get recent trades
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            recent_trades = Trade.query.filter(
                Trade.user_id == self.user_id,
                Trade.created_at >= start_date,
                Trade.created_at <= end_date
            ).all()
            
            # Convert trades to analysis format
            trades_data = []
            for trade in recent_trades:
                trades_data.append({
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "quantity": float(trade.quantity) if trade.quantity else 0,
                    "price": float(trade.price) if trade.price else 0,
                    "date": trade.created_at.isoformat(),
                    "provider": trade.provider,
                    "is_simulation": trade.is_simulation,
                    "ai_generated": getattr(trade, 'ai_generated', False)
                })
            
            # AI analysis prompt
            analysis_prompt = f"""
            Analyze this trading performance over the last {days} days:
            
            Trades Data: {json.dumps(trades_data, indent=2)}
            
            Provide a comprehensive analysis including:
            - Overall performance metrics
            - Win/loss ratio
            - Best and worst performing trades
            - Strategy effectiveness
            - Risk management evaluation
            - Recommendations for improvement
            - Comparison between AI-generated and manual trades
            """
            
            messages = [
                {"role": "system", "content": "You are a trading performance analyst providing detailed trading insights."},
                {"role": "user", "content": analysis_prompt}
            ]
            
            response = await self.openai_client.create_chat_completion(
                messages=messages,
                model="gpt-4o",
                response_format={"type": "json_object"}
            )
            
            analysis = json.loads(response.choices[0].message.content)
            analysis["analysis_period_days"] = days
            analysis["total_trades"] = len(trades_data)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Performance analysis failed: {e}")
            return {"error": str(e)}
    
    # Configuration methods
    def set_risk_tolerance(self, risk_level: str):
        """Set risk tolerance level"""
        if risk_level in ["conservative", "moderate", "aggressive"]:
            self.risk_tolerance = risk_level
            
            # Adjust parameters based on risk level
            if risk_level == "conservative":
                self.max_position_size = 0.03  # 3%
                self.stop_loss_pct = 0.015     # 1.5%
                self.take_profit_pct = 0.04    # 4%
            elif risk_level == "aggressive":
                self.max_position_size = 0.08  # 8%
                self.stop_loss_pct = 0.03      # 3%
                self.take_profit_pct = 0.10    # 10%
            
            logger.info(f"Risk tolerance set to {risk_level}")
    
    def set_position_sizing(self, max_position_pct: float, stop_loss_pct: float, take_profit_pct: float):
        """Set custom position sizing parameters"""
        self.max_position_size = max_position_pct / 100
        self.stop_loss_pct = stop_loss_pct / 100
        self.take_profit_pct = take_profit_pct / 100
        
        logger.info(f"Position sizing updated: max={max_position_pct}%, stop={stop_loss_pct}%, profit={take_profit_pct}%")

# Factory function
def create_trading_engine(user_id: str) -> OpenAITradingEngine:
    """Create an OpenAI trading engine instance"""
    return OpenAITradingEngine(user_id=user_id)