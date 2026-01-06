"""
Comprehensive OpenAI Integration for Arbion Trading Platform
Simplified but complete implementation of OpenAI capabilities for trading.
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from dataclasses import dataclass

from openai import OpenAI, AsyncOpenAI
from models import APICredential
from utils.encryption import decrypt_credentials

logger = logging.getLogger(__name__)

@dataclass
class TradingDecision:
    """AI trading decision"""
    symbol: str
    action: str  # buy, sell, hold
    confidence: float
    quantity: Optional[float] = None
    price_target: Optional[float] = None
    reasoning: str = ""

@dataclass
class MarketInsight:
    """AI market insights"""
    symbol: str
    sentiment: str  # bullish, bearish, neutral
    confidence_score: float
    key_factors: Optional[List[str]] = None
    price_prediction: Optional[float] = None

class ComprehensiveOpenAIClient:
    """Comprehensive OpenAI client for trading"""
    
    def __init__(self, user_id: Optional[str] = None, api_key: Optional[str] = None):
        self.user_id = user_id
        self.api_key = api_key or self._load_api_key(user_id)
        
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self.client = OpenAI(api_key=self.api_key)
        self.async_client = AsyncOpenAI(api_key=self.api_key)
        
        # Model configuration
        self.models = {
            "gpt-4o": "gpt-4o",
            "gpt-4o-mini": "gpt-4o-mini", 
            "whisper-1": "whisper-1",
            "tts-1": "tts-1",
            "text-embedding-3-large": "text-embedding-3-large"
        }
        
        logger.info(f"OpenAI client initialized for user {user_id}")
    
    def _load_api_key(self, user_id: Optional[str]) -> Optional[str]:
        """Load API key from database"""
        if not user_id:
            return None
            
        try:
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
    
    # CHAT COMPLETIONS
    async def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-5.2",
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Enhanced chat completion"""
        try:
            params = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
            }
            
            if max_tokens:
                params["max_tokens"] = max_tokens
            if response_format:
                params["response_format"] = response_format
            
            response = await self.async_client.chat.completions.create(**params)
            
            return {
                "success": True,
                "response": response.choices[0].message.content,
                "usage": response.usage.total_tokens if response.usage else 0
            }
                
        except Exception as e:
            logger.error(f"Chat completion failed: {e}")
            return {"success": False, "error": str(e)}
    
    # NATURAL LANGUAGE TRADING
    async def process_trading_command(self, command: str) -> TradingDecision:
        """Process natural language trading commands"""
        try:
            messages = [
                {
                    "role": "system",
                    "content": """You are an AI trading assistant. Parse trading commands and return structured decisions.
                    
                    Respond with JSON in this exact format:
                    {
                        "symbol": "SYMBOL",
                        "action": "buy/sell/hold",
                        "confidence": 0.8,
                        "quantity": 100.0,
                        "price_target": 150.0,
                        "reasoning": "Clear explanation"
                    }
                    
                    Always consider risk management and market conditions."""
                },
                {
                    "role": "user",
                    "content": f"Parse this trading command: {command}"
                }
            ]
            
            result = await self.create_chat_completion(
                messages=messages,
                model="gpt-5.2",
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            if result.get("success"):
                decision_data = json.loads(result["response"])
                return TradingDecision(
                    symbol=decision_data.get("symbol", ""),
                    action=decision_data.get("action", "hold"),
                    confidence=decision_data.get("confidence", 0.0),
                    quantity=decision_data.get("quantity"),
                    price_target=decision_data.get("price_target"),
                    reasoning=decision_data.get("reasoning", "")
                )
            else:
                raise Exception(result.get("error", "Unknown error"))
                
        except Exception as e:
            logger.error(f"Trading command processing failed: {e}")
            return TradingDecision(
                symbol="ERROR",
                action="hold",
                confidence=0.0,
                reasoning=f"Error processing command: {str(e)}"
            )
    
    # MARKET ANALYSIS
    async def generate_market_insights(self, symbols: List[str]) -> List[MarketInsight]:
        """Generate market insights for symbols"""
        try:
            insights = []
            
            for symbol in symbols:
                messages = [
                    {
                        "role": "system",
                        "content": "You are a market analyst. Provide insights in JSON format."
                    },
                    {
                        "role": "user",
                        "content": f"""Analyze {symbol} and provide market insight in JSON format:
                        {{
                            "sentiment": "bullish/bearish/neutral",
                            "confidence_score": 0.8,
                            "key_factors": ["factor1", "factor2"],
                            "price_prediction": 150.0
                        }}"""
                    }
                ]
                
                result = await self.create_chat_completion(
                    messages=messages,
                    model="gpt-5.2",
                    response_format={"type": "json_object"}
                )
                
                if result.get("success"):
                    insight_data = json.loads(result["response"])
                    insights.append(MarketInsight(
                        symbol=symbol,
                        sentiment=insight_data.get("sentiment", "neutral"),
                        confidence_score=insight_data.get("confidence_score", 0.5),
                        key_factors=insight_data.get("key_factors", []),
                        price_prediction=insight_data.get("price_prediction")
                    ))
            
            return insights
            
        except Exception as e:
            logger.error(f"Market insights generation failed: {e}")
            return []
    
    # AUDIO CAPABILITIES  
    async def create_speech(self, text: str, voice: str = "alloy") -> bytes:
        """Convert text to speech"""
        try:
            response = await self.async_client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text
            )
            return response.content
        except Exception as e:
            logger.error(f"Speech creation failed: {e}")
            raise
    
    async def transcribe_audio(self, audio_file: bytes) -> str:
        """Convert audio to text"""
        try:
            from io import BytesIO
            audio_buffer = BytesIO(audio_file)
            audio_buffer.name = "audio.wav"
            
            transcript = await self.async_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_buffer
            )
            return transcript.text
        except Exception as e:
            logger.error(f"Audio transcription failed: {e}")
            raise
    
    # EMBEDDINGS
    async def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Create embeddings for texts"""
        try:
            response = await self.async_client.embeddings.create(
                model="text-embedding-3-large",
                input=texts
            )
            return [embedding.embedding for embedding in response.data]
        except Exception as e:
            logger.error(f"Embeddings creation failed: {e}")
            raise
    
    # MODERATION
    async def moderate_content(self, content: str) -> Dict[str, Any]:
        """Moderate content for safety"""
        try:
            response = await self.async_client.moderations.create(input=content)
            result = response.results[0]
            return {
                "flagged": result.flagged,
                "categories": dict(result.categories),
                "safe": not result.flagged
            }
        except Exception as e:
            logger.error(f"Content moderation failed: {e}")
            return {"flagged": False, "safe": True, "error": str(e)}
    
    # CONNECTION TEST
    async def test_connection(self) -> Dict[str, Any]:
        """Test OpenAI connection"""
        try:
            # Test models endpoint
            models = self.client.models.list()
            
            # Test simple chat
            response = await self.create_chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="gpt-5.2-mini",
                max_tokens=1
            )
            
            return {
                "success": True,
                "models_count": len(models.data),
                "chat_working": response.get("success", False),
                "message": "OpenAI connection successful"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "OpenAI connection failed"
            }
    
    # TRADING ASSISTANT CONVERSATION
    async def chat_with_assistant(self, message: str, conversation_history: Optional[List[Dict]] = None) -> str:
        """Interactive trading assistant"""
        try:
            messages = [
                {
                    "role": "system",
                    "content": """You are an expert AI trading assistant for Arbion platform.
                    
                    You can:
                    - Analyze market conditions
                    - Provide trading recommendations  
                    - Explain market trends
                    - Help with risk management
                    - Answer trading questions
                    
                    Always provide helpful, accurate information and consider risk management."""
                }
            ]
            
            # Add conversation history
            if conversation_history:
                messages.extend(conversation_history)
            
            # Add current message
            messages.append({"role": "user", "content": message})
            
            result = await self.create_chat_completion(
                messages=messages,
                model="gpt-5.2"
            )
            
            if result.get("success"):
                return result["response"]
            else:
                return f"I encountered an error: {result.get('error')}"
                
        except Exception as e:
            logger.error(f"Assistant chat failed: {e}")
            return f"I'm having trouble responding right now: {str(e)}"

def create_comprehensive_openai_client(user_id: Optional[str] = None, api_key: Optional[str] = None) -> ComprehensiveOpenAIClient:
    """Factory function to create OpenAI client"""
    return ComprehensiveOpenAIClient(user_id=user_id, api_key=api_key)