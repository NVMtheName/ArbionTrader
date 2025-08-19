"""
OpenAI Integration Routes for Arbion Trading Platform
Complete API endpoints for OpenAI-powered trading functionality
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any

from utils.simple_comprehensive_openai import create_comprehensive_openai_client
from models import APICredential, Trade
from app import db

logger = logging.getLogger(__name__)

comprehensive_openai_bp = Blueprint('comprehensive_openai', __name__, url_prefix='/api/openai')

# Helper function for async route handling
def async_route(f):
    """Decorator to handle async functions in Flask routes"""
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(f(*args, **kwargs))
        finally:
            loop.close()
    wrapper.__name__ = f.__name__
    return wrapper

@comprehensive_openai_bp.route('/test_connection', methods=['POST'])
@login_required
@async_route
async def test_openai_connection():
    """Test OpenAI API connection"""
    try:
        client = create_comprehensive_openai_client(user_id=str(current_user.id))
        
        result = await client.test_connection()
        
        return jsonify({
            "success": result.get("success", False),
            "message": result.get("message", "Connection test completed"),
            "details": result
        })
        
    except Exception as e:
        logger.error(f"OpenAI connection test failed: {e}")
        return jsonify({
            "success": False,
            "message": f"Connection test failed: {str(e)}"
        }), 500

@comprehensive_openai_bp.route('/natural_language_trade', methods=['POST'])
@login_required
@async_route
async def process_natural_language_trade():
    """Process natural language trading commands"""
    try:
        data = request.get_json()
        command = data.get('command', '').strip()
        is_simulation = data.get('is_simulation', True)
        
        if not command:
            return jsonify({
                "success": False,
                "message": "Trading command is required"
            }), 400
        
        # Create trading engine
        engine = create_trading_engine(str(current_user.id))
        
        # Process the command
        result = await engine.process_natural_language_trade(command, is_simulation)
        
        return jsonify({
            "success": result.get("success", False),
            "message": result.get("message", "Trade processed"),
            "action": result.get("action"),
            "symbol": result.get("symbol"),
            "decision": {
                "action": result.get("decision", {}).get("action"),
                "symbol": result.get("decision", {}).get("symbol"),
                "confidence": result.get("decision", {}).get("confidence"),
                "reasoning": result.get("decision", {}).get("reasoning")
            } if result.get("decision") else None,
            "execution": result.get("execution")
        })
        
    except Exception as e:
        logger.error(f"Natural language trade processing failed: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to process trade: {str(e)}"
        }), 500

@comprehensive_openai_bp.route('/market_insights', methods=['POST'])
@login_required
@async_route
async def generate_market_insights():
    """Generate AI-powered market insights"""
    try:
        data = request.get_json()
        symbols = data.get('symbols', [])
        
        if not symbols:
            return jsonify({
                "success": False,
                "message": "Symbols list is required"
            }), 400
        
        client = create_comprehensive_openai_client(user_id=str(current_user.id))
        
        insights = await client.generate_market_insights(symbols)
        
        # Convert insights to JSON-serializable format
        insights_data = []
        for insight in insights:
            insights_data.append({
                "symbol": insight.symbol,
                "sentiment": insight.sentiment,
                "price_prediction": insight.price_prediction,
                "volatility_forecast": insight.volatility_forecast,
                "key_factors": insight.key_factors,
                "confidence_score": insight.confidence_score,
                "technical_signals": insight.technical_signals,
                "news_sentiment": insight.news_sentiment
            })
        
        return jsonify({
            "success": True,
            "insights": insights_data,
            "count": len(insights_data)
        })
        
    except Exception as e:
        logger.error(f"Market insights generation failed: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to generate insights: {str(e)}"
        }), 500

@comprehensive_openai_bp.route('/trading_signals', methods=['POST'])
@login_required
@async_route
async def generate_trading_signals():
    """Generate real-time trading signals"""
    try:
        data = request.get_json()
        symbols = data.get('symbols', [])
        
        if not symbols:
            return jsonify({
                "success": False,
                "message": "Symbols list is required"
            }), 400
        
        engine = create_trading_engine(str(current_user.id))
        
        signals = await engine.monitor_positions_and_generate_signals(symbols)
        
        # Convert signals to JSON format
        signals_data = []
        for signal in signals:
            signals_data.append({
                "symbol": signal.symbol,
                "signal_type": signal.signal_type,
                "strength": signal.strength,
                "price_target": signal.price_target,
                "stop_loss": signal.stop_loss,
                "confidence": signal.confidence,
                "reasoning": signal.reasoning,
                "timestamp": signal.timestamp.isoformat(),
                "expires_at": signal.expires_at.isoformat() if signal.expires_at else None
            })
        
        return jsonify({
            "success": True,
            "signals": signals_data,
            "count": len(signals_data)
        })
        
    except Exception as e:
        logger.error(f"Trading signals generation failed: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to generate signals: {str(e)}"
        }), 500

@comprehensive_openai_bp.route('/portfolio_optimization', methods=['POST'])
@login_required
@async_route
async def optimize_portfolio():
    """Generate AI-powered portfolio optimization"""
    try:
        engine = create_trading_engine(str(current_user.id))
        
        recommendation = await engine.optimize_portfolio_with_ai()
        
        # Convert recommendation to JSON format
        recommendation_data = {
            "total_value": recommendation.total_value,
            "recommendations": recommendation.recommendations,
            "risk_score": recommendation.risk_score,
            "diversification_analysis": recommendation.diversification_analysis,
            "rebalancing_suggestions": recommendation.rebalancing_suggestions,
            "performance_projection": recommendation.performance_projection
        }
        
        return jsonify({
            "success": True,
            "recommendation": recommendation_data
        })
        
    except Exception as e:
        logger.error(f"Portfolio optimization failed: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to optimize portfolio: {str(e)}"
        }), 500

@comprehensive_openai_bp.route('/create_strategy', methods=['POST'])
@login_required
@async_route
async def create_trading_strategy():
    """Create AI-powered trading strategy"""
    try:
        data = request.get_json()
        parameters = data.get('parameters', {})
        
        if not parameters:
            return jsonify({
                "success": False,
                "message": "Strategy parameters are required"
            }), 400
        
        engine = create_trading_engine(str(current_user.id))
        
        strategy = await engine.generate_trading_strategy(parameters)
        
        # Convert strategy to JSON format
        strategy_data = {
            "name": strategy.name,
            "description": strategy.description,
            "entry_conditions": strategy.entry_conditions,
            "exit_conditions": strategy.exit_conditions,
            "risk_parameters": strategy.risk_parameters,
            "expected_return": strategy.expected_return,
            "risk_level": strategy.risk_level,
            "timeframe": strategy.timeframe,
            "confidence_score": strategy.confidence_score
        }
        
        return jsonify({
            "success": True,
            "strategy": strategy_data
        })
        
    except Exception as e:
        logger.error(f"Strategy creation failed: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to create strategy: {str(e)}"
        }), 500

@comprehensive_openai_bp.route('/trading_assistant', methods=['POST'])
@login_required
@async_route
async def trading_assistant_chat():
    """Interactive AI trading assistant"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({
                "success": False,
                "message": "Message is required"
            }), 400
        
        engine = create_trading_engine(str(current_user.id))
        
        response = await engine.continuous_trading_assistant(message)
        
        return jsonify({
            "success": True,
            "response": response,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Trading assistant chat failed: {e}")
        return jsonify({
            "success": False,
            "message": f"Assistant unavailable: {str(e)}"
        }), 500

@comprehensive_openai_bp.route('/performance_analysis', methods=['GET'])
@login_required
@async_route
async def analyze_performance():
    """Analyze trading performance with AI"""
    try:
        days = request.args.get('days', 30, type=int)
        
        engine = create_trading_engine(str(current_user.id))
        
        analysis = await engine.analyze_trading_performance(days)
        
        return jsonify({
            "success": True,
            "analysis": analysis
        })
        
    except Exception as e:
        logger.error(f"Performance analysis failed: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to analyze performance: {str(e)}"
        }), 500

@comprehensive_openai_bp.route('/voice_command', methods=['POST'])
@login_required
@async_route
async def process_voice_command():
    """Process voice trading commands using Whisper"""
    try:
        if 'audio' not in request.files:
            return jsonify({
                "success": False,
                "message": "Audio file is required"
            }), 400
        
        audio_file = request.files['audio']
        audio_data = audio_file.read()
        
        client = create_comprehensive_openai_client(user_id=str(current_user.id))
        
        # Transcribe audio to text
        transcription = await client.transcribe_audio(audio_data)
        
        # Process the transcribed command
        engine = create_trading_engine(str(current_user.id))
        result = await engine.process_natural_language_trade(transcription)
        
        return jsonify({
            "success": True,
            "transcription": transcription,
            "trading_result": result
        })
        
    except Exception as e:
        logger.error(f"Voice command processing failed: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to process voice command: {str(e)}"
        }), 500

@comprehensive_openai_bp.route('/speech_alert', methods=['POST'])
@login_required
@async_route
async def create_speech_alert():
    """Create speech alert for trading notifications"""
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        voice = data.get('voice', 'alloy')
        
        if not text:
            return jsonify({
                "success": False,
                "message": "Text is required"
            }), 400
        
        client = create_comprehensive_openai_client(user_id=str(current_user.id))
        
        # Generate speech
        audio_content = await client.create_speech(text, voice)
        
        # Return audio data as base64
        import base64
        audio_base64 = base64.b64encode(audio_content).decode('utf-8')
        
        return jsonify({
            "success": True,
            "audio_data": audio_base64,
            "text": text,
            "voice": voice
        })
        
    except Exception as e:
        logger.error(f"Speech alert creation failed: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to create speech alert: {str(e)}"
        }), 500

@comprehensive_openai_bp.route('/configure', methods=['POST'])
@login_required
def configure_openai_settings():
    """Configure OpenAI integration settings"""
    try:
        data = request.get_json()
        
        # Update user's OpenAI preferences
        settings = {
            "risk_tolerance": data.get("risk_tolerance", "moderate"),
            "max_position_size": data.get("max_position_size", 5.0),
            "stop_loss_percentage": data.get("stop_loss_percentage", 2.0),
            "take_profit_percentage": data.get("take_profit_percentage", 6.0),
            "preferred_model": data.get("preferred_model", "gpt-4o"),
            "enable_voice_commands": data.get("enable_voice_commands", False),
            "enable_speech_alerts": data.get("enable_speech_alerts", False)
        }
        
        # Save settings to user profile or separate settings table
        # For now, we'll just acknowledge the configuration
        
        return jsonify({
            "success": True,
            "message": "OpenAI settings configured successfully",
            "settings": settings
        })
        
    except Exception as e:
        logger.error(f"OpenAI configuration failed: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to configure settings: {str(e)}"
        }), 500

# Error handlers
@comprehensive_openai_bp.errorhandler(404)
def not_found_error(error):
    return jsonify({"success": False, "message": "Endpoint not found"}), 404

@comprehensive_openai_bp.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({"success": False, "message": "Internal server error"}), 500