"""
Comprehensive Claude/Anthropic API Integration for Arbion Trading Platform
Complete implementation of Anthropic's Claude API for advanced AI trading capabilities.

Features:
- Messages API (claude-opus-4-20250514, claude-sonnet-4-20250514, claude-haiku-4-20250414)
- Tool Use (function calling) for trading actions
- Streaming Responses
- Natural language trading command processing
- Market analysis and portfolio optimization
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import uuid

from anthropic import Anthropic, AsyncAnthropic

logger = logging.getLogger(__name__)


@dataclass
class TradingDecision:
    """Structured AI trading decision"""
    symbol: str
    action: str  # buy, sell, hold
    confidence: float
    quantity: Optional[float] = None
    price_target: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reasoning: str = ""
    risk_assessment: str = "medium"
    time_horizon: str = "short"
    market_conditions: Dict[str, Any] = None


@dataclass
class MarketInsight:
    """AI-generated market insights"""
    symbol: str
    sentiment: str  # bullish, bearish, neutral
    price_prediction: Optional[float] = None
    volatility_forecast: str = "medium"
    key_factors: List[str] = None
    technical_signals: Dict[str, Any] = None
    news_sentiment: Dict[str, Any] = None
    confidence_score: float = 0.0


@dataclass
class PortfolioRecommendation:
    """AI portfolio optimization recommendation"""
    total_value: float
    recommendations: List[Dict[str, Any]]
    risk_score: float
    diversification_analysis: Dict[str, Any]
    rebalancing_suggestions: List[str]
    performance_projection: Dict[str, Any]


class ComprehensiveClaudeClient:
    """Complete Claude API implementation for trading"""

    def __init__(self, user_id: str = None, api_key: str = None):
        self.user_id = user_id
        self.api_key = api_key or self._load_api_key(user_id)

        if not self.api_key:
            raise ValueError("Claude API key is required")

        # Initialize clients
        self.client = Anthropic(api_key=self.api_key)
        self.async_client = AsyncAnthropic(api_key=self.api_key)

        # Model configuration
        self.models = {
            "opus": "claude-opus-4-20250514",
            "sonnet": "claude-sonnet-4-20250514",
            "haiku": "claude-haiku-4-20250414",
            "primary": "claude-sonnet-4-20250514",       # Best balance of quality and speed
            "analysis": "claude-sonnet-4-20250514",       # Detailed market analysis
            "fast": "claude-haiku-4-20250414",             # Quick responses
            "reasoning": "claude-opus-4-20250514",         # Deep reasoning tasks
        }

        # Trading tool definitions (Anthropic tool_use format)
        self.trading_tools = self._define_trading_tools()

        # Conversation history management (Claude has no Assistants API)
        self.conversations: Dict[str, List[Dict]] = {}

        logger.info(f"Comprehensive Claude client initialized for user {user_id}")

    def _load_api_key(self, user_id: str) -> Optional[str]:
        """Load API key from database"""
        if not user_id:
            return None

        try:
            from models import APICredential
            from utils.encryption import decrypt_credentials

            credential = APICredential.query.filter_by(
                user_id=user_id,
                provider='claude',
                is_active=True
            ).first()

            if credential:
                creds = decrypt_credentials(credential.encrypted_credentials)
                return creds.get('api_key')
        except Exception as e:
            logger.error(f"Failed to load Claude API key for user {user_id}: {e}")

        return None

    def _define_trading_tools(self) -> List[Dict]:
        """Define trading tools in Anthropic tool_use format.

        Note: Anthropic uses 'input_schema' instead of OpenAI's 'parameters',
        and tools are flat dicts (not nested under 'function').
        """
        return [
            {
                "name": "analyze_market_data",
                "description": "Analyze real-time market data for trading decisions",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbols": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of trading symbols to analyze"
                        },
                        "timeframe": {
                            "type": "string",
                            "enum": ["1m", "5m", "15m", "1h", "4h", "1d"],
                            "description": "Analysis timeframe"
                        },
                        "indicators": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Technical indicators to include"
                        }
                    },
                    "required": ["symbols"]
                }
            },
            {
                "name": "execute_trade_order",
                "description": "Execute a trading order based on AI analysis",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string", "description": "Trading symbol"},
                        "side": {"type": "string", "enum": ["buy", "sell"], "description": "Order side"},
                        "quantity": {"type": "number", "description": "Order quantity"},
                        "order_type": {"type": "string", "enum": ["market", "limit", "stop"], "description": "Order type"},
                        "price": {"type": "number", "description": "Price for limit orders"},
                        "stop_loss": {"type": "number", "description": "Stop loss price"},
                        "take_profit": {"type": "number", "description": "Take profit price"},
                        "provider": {"type": "string", "enum": ["coinbase", "schwab", "etrade"], "description": "Trading provider"}
                    },
                    "required": ["symbol", "side", "quantity", "provider"]
                }
            },
            {
                "name": "get_portfolio_status",
                "description": "Get current portfolio status and balances",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "provider": {"type": "string", "description": "Specific provider or 'all' for all accounts"}
                    }
                }
            },
            {
                "name": "calculate_risk_metrics",
                "description": "Calculate portfolio risk metrics and position sizing",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "positions": {
                            "type": "array",
                            "items": {"type": "object"},
                            "description": "Current positions for risk analysis"
                        },
                        "risk_tolerance": {
                            "type": "string",
                            "enum": ["conservative", "moderate", "aggressive"],
                            "description": "Risk tolerance level"
                        }
                    },
                    "required": ["positions"]
                }
            }
        ]

    # MESSAGES API
    async def create_message(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        system: str = None,
        stream: bool = False,
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs
    ) -> Any:
        """Create a Claude message.

        Key differences from OpenAI's chat.completions.create():
        1. 'system' is a top-level parameter, not a message role
        2. Response is message.content[0].text, not choices[0].message.content
        3. Tools use 'input_schema' not 'parameters'
        4. Tool results are sent as role='user' with tool_result content blocks
        """
        try:
            # Extract system messages from messages list
            actual_messages = []
            system_prompt = system
            for msg in messages:
                if msg.get("role") == "system":
                    system_prompt = msg["content"]
                else:
                    actual_messages.append(msg)

            params = {
                "model": model or self.models["primary"],
                "messages": actual_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            if system_prompt:
                params["system"] = system_prompt
            if tools:
                params["tools"] = tools

            if stream:
                return await self.async_client.messages.create(**params, stream=True)

            response = await self.async_client.messages.create(**params)
            logger.info(
                f"Claude message created: {response.usage.input_tokens} in / "
                f"{response.usage.output_tokens} out tokens"
            )
            return response

        except Exception as e:
            logger.error(f"Claude message creation failed: {e}")
            raise

    async def _handle_tool_use_loop(
        self,
        response,
        messages: List[Dict],
        system: str = None,
        model: str = None
    ) -> Any:
        """Handle Claude's tool_use responses in a loop until text response.

        Claude returns stop_reason='tool_use' when it wants to call a tool.
        We must:
        1. Extract tool_use blocks from response.content
        2. Execute the tools
        3. Send tool_result blocks back
        4. Repeat until stop_reason='end_turn'
        """
        while response.stop_reason == "tool_use":
            # Build tool results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await self._execute_tool_call(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
                    })

            # Append assistant response and tool results to conversation
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            # Get next response
            params = {
                "model": model or self.models["primary"],
                "messages": messages,
                "max_tokens": 4096,
                "tools": self.trading_tools,
            }
            if system:
                params["system"] = system
            response = await self.async_client.messages.create(**params)

        return response

    async def _execute_tool_call(self, function_name: str, arguments: Dict) -> Dict[str, Any]:
        """Execute tool calls for trading operations"""
        try:
            if function_name == "analyze_market_data":
                return await self._analyze_market_data(**arguments)
            elif function_name == "execute_trade_order":
                return await self._execute_trade_order(**arguments)
            elif function_name == "get_portfolio_status":
                return await self._get_portfolio_status(**arguments)
            elif function_name == "calculate_risk_metrics":
                return await self._calculate_risk_metrics(**arguments)
            else:
                return {"error": f"Unknown function: {function_name}"}
        except Exception as e:
            logger.error(f"Tool execution failed for {function_name}: {e}")
            return {"error": str(e)}

    async def _analyze_market_data(self, symbols: List[str], timeframe: str = "1h", indicators: List[str] = None) -> Dict:
        """Implement market data analysis"""
        from utils.comprehensive_market_data import ComprehensiveMarketDataProvider

        try:
            provider = ComprehensiveMarketDataProvider()
            analysis_results = {}

            for symbol in symbols:
                market_data = provider.get_symbol_data(symbol)
                technical_analysis = self._perform_technical_analysis(market_data, indicators or [])

                analysis_results[symbol] = {
                    "current_price": market_data.get("price", 0),
                    "change_percent": market_data.get("change_percent", 0),
                    "volume": market_data.get("volume", 0),
                    "technical_analysis": technical_analysis,
                    "timestamp": datetime.utcnow().isoformat()
                }

            return {
                "success": True,
                "data": analysis_results,
                "timeframe": timeframe
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _perform_technical_analysis(self, market_data: Dict, indicators: List[str]) -> Dict:
        """Perform technical analysis on market data"""
        analysis = {
            "trend": "neutral",
            "momentum": "neutral",
            "volatility": "medium",
            "support_levels": [],
            "resistance_levels": [],
            "signals": []
        }

        price = market_data.get("price", 0)
        change_percent = market_data.get("change_percent", 0)

        if change_percent > 2:
            analysis["trend"] = "bullish"
            analysis["momentum"] = "strong_up"
        elif change_percent < -2:
            analysis["trend"] = "bearish"
            analysis["momentum"] = "strong_down"

        volume = market_data.get("volume", 0)
        if volume > 1000000:
            analysis["signals"].append("high_volume")

        return analysis

    async def _execute_trade_order(self, symbol: str, side: str, quantity: float, provider: str, **kwargs) -> Dict:
        """Execute trade through appropriate provider"""
        try:
            if provider == "coinbase":
                from utils.coinbase_connector import CoinbaseConnector
                connector = CoinbaseConnector(user_id=self.user_id)
            elif provider == "schwab":
                from utils.schwab_connector import SchwabConnector
                connector = SchwabConnector(user_id=self.user_id)
            else:
                return {"success": False, "error": f"Unsupported provider: {provider}"}

            result = connector.place_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=kwargs.get("order_type", "market"),
                price=kwargs.get("price"),
                is_simulation=kwargs.get("is_simulation", False)
            )

            # Log the trade
            from models import Trade
            from app import db

            trade = Trade(
                user_id=self.user_id,
                provider=provider,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=result.get("executed_price"),
                status="executed" if result.get("success") else "failed",
                is_simulation=kwargs.get("is_simulation", False)
            )

            db.session.add(trade)
            db.session.commit()

            return result

        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            return {"success": False, "error": str(e)}

    async def _get_portfolio_status(self, provider: str = "all") -> Dict:
        """Get current portfolio status"""
        try:
            from routes import get_account_balance

            balance_data = get_account_balance()

            return {
                "success": True,
                "total_balance": balance_data.get("total", 0),
                "accounts": balance_data.get("accounts", []),
                "last_updated": balance_data.get("last_updated"),
                "breakdown": balance_data.get("breakdown", {})
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _calculate_risk_metrics(self, positions: List[Dict], risk_tolerance: str = "moderate") -> Dict:
        """Calculate portfolio risk metrics"""
        try:
            total_value = sum(pos.get("value", 0) for pos in positions)

            risk_metrics = {
                "total_portfolio_value": total_value,
                "position_count": len(positions),
                "largest_position_pct": 0,
                "risk_score": 0,
                "diversification_score": 0,
                "recommendations": []
            }

            if positions:
                largest_position = max(positions, key=lambda x: x.get("value", 0))
                risk_metrics["largest_position_pct"] = (largest_position.get("value", 0) / total_value) * 100

                if risk_metrics["largest_position_pct"] > 20:
                    risk_metrics["recommendations"].append("Consider reducing concentration in largest position")

                if len(positions) < 5:
                    risk_metrics["recommendations"].append("Consider diversifying across more positions")

                risk_metrics["risk_score"] = min(100, risk_metrics["largest_position_pct"] + (100 / len(positions)))

            return {"success": True, "metrics": risk_metrics}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # NATURAL LANGUAGE TRADING INTERFACE
    async def process_trading_command(self, command: str) -> Dict[str, Any]:
        """Process natural language trading commands via Claude"""
        try:
            system_prompt = """You are an AI trading assistant for the Arbion trading platform.
Parse the user's trading command and return a structured trading decision as JSON.

Always consider:
- Risk management and position sizing
- Current market conditions
- User's portfolio balance

Return your response as a valid JSON object with these fields:
{
    "symbol": "string",
    "action": "buy|sell|hold",
    "confidence": 0.0-1.0,
    "quantity": number or null,
    "price_target": number or null,
    "stop_loss": number or null,
    "take_profit": number or null,
    "reasoning": "string",
    "risk_assessment": "low|medium|high",
    "time_horizon": "short|medium|long"
}"""

            messages = [
                {"role": "user", "content": f"Parse this trading command: {command}"}
            ]

            response = await self.create_message(
                messages=messages,
                system=system_prompt,
                model=self.models["primary"],
                tools=self.trading_tools,
                temperature=0.1
            )

            # Handle any tool use loops
            if response.stop_reason == "tool_use":
                response = await self._handle_tool_use_loop(
                    response, messages, system=system_prompt, model=self.models["primary"]
                )

            # Extract text from response
            text_content = ""
            for block in response.content:
                if block.type == "text":
                    text_content = block.text
                    break

            # Try to parse as JSON
            try:
                decision_data = json.loads(text_content)
                return {
                    "success": True,
                    "decision": decision_data,
                    "raw_response": text_content,
                    "model_used": self.models["primary"],
                    "provider": "claude"
                }
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "decision": None,
                    "raw_response": text_content,
                    "model_used": self.models["primary"],
                    "provider": "claude"
                }

        except Exception as e:
            logger.error(f"Claude trading command processing failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "provider": "claude"
            }

    # MARKET ANALYSIS ENGINE
    async def generate_market_insights(self, symbols: List[str]) -> List[Dict[str, Any]]:
        """Generate comprehensive market insights using Claude"""
        try:
            insights = []

            for symbol in symbols:
                market_analysis = await self._analyze_market_data([symbol])

                if not market_analysis.get("success"):
                    continue

                symbol_data = market_analysis["data"].get(symbol, {})

                prompt = f"""Analyze the market data for {symbol} and provide insights as JSON:

Current Price: ${symbol_data.get('current_price', 'N/A')}
Change: {symbol_data.get('change_percent', 'N/A')}%
Volume: {symbol_data.get('volume', 'N/A')}
Technical Analysis: {json.dumps(symbol_data.get('technical_analysis', {}))}

Return a JSON object with:
{{
    "symbol": "{symbol}",
    "sentiment": "bullish|bearish|neutral",
    "price_prediction": number or null,
    "volatility_forecast": "low|medium|high",
    "key_factors": ["factor1", "factor2"],
    "confidence_score": 0.0-1.0
}}"""

                response = await self.create_message(
                    messages=[{"role": "user", "content": prompt}],
                    system="You are a market analyst. Respond only with valid JSON.",
                    model=self.models["analysis"],
                    temperature=0.1
                )

                text_content = ""
                for block in response.content:
                    if block.type == "text":
                        text_content = block.text
                        break

                try:
                    insight_data = json.loads(text_content)
                    insight_data["symbol"] = symbol
                    insights.append(insight_data)
                except json.JSONDecodeError:
                    insights.append({
                        "symbol": symbol,
                        "sentiment": "neutral",
                        "raw_analysis": text_content,
                        "confidence_score": 0.0
                    })

            return insights

        except Exception as e:
            logger.error(f"Claude market insights generation failed: {e}")
            raise

    # PORTFOLIO OPTIMIZATION
    async def optimize_portfolio(
        self,
        current_positions: List[Dict],
        target_allocation: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """Generate AI-powered portfolio optimization recommendations"""
        try:
            total_value = sum(pos.get("value", 0) for pos in current_positions)

            prompt = f"""Analyze and optimize this portfolio:

Current Positions: {json.dumps(current_positions)}
Total Value: ${total_value:,.2f}
Target Allocation: {json.dumps(target_allocation) if target_allocation else 'Not specified'}

Return a JSON object with:
{{
    "total_value": {total_value},
    "recommendations": [
        {{"action": "buy|sell|hold", "symbol": "...", "reason": "..."}}
    ],
    "risk_score": 0-100,
    "diversification_analysis": {{"score": 0-100, "details": "..."}},
    "rebalancing_suggestions": ["suggestion1", "suggestion2"],
    "performance_projection": {{"expected_return": 0.0, "risk_level": "low|medium|high"}}
}}"""

            response = await self.create_message(
                messages=[{"role": "user", "content": prompt}],
                system="You are a portfolio optimization expert. Respond only with valid JSON.",
                model=self.models["analysis"],
                temperature=0.1
            )

            text_content = ""
            for block in response.content:
                if block.type == "text":
                    text_content = block.text
                    break

            try:
                optimization_data = json.loads(text_content)
                return {
                    "success": True,
                    "optimization": optimization_data,
                    "provider": "claude"
                }
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "raw_analysis": text_content,
                    "provider": "claude"
                }

        except Exception as e:
            logger.error(f"Claude portfolio optimization failed: {e}")
            return {"success": False, "error": str(e), "provider": "claude"}

    # CONVERSATIONAL TRADING INTERFACE
    def get_or_create_conversation(self, conversation_id: str = None) -> str:
        """Get or create a conversation thread (managed in memory)"""
        if conversation_id and conversation_id in self.conversations:
            return conversation_id

        new_id = conversation_id or str(uuid.uuid4())
        self.conversations[new_id] = []
        return new_id

    async def send_trading_message(
        self,
        message: str,
        conversation_id: str = None,
        stream: bool = False
    ) -> Union[str, Any]:
        """Send a message in a trading conversation"""
        try:
            conv_id = self.get_or_create_conversation(conversation_id)
            history = self.conversations[conv_id]

            history.append({"role": "user", "content": message})

            system_prompt = """You are an expert AI trading assistant for the Arbion platform.

Your capabilities:
- Analyze real-time market data across stocks, crypto, and options
- Generate trading signals with confidence scores
- Execute trades through connected broker APIs (Coinbase, Schwab, E*TRADE)
- Provide risk management recommendations
- Monitor portfolio performance and suggest optimizations

Always:
1. Analyze market data before making recommendations
2. Consider risk management in every decision
3. Provide clear reasoning for your recommendations
4. Use appropriate position sizing based on account balance
5. Respect user's risk tolerance and trading preferences

Use the available tools to access real market data and execute trades.
Never make recommendations without current data analysis."""

            if stream:
                return await self.async_client.messages.create(
                    model=self.models["primary"],
                    max_tokens=4096,
                    system=system_prompt,
                    messages=history,
                    tools=self.trading_tools,
                    stream=True
                )

            response = await self.create_message(
                messages=history,
                system=system_prompt,
                model=self.models["primary"],
                tools=self.trading_tools
            )

            # Handle tool use loops
            if response.stop_reason == "tool_use":
                response = await self._handle_tool_use_loop(
                    response, history, system=system_prompt, model=self.models["primary"]
                )

            # Extract text response
            text_content = ""
            for block in response.content:
                if block.type == "text":
                    text_content = block.text
                    break

            # Save assistant response to history
            history.append({"role": "assistant", "content": text_content})

            return text_content

        except Exception as e:
            logger.error(f"Claude trading message failed: {e}")
            raise

    # CONNECTION TEST
    async def test_connection(self) -> Dict[str, Any]:
        """Test Claude API connection"""
        try:
            response = await self.async_client.messages.create(
                model="claude-haiku-4-20250414",
                max_tokens=16,
                messages=[{"role": "user", "content": "Reply with 'OK'."}]
            )
            return {
                "success": True,
                "message": "Claude API connection successful",
                "model_used": "claude-haiku-4-20250414",
                "response_text": response.content[0].text if response.content else ""
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": f"Claude API connection failed: {str(e)}"
            }


def create_comprehensive_claude_client(
    user_id: str = None, api_key: str = None
) -> ComprehensiveClaudeClient:
    """Factory function to create a comprehensive Claude client"""
    return ComprehensiveClaudeClient(user_id=user_id, api_key=api_key)


def get_claude_enhancement_info() -> Dict[str, Any]:
    """Get information about Claude API capabilities"""
    return {
        "provider": "anthropic",
        "name": "Claude API Integration",
        "description": "Advanced AI trading capabilities powered by Anthropic's Claude",
        "models": {
            "claude-opus-4-20250514": "Most capable model for complex reasoning and analysis",
            "claude-sonnet-4-20250514": "Best balance of intelligence and speed",
            "claude-haiku-4-20250414": "Fastest model for quick responses and simple tasks"
        },
        "features": [
            "Natural language trading command processing",
            "Market analysis and sentiment detection",
            "Portfolio optimization recommendations",
            "Risk assessment and position sizing",
            "Tool use for real-time data access",
            "Streaming responses for interactive chat",
            "Conversational trading interface"
        ],
        "trading_tools": [
            "analyze_market_data",
            "execute_trade_order",
            "get_portfolio_status",
            "calculate_risk_metrics"
        ]
    }
