"""
OpenAI Responses API Client for Arbion Trading Platform

Modern integration using OpenAI's Responses API (the current recommended interface).
Provides structured outputs, tool use, streaming, and multi-modal capabilities
for AI-powered trading operations.

References: https://github.com/openai/openai-python
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union, AsyncGenerator
from datetime import datetime, timedelta
from dataclasses import dataclass, field

import httpx
from openai import OpenAI, AsyncOpenAI
from openai import (
    APIError,
    APIConnectionError,
    RateLimitError,
    AuthenticationError,
    BadRequestError,
    APITimeoutError,
)

logger = logging.getLogger(__name__)


@dataclass
class ResponsesConfig:
    """Configuration for Responses API calls"""
    model: str = "gpt-4o"
    temperature: float = 0.1
    max_output_tokens: Optional[int] = None
    store: bool = False
    stream: bool = False


@dataclass
class TradingToolResult:
    """Result from a trading tool execution"""
    tool_name: str
    arguments: Dict[str, Any]
    result: Dict[str, Any]
    success: bool = True
    error: Optional[str] = None


# Trading tool definitions for Responses API function calling
TRADING_TOOLS = [
    {
        "type": "function",
        "name": "analyze_market_data",
        "description": "Analyze real-time market data for trading decisions. Returns current prices, technical indicators, and trend analysis.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbols": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of trading symbols to analyze (e.g., ['AAPL', 'BTC-USD'])"
                },
                "timeframe": {
                    "type": "string",
                    "enum": ["1m", "5m", "15m", "1h", "4h", "1d", "1w"],
                    "description": "Analysis timeframe"
                },
                "indicators": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Technical indicators to compute (e.g., ['RSI', 'MACD', 'SMA'])"
                }
            },
            "required": ["symbols"]
        }
    },
    {
        "type": "function",
        "name": "execute_trade_order",
        "description": "Execute a trading order through the connected broker. Supports market, limit, and stop orders.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading symbol (e.g., 'AAPL', 'BTC-USD')"},
                "side": {"type": "string", "enum": ["buy", "sell"], "description": "Order side"},
                "quantity": {"type": "number", "description": "Number of shares/units to trade"},
                "order_type": {"type": "string", "enum": ["market", "limit", "stop", "stop_limit"], "description": "Order type"},
                "price": {"type": "number", "description": "Limit price (required for limit/stop_limit orders)"},
                "stop_loss": {"type": "number", "description": "Stop loss price for risk management"},
                "take_profit": {"type": "number", "description": "Take profit price target"},
                "provider": {"type": "string", "enum": ["coinbase", "schwab", "etrade"], "description": "Broker to execute through"}
            },
            "required": ["symbol", "side", "quantity", "provider"]
        }
    },
    {
        "type": "function",
        "name": "get_portfolio_status",
        "description": "Retrieve current portfolio holdings, balances, and performance metrics across all connected accounts.",
        "parameters": {
            "type": "object",
            "properties": {
                "provider": {"type": "string", "description": "Specific broker or 'all' for aggregate view"},
                "include_history": {"type": "boolean", "description": "Include historical performance data"}
            }
        }
    },
    {
        "type": "function",
        "name": "calculate_risk_metrics",
        "description": "Calculate risk metrics for a portfolio or proposed trade including VaR, Sharpe ratio, and position sizing.",
        "parameters": {
            "type": "object",
            "properties": {
                "positions": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Current or proposed positions for risk analysis"
                },
                "risk_tolerance": {
                    "type": "string",
                    "enum": ["conservative", "moderate", "aggressive"],
                    "description": "Risk tolerance level"
                },
                "analysis_type": {
                    "type": "string",
                    "enum": ["var", "sharpe", "position_sizing", "comprehensive"],
                    "description": "Type of risk analysis"
                }
            },
            "required": ["positions"]
        }
    },
    {
        "type": "function",
        "name": "set_price_alert",
        "description": "Set a price alert for a trading symbol with specified conditions.",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Symbol to monitor"},
                "condition": {"type": "string", "enum": ["above", "below", "crosses"], "description": "Alert trigger condition"},
                "price": {"type": "number", "description": "Target price for the alert"},
                "notification_type": {"type": "string", "enum": ["push", "email", "sms"], "description": "How to notify"}
            },
            "required": ["symbol", "condition", "price"]
        }
    }
]


class OpenAIResponsesClient:
    """
    Modern OpenAI client using the Responses API.

    The Responses API is OpenAI's current recommended interface, providing:
    - Simplified input/output with `input` and `instructions`
    - Built-in tool use with automatic execution loops
    - Streaming support via server-sent events
    - Structured outputs
    - Multi-modal input (text + images)
    """

    def __init__(self, user_id: str = None, api_key: str = None):
        self.user_id = user_id
        self.api_key = api_key or self._load_api_key(user_id)

        if not self.api_key:
            raise ValueError("OpenAI API key is required")

        # Client configuration with proper timeouts and retries
        client_kwargs = {
            "api_key": self.api_key,
            "timeout": httpx.Timeout(120.0, connect=10.0),
            "max_retries": 3,
        }

        org_id = os.environ.get("OPENAI_ORG_ID")
        if org_id:
            client_kwargs["organization"] = org_id

        project_id = os.environ.get("OPENAI_PROJECT_ID")
        if project_id:
            client_kwargs["project"] = project_id

        base_url = os.environ.get("OPENAI_BASE_URL")
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = OpenAI(**client_kwargs)
        self.async_client = AsyncOpenAI(**client_kwargs)

        # Available models
        self.models = {
            "primary": "gpt-4o",
            "fast": "gpt-4o-mini",
            "reasoning": "o1",
            "reasoning_fast": "o3-mini",
        }

        # Tool handler registry
        self._tool_handlers = {}
        self._register_default_tool_handlers()

        logger.info(f"OpenAI Responses client initialized for user {user_id}")

    def _load_api_key(self, user_id: str) -> Optional[str]:
        """Load API key from database or environment"""
        # Try environment first
        env_key = os.environ.get("OPENAI_API_KEY")
        if env_key:
            return env_key

        if not user_id:
            return None

        try:
            from models import APICredential
            from utils.encryption import decrypt_credentials

            credential = APICredential.query.filter_by(
                user_id=user_id,
                provider='openai',
                is_active=True
            ).first()

            if credential:
                creds = decrypt_credentials(credential.encrypted_credentials)
                return creds.get('api_key')
        except Exception as e:
            logger.error(f"Failed to load API key for user {user_id}: {e}")

        return None

    def _register_default_tool_handlers(self):
        """Register default handlers for trading tools"""
        self._tool_handlers = {
            "analyze_market_data": self._handle_analyze_market,
            "execute_trade_order": self._handle_execute_trade,
            "get_portfolio_status": self._handle_get_portfolio,
            "calculate_risk_metrics": self._handle_calculate_risk,
            "set_price_alert": self._handle_set_alert,
        }

    def register_tool_handler(self, name: str, handler):
        """Register a custom tool handler"""
        self._tool_handlers[name] = handler

    # ---- RESPONSES API: Core Methods ----

    async def create_response(
        self,
        input_text: str,
        instructions: str = None,
        model: str = None,
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.1,
        max_output_tokens: Optional[int] = None,
        response_format: Optional[Dict] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a response using the Responses API.

        This is the modern replacement for chat.completions.create().
        Uses `input` instead of `messages` and `instructions` instead of system messages.
        """
        try:
            params = {
                "model": model or self.models["primary"],
                "input": input_text,
                "temperature": temperature,
            }

            if instructions:
                params["instructions"] = instructions
            if tools:
                params["tools"] = tools
            if max_output_tokens:
                params["max_output_tokens"] = max_output_tokens
            if response_format:
                params["text"] = {"format": response_format}
            if stream:
                params["stream"] = True

            if stream:
                return await self._stream_response(params)

            response = await self.async_client.responses.create(**params)

            return {
                "success": True,
                "output_text": response.output_text,
                "response_id": response.id,
                "model": response.model,
                "usage": {
                    "input_tokens": response.usage.input_tokens if response.usage else 0,
                    "output_tokens": response.usage.output_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                } if response.usage else None,
                "output": [item.model_dump() for item in response.output] if response.output else [],
            }

        except AuthenticationError as e:
            logger.error(f"Authentication failed: {e}")
            return {"success": False, "error": "authentication_failed", "message": str(e)}
        except RateLimitError as e:
            logger.error(f"Rate limit exceeded: {e}")
            return {"success": False, "error": "rate_limit", "message": str(e)}
        except BadRequestError as e:
            logger.error(f"Bad request: {e}")
            return {"success": False, "error": "bad_request", "message": str(e)}
        except APIConnectionError as e:
            logger.error(f"Connection error: {e}")
            return {"success": False, "error": "connection_error", "message": str(e)}
        except APITimeoutError as e:
            logger.error(f"Request timed out: {e}")
            return {"success": False, "error": "timeout", "message": str(e)}
        except APIError as e:
            logger.error(f"API error: {e}")
            return {"success": False, "error": "api_error", "message": str(e)}

    async def _stream_response(self, params: Dict) -> AsyncGenerator[str, None]:
        """Handle streaming responses from the Responses API"""
        try:
            stream = await self.async_client.responses.create(**params)
            async for event in stream:
                if hasattr(event, 'type'):
                    if event.type == 'response.output_text.delta':
                        yield event.delta
                    elif event.type == 'response.completed':
                        break
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"\n[Error: {str(e)}]"

    async def create_response_with_tools(
        self,
        input_text: str,
        instructions: str = None,
        model: str = None,
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.1,
        max_output_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Create a response with automatic tool call handling.

        Processes the response, executes any tool calls, and returns
        the final response after tool results are incorporated.
        """
        try:
            effective_tools = tools or TRADING_TOOLS
            params = {
                "model": model or self.models["primary"],
                "input": input_text,
                "tools": effective_tools,
                "temperature": temperature,
            }

            if instructions:
                params["instructions"] = instructions
            if max_output_tokens:
                params["max_output_tokens"] = max_output_tokens

            response = await self.async_client.responses.create(**params)

            # Check for tool calls in the output
            tool_results = []
            has_tool_calls = False

            if response.output:
                for item in response.output:
                    if hasattr(item, 'type') and item.type == 'function_call':
                        has_tool_calls = True
                        tool_name = item.name
                        tool_args = json.loads(item.arguments) if isinstance(item.arguments, str) else item.arguments

                        # Execute the tool
                        handler = self._tool_handlers.get(tool_name)
                        if handler:
                            result = await handler(**tool_args)
                        else:
                            result = {"error": f"No handler for tool: {tool_name}"}

                        tool_results.append(TradingToolResult(
                            tool_name=tool_name,
                            arguments=tool_args,
                            result=result,
                            success="error" not in result,
                        ))

            # If there were tool calls, send results back for final response
            if has_tool_calls and tool_results:
                # Build follow-up input with tool results
                follow_up_input = [
                    {"role": "user", "content": input_text}
                ]

                # Add each tool call and its result
                for item in response.output:
                    if hasattr(item, 'type') and item.type == 'function_call':
                        follow_up_input.append(item.model_dump())
                        matching_result = next(
                            (tr for tr in tool_results if tr.tool_name == item.name),
                            None
                        )
                        if matching_result:
                            follow_up_input.append({
                                "type": "function_call_output",
                                "call_id": item.call_id,
                                "output": json.dumps(matching_result.result),
                            })

                # Get final response with tool results
                final_response = await self.async_client.responses.create(
                    model=model or self.models["primary"],
                    input=follow_up_input,
                    instructions=instructions,
                    temperature=temperature,
                )

                return {
                    "success": True,
                    "output_text": final_response.output_text,
                    "response_id": final_response.id,
                    "tool_calls": [
                        {
                            "tool": tr.tool_name,
                            "arguments": tr.arguments,
                            "result": tr.result,
                            "success": tr.success,
                        }
                        for tr in tool_results
                    ],
                    "model": final_response.model,
                }

            return {
                "success": True,
                "output_text": response.output_text,
                "response_id": response.id,
                "tool_calls": [],
                "model": response.model,
            }

        except Exception as e:
            logger.error(f"Response with tools failed: {e}")
            return {"success": False, "error": str(e)}

    # ---- CHAT COMPLETIONS API (Legacy, still supported) ----

    async def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict]] = None,
        response_format: Optional[Dict] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Chat Completions API (legacy but fully supported).

        Use this when you need message-based conversations with role history,
        or when integrating with existing code that uses the messages format.
        """
        try:
            params = {
                "model": model or self.models["primary"],
                "messages": messages,
                "temperature": temperature,
            }

            if max_tokens:
                params["max_tokens"] = max_tokens
            if tools:
                params["tools"] = tools
            if response_format:
                params["response_format"] = response_format
            if stream:
                params["stream"] = True

            if stream:
                return await self._stream_chat_completion(params)

            response = await self.async_client.chat.completions.create(**params)

            return {
                "success": True,
                "content": response.choices[0].message.content,
                "role": response.choices[0].message.role,
                "finish_reason": response.choices[0].finish_reason,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "function": tc.function.name,
                        "arguments": json.loads(tc.function.arguments),
                    }
                    for tc in (response.choices[0].message.tool_calls or [])
                ],
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                } if response.usage else None,
                "model": response.model,
                "response_id": response.id,
            }

        except Exception as e:
            logger.error(f"Chat completion failed: {e}")
            return {"success": False, "error": str(e)}

    async def _stream_chat_completion(self, params: Dict) -> AsyncGenerator[str, None]:
        """Handle streaming chat completions"""
        try:
            stream = await self.async_client.chat.completions.create(**params)
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"\n[Error: {str(e)}]"

    # ---- TRADING-SPECIFIC METHODS ----

    async def process_trading_command(self, command: str) -> Dict[str, Any]:
        """
        Process a natural language trading command using the Responses API.

        Examples:
            "Buy 100 shares of AAPL at market"
            "Analyze Bitcoin and Ethereum market trends"
            "What's the risk of my current portfolio?"
        """
        instructions = """You are an expert AI trading assistant for the Arbion platform.

Your capabilities:
- Parse and execute trading commands across stocks, crypto, and options
- Analyze market data with technical and fundamental indicators
- Assess risk and recommend position sizing
- Monitor portfolios and suggest optimizations

Rules:
1. Always use the available tools to access real market data before making recommendations
2. Consider risk management in every trading decision
3. Provide confidence levels (0.0-1.0) for all recommendations
4. Never guarantee profits - always disclose risks
5. Use appropriate position sizing based on account balance and risk tolerance
6. Respect the user's risk tolerance preferences

When processing trade orders:
- Validate the symbol and determine the correct broker (crypto -> coinbase, stocks -> schwab)
- Check risk parameters before execution
- Provide clear confirmation of what will be executed"""

        result = await self.create_response_with_tools(
            input_text=command,
            instructions=instructions,
            tools=TRADING_TOOLS,
            temperature=0.1,
        )

        return {
            "success": result.get("success", False),
            "command": command,
            "response": result.get("output_text", ""),
            "tool_calls": result.get("tool_calls", []),
            "model": result.get("model"),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def analyze_market(
        self,
        symbols: List[str],
        analysis_type: str = "comprehensive"
    ) -> Dict[str, Any]:
        """Perform AI-powered market analysis using the Responses API"""
        input_text = f"""Perform a {analysis_type} market analysis for: {', '.join(symbols)}

Please analyze using the available tools and provide:
1. Current price and trend direction
2. Technical indicator signals (RSI, MACD, moving averages)
3. Market sentiment assessment
4. Key support and resistance levels
5. Trading recommendations with confidence levels
6. Risk factors and volatility assessment

Use the analyze_market_data tool to get current data, then provide your expert analysis."""

        instructions = (
            "You are a senior market analyst with expertise in technical analysis, "
            "fundamental analysis, and quantitative finance. Provide data-driven, "
            "actionable market insights. Always cite specific data points."
        )

        return await self.create_response_with_tools(
            input_text=input_text,
            instructions=instructions,
            tools=TRADING_TOOLS,
            temperature=0.2,
        )

    async def generate_trading_strategy(
        self,
        strategy_type: str,
        risk_tolerance: str = "moderate",
        time_horizon: str = "medium",
        capital: float = 10000.0,
    ) -> Dict[str, Any]:
        """Generate an AI-powered trading strategy"""
        input_text = f"""Generate a comprehensive {strategy_type} trading strategy with:
- Risk Tolerance: {risk_tolerance}
- Time Horizon: {time_horizon}
- Available Capital: ${capital:,.2f}

Include specific entry/exit rules, position sizing, risk management parameters,
asset selection criteria, and a monitoring/rebalancing schedule.

Provide quantitative thresholds where possible."""

        instructions = (
            "You are a quantitative trading strategist. Generate detailed, "
            "implementable trading strategies with specific numeric parameters. "
            "Consider modern portfolio theory, risk-adjusted returns, and "
            "practical execution constraints."
        )

        return await self.create_response(
            input_text=input_text,
            instructions=instructions,
            model=self.models["primary"],
            temperature=0.2,
            response_format={"type": "json_object"},
        )

    async def assess_trade_risk(
        self,
        trade_details: Dict[str, Any],
        portfolio_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Assess risk for a proposed trade"""
        input_text = f"""Assess the risk of this proposed trade:

Trade Details: {json.dumps(trade_details, indent=2)}
Portfolio Context: {json.dumps(portfolio_context, indent=2) if portfolio_context else 'Not provided'}

Provide:
1. Overall risk score (0-100)
2. Position-specific risks
3. Portfolio impact analysis
4. Scenario analysis (best/worst/expected)
5. Risk mitigation recommendations
6. Position sizing suggestion"""

        instructions = (
            "You are a risk management specialist. Provide quantitative risk "
            "assessment with specific metrics. Be conservative in your estimates "
            "and always highlight potential downsides."
        )

        return await self.create_response(
            input_text=input_text,
            instructions=instructions,
            temperature=0.1,
            response_format={"type": "json_object"},
        )

    async def portfolio_optimization(
        self,
        current_positions: List[Dict],
        optimization_goal: str = "risk_adjusted_return",
    ) -> Dict[str, Any]:
        """Generate AI-powered portfolio optimization recommendations"""
        input_text = f"""Optimize this portfolio for {optimization_goal}:

Current Positions: {json.dumps(current_positions, indent=2)}

Provide:
1. Current allocation assessment
2. Recommended target allocation
3. Specific rebalancing trades needed
4. Expected improvement in risk-adjusted returns
5. Diversification analysis
6. Tax-efficient rebalancing suggestions"""

        instructions = (
            "You are a portfolio optimization expert using modern portfolio theory. "
            "Provide specific, actionable rebalancing recommendations with "
            "expected impact on portfolio metrics."
        )

        return await self.create_response_with_tools(
            input_text=input_text,
            instructions=instructions,
            tools=TRADING_TOOLS,
            temperature=0.2,
        )

    async def chat_with_trader(
        self,
        message: str,
        conversation_history: Optional[List[Dict]] = None,
        stream: bool = False,
    ) -> Union[Dict[str, Any], AsyncGenerator[str, None]]:
        """
        Interactive trading assistant conversation.

        Falls back to Chat Completions API for multi-turn conversations
        since it natively supports message history.
        """
        messages = [
            {
                "role": "developer",
                "content": """You are an expert AI trading assistant for the Arbion platform.

You can help users with:
- Market analysis and trading recommendations
- Portfolio management and optimization
- Risk assessment and position sizing
- Trading strategy development
- Understanding market trends and indicators

Always provide data-driven insights, consider risk management,
and never guarantee returns. Be clear about uncertainty levels."""
            }
        ]

        if conversation_history:
            messages.extend(conversation_history[-20:])

        messages.append({"role": "user", "content": message})

        if stream:
            return self._stream_chat_completion({
                "model": self.models["primary"],
                "messages": messages,
                "tools": [
                    {"type": "function", "function": t} if "function" in t else t
                    for t in TRADING_TOOLS
                ],
                "stream": True,
                "temperature": 0.3,
            })

        return await self.create_chat_completion(
            messages=messages,
            tools=[
                {"type": "function", "function": t} if "function" in t else t
                for t in TRADING_TOOLS
            ],
            temperature=0.3,
        )

    # ---- EMBEDDINGS ----

    async def create_embeddings(
        self, texts: List[str], model: str = "text-embedding-3-large"
    ) -> List[List[float]]:
        """Create text embeddings for semantic search and similarity"""
        try:
            response = await self.async_client.embeddings.create(
                model=model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"Embeddings creation failed: {e}")
            raise

    # ---- AUDIO ----

    async def text_to_speech(
        self, text: str, voice: str = "alloy", model: str = "tts-1"
    ) -> bytes:
        """Convert text to speech for voice trading alerts"""
        try:
            response = await self.async_client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
            )
            return response.content
        except Exception as e:
            logger.error(f"Text-to-speech failed: {e}")
            raise

    async def speech_to_text(self, audio_data: bytes) -> str:
        """Transcribe audio for voice trading commands"""
        try:
            from io import BytesIO
            buffer = BytesIO(audio_data)
            buffer.name = "audio.wav"

            transcript = await self.async_client.audio.transcriptions.create(
                model="whisper-1",
                file=buffer,
            )
            return transcript.text
        except Exception as e:
            logger.error(f"Speech-to-text failed: {e}")
            raise

    # ---- MODERATION ----

    async def moderate_content(self, content: str) -> Dict[str, Any]:
        """Check content for policy violations before processing"""
        try:
            response = await self.async_client.moderations.create(input=content)
            result = response.results[0]
            return {
                "flagged": result.flagged,
                "categories": result.categories.model_dump(),
                "safe": not result.flagged,
            }
        except Exception as e:
            logger.error(f"Moderation check failed: {e}")
            return {"flagged": False, "safe": True, "error": str(e)}

    # ---- CONNECTION & STATUS ----

    async def test_connection(self) -> Dict[str, Any]:
        """Test the OpenAI API connection"""
        try:
            # Quick test with Responses API
            response = await self.async_client.responses.create(
                model="gpt-4o-mini",
                input="Connection test. Reply with 'ok'.",
                max_output_tokens=5,
            )

            return {
                "success": True,
                "message": "OpenAI API connection successful",
                "model_used": response.model,
                "response_id": response.id,
                "api_version": "responses",
                "timestamp": datetime.utcnow().isoformat(),
            }

        except AuthenticationError as e:
            return {
                "success": False,
                "error": "authentication_failed",
                "message": f"Invalid API key: {e}",
                "solution": "Check your API key at https://platform.openai.com/api-keys",
            }
        except RateLimitError as e:
            return {
                "success": False,
                "error": "rate_limited",
                "message": f"Rate limit exceeded: {e}",
                "solution": "Wait before retrying or upgrade your plan",
            }
        except APIConnectionError as e:
            return {
                "success": False,
                "error": "connection_failed",
                "message": f"Cannot connect to OpenAI: {e}",
                "solution": "Check your network connection",
            }
        except Exception as e:
            return {
                "success": False,
                "error": "unknown",
                "message": str(e),
            }

    def get_status(self) -> Dict[str, Any]:
        """Get client status and capabilities"""
        return {
            "user_id": self.user_id,
            "api_key_present": bool(self.api_key),
            "available_models": self.models,
            "api_version": "responses + chat_completions",
            "tools_registered": list(self._tool_handlers.keys()),
            "capabilities": [
                "responses_api",
                "chat_completions",
                "function_calling",
                "streaming",
                "embeddings",
                "audio_tts",
                "audio_stt",
                "moderation",
                "structured_outputs",
                "multi_modal",
            ],
        }

    # ---- TOOL HANDLERS ----

    async def _handle_analyze_market(self, symbols: List[str], **kwargs) -> Dict:
        """Handle market data analysis tool calls"""
        try:
            from utils.comprehensive_market_data import ComprehensiveMarketDataProvider
            provider = ComprehensiveMarketDataProvider()

            results = {}
            for symbol in symbols:
                data = provider.get_symbol_data(symbol)
                results[symbol] = {
                    "price": data.get("price", 0),
                    "change_percent": data.get("change_percent", 0),
                    "volume": data.get("volume", 0),
                    "high": data.get("high", 0),
                    "low": data.get("low", 0),
                    "timestamp": datetime.utcnow().isoformat(),
                }

            return {"success": True, "data": results}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_execute_trade(self, symbol: str, side: str, quantity: float, provider: str, **kwargs) -> Dict:
        """Handle trade execution tool calls"""
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
                is_simulation=kwargs.get("is_simulation", True),
            )

            # Log the trade
            try:
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
                    is_simulation=kwargs.get("is_simulation", True),
                )
                db.session.add(trade)
                db.session.commit()
            except Exception as log_err:
                logger.warning(f"Trade logging failed: {log_err}")

            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_get_portfolio(self, **kwargs) -> Dict:
        """Handle portfolio status tool calls"""
        try:
            from routes import get_account_balance
            balance_data = get_account_balance()
            return {
                "success": True,
                "total_balance": balance_data.get("total", 0),
                "accounts": balance_data.get("accounts", []),
                "last_updated": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_calculate_risk(self, positions: List[Dict], **kwargs) -> Dict:
        """Handle risk calculation tool calls"""
        try:
            total_value = sum(pos.get("value", 0) for pos in positions)
            if total_value <= 0:
                return {"success": False, "error": "No position value"}

            largest = max(positions, key=lambda x: x.get("value", 0)) if positions else {}
            largest_pct = (largest.get("value", 0) / total_value * 100) if total_value > 0 else 0

            recommendations = []
            if largest_pct > 20:
                recommendations.append("Reduce concentration in largest position")
            if len(positions) < 5:
                recommendations.append("Increase diversification across more positions")

            risk_score = min(100, largest_pct + (100 / max(len(positions), 1)))

            return {
                "success": True,
                "total_value": total_value,
                "position_count": len(positions),
                "largest_position_pct": round(largest_pct, 2),
                "risk_score": round(risk_score, 2),
                "recommendations": recommendations,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _handle_set_alert(self, symbol: str, condition: str, price: float, **kwargs) -> Dict:
        """Handle price alert setup"""
        return {
            "success": True,
            "alert": {
                "symbol": symbol,
                "condition": condition,
                "price": price,
                "notification_type": kwargs.get("notification_type", "push"),
                "status": "active",
                "created_at": datetime.utcnow().isoformat(),
            },
        }


# Factory functions
def create_responses_client(user_id: str = None, api_key: str = None) -> OpenAIResponsesClient:
    """Create an OpenAI Responses API client"""
    return OpenAIResponsesClient(user_id=user_id, api_key=api_key)


def get_responses_api_info() -> Dict[str, Any]:
    """Get information about the Responses API integration"""
    return {
        "description": "OpenAI Responses API integration for AI-powered trading",
        "api_version": "Responses API (current) + Chat Completions (legacy)",
        "features": [
            "Responses API with simplified input/output",
            "Automatic tool call handling for trading operations",
            "Streaming responses for real-time interaction",
            "Chat Completions API for multi-turn conversations",
            "Function calling for market analysis and trade execution",
            "Text embeddings for semantic search",
            "Audio transcription for voice commands",
            "Text-to-speech for voice alerts",
            "Content moderation for safety",
            "Structured JSON outputs",
            "Multi-modal input support",
        ],
        "models": {
            "gpt-4o": "Primary model for comprehensive analysis",
            "gpt-4o-mini": "Fast model for quick responses",
            "o1": "Reasoning model for complex strategy development",
            "o3-mini": "Fast reasoning model",
        },
        "trading_tools": [
            "analyze_market_data",
            "execute_trade_order",
            "get_portfolio_status",
            "calculate_risk_metrics",
            "set_price_alert",
        ],
    }
