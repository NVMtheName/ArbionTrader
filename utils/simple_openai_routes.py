"""
Simple OpenAI Routes for Arbion Trading Platform
Basic API endpoints for OpenAI integration
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import asyncio
import json
import logging
from datetime import datetime

from utils.simple_comprehensive_openai import create_comprehensive_openai_client

logger = logging.getLogger(__name__)

simple_openai_bp = Blueprint('simple_openai', __name__, url_prefix='/api/simple-openai')

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

@simple_openai_bp.route('/test', methods=['POST'])
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
            "details": {
                "models_count": result.get("models_count", 0),
                "chat_working": result.get("chat_working", False)
            }
        })
        
    except Exception as e:
        logger.error(f"OpenAI connection test failed: {e}")
        return jsonify({
            "success": False,
            "message": f"Connection test failed: {str(e)}"
        }), 500

@simple_openai_bp.route('/chat', methods=['POST'])
@login_required
@async_route
async def chat_with_assistant():
    """Chat with AI trading assistant"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({
                "success": False,
                "message": "Message is required"
            }), 400
        
        client = create_comprehensive_openai_client(user_id=str(current_user.id))
        response = await client.chat_with_assistant(message)
        
        return jsonify({
            "success": True,
            "response": response,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Assistant chat failed: {e}")
        return jsonify({
            "success": False,
            "message": f"Assistant unavailable: {str(e)}"
        }), 500

@simple_openai_bp.route('/trade-command', methods=['POST'])
@login_required
@async_route
async def process_trade_command():
    """Process natural language trading command"""
    try:
        data = request.get_json()
        command = data.get('command', '').strip()
        
        if not command:
            return jsonify({
                "success": False,
                "message": "Trading command is required"
            }), 400
        
        client = create_comprehensive_openai_client(user_id=str(current_user.id))
        decision = await client.process_trading_command(command)
        
        return jsonify({
            "success": True,
            "decision": {
                "symbol": decision.symbol,
                "action": decision.action,
                "confidence": decision.confidence,
                "quantity": decision.quantity,
                "price_target": decision.price_target,
                "reasoning": decision.reasoning
            }
        })
        
    except Exception as e:
        logger.error(f"Trade command processing failed: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to process command: {str(e)}"
        }), 500

@simple_openai_bp.route('/market-insights', methods=['POST'])
@login_required
@async_route
async def get_market_insights():
    """Get AI market insights"""
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
        
        insights_data = []
        for insight in insights:
            insights_data.append({
                "symbol": insight.symbol,
                "sentiment": insight.sentiment,
                "confidence_score": insight.confidence_score,
                "key_factors": insight.key_factors or [],
                "price_prediction": insight.price_prediction
            })
        
        return jsonify({
            "success": True,
            "insights": insights_data,
            "count": len(insights_data)
        })
        
    except Exception as e:
        logger.error(f"Market insights failed: {e}")
        return jsonify({
            "success": False,
            "message": f"Failed to generate insights: {str(e)}"
        }), 500

@simple_openai_bp.route('/moderate', methods=['POST'])
@login_required
@async_route
async def moderate_content():
    """Moderate content for safety"""
    try:
        data = request.get_json()
        content = data.get('content', '').strip()
        
        if not content:
            return jsonify({
                "success": False,
                "message": "Content is required"
            }), 400
        
        client = create_comprehensive_openai_client(user_id=str(current_user.id))
        result = await client.moderate_content(content)
        
        return jsonify({
            "success": True,
            "moderation": result
        })
        
    except Exception as e:
        logger.error(f"Content moderation failed: {e}")
        return jsonify({
            "success": False,
            "message": f"Moderation failed: {str(e)}"
        }), 500

# Error handlers
@simple_openai_bp.errorhandler(404)
def not_found_error(error):
    return jsonify({"success": False, "message": "Endpoint not found"}), 404

@simple_openai_bp.errorhandler(500)
def internal_error(error):
    return jsonify({"success": False, "message": "Internal server error"}), 500