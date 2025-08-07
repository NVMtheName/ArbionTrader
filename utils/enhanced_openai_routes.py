"""
Enhanced OpenAI API Routes for Arbion Trading Platform
Flask endpoints for advanced AI trading capabilities and natural language processing
"""

from flask import Blueprint, request, jsonify, Response, stream_template
from flask_login import login_required, current_user
import asyncio
import json
import logging
from typing import AsyncGenerator
from utils.enhanced_openai_client import EnhancedOpenAIClient, get_openai_enhancement_info

logger = logging.getLogger(__name__)

# Create blueprint for enhanced OpenAI routes
enhanced_openai_bp = Blueprint('enhanced_openai', __name__)

@enhanced_openai_bp.route('/api/openai/info', methods=['GET'])
@login_required
def get_openai_info():
    """Get information about OpenAI enhancements"""
    try:
        info = get_openai_enhancement_info()
        return jsonify({
            'success': True,
            'openai_info': info
        })
    
    except Exception as e:
        logger.error(f"Error getting OpenAI info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@enhanced_openai_bp.route('/api/openai/process-command', methods=['POST'])
@login_required
def process_natural_language_command():
    """Process natural language trading commands"""
    try:
        data = request.get_json()
        command = data.get('command', '').strip()
        context = data.get('context', {})
        
        if not command:
            return jsonify({
                'success': False,
                'error': 'Command is required'
            }), 400
        
        # Create OpenAI client
        client = EnhancedOpenAIClient(user_id=str(current_user.id))
        
        # Process command using asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                client.process_natural_language_command(command, context)
            )
            
            return jsonify({
                'success': True,
                'command_result': result
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error processing natural language command: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@enhanced_openai_bp.route('/api/openai/create-assistant', methods=['POST'])
@login_required
def create_trading_assistant():
    """Create a persistent trading assistant"""
    try:
        data = request.get_json()
        name = data.get('name', f'TradingAssistant_{current_user.id}')
        personality = data.get('personality', 'professional')
        
        client = EnhancedOpenAIClient(user_id=str(current_user.id))
        
        # Create assistant using asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            assistant_id = loop.run_until_complete(
                client.create_trading_assistant(name, personality)
            )
            
            return jsonify({
                'success': True,
                'assistant_id': assistant_id,
                'message': 'Trading assistant created successfully'
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error creating trading assistant: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@enhanced_openai_bp.route('/api/openai/market-analysis', methods=['POST'])
@login_required
def advanced_market_analysis():
    """Perform advanced market analysis using AI"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        analysis_type = data.get('analysis_type', 'comprehensive')
        time_horizon = data.get('time_horizon', 'medium')
        
        if not symbol:
            return jsonify({
                'success': False,
                'error': 'Symbol is required'
            }), 400
        
        client = EnhancedOpenAIClient(user_id=str(current_user.id))
        
        # Perform analysis using function call
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            analysis_args = {
                'symbol': symbol,
                'analysis_type': analysis_type,
                'time_horizon': time_horizon
            }
            
            result = loop.run_until_complete(
                client._handle_market_analysis(analysis_args)
            )
            
            return jsonify({
                'success': True,
                'symbol': symbol,
                'analysis': result
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error in advanced market analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@enhanced_openai_bp.route('/api/openai/sentiment-analysis', methods=['POST'])
@login_required
def market_sentiment_analysis():
    """Perform comprehensive sentiment analysis"""
    try:
        data = request.get_json()
        symbols = data.get('symbols', [])
        
        if not symbols:
            return jsonify({
                'success': False,
                'error': 'At least one symbol is required'
            }), 400
        
        client = EnhancedOpenAIClient(user_id=str(current_user.id))
        
        # Perform sentiment analysis using asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                client.advanced_market_sentiment_analysis(symbols)
            )
            
            return jsonify({
                'success': True,
                'sentiment_result': result
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error in sentiment analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@enhanced_openai_bp.route('/api/openai/generate-strategy', methods=['POST'])
@login_required
def generate_trading_strategy():
    """Generate AI-powered trading strategy"""
    try:
        data = request.get_json()
        strategy_type = data.get('strategy_type', 'balanced')
        risk_tolerance = data.get('risk_tolerance', 'moderate')
        time_horizon = data.get('time_horizon', 'medium')
        capital = float(data.get('capital', 10000))
        
        client = EnhancedOpenAIClient(user_id=str(current_user.id))
        
        # Generate strategy using asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                client.generate_trading_strategy(
                    strategy_type, risk_tolerance, time_horizon, capital
                )
            )
            
            return jsonify({
                'success': True,
                'strategy_result': result
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error generating trading strategy: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@enhanced_openai_bp.route('/api/openai/chat-stream', methods=['POST'])
@login_required
def streaming_chat_interface():
    """Streaming conversational trading interface"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        history = data.get('history', [])
        
        if not message:
            return jsonify({
                'success': False,
                'error': 'Message is required'
            }), 400
        
        client = EnhancedOpenAIClient(user_id=str(current_user.id))
        
        # Set up streaming response
        def generate_response():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                async def stream_chunks():
                    async for chunk in client.conversational_trading_interface(message, history):
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                
                # Run async generator in sync context
                async_gen = stream_chunks()
                while True:
                    try:
                        chunk = loop.run_until_complete(async_gen.__anext__())
                        yield chunk
                    except StopAsyncIteration:
                        break
                        
            finally:
                loop.close()
            
            yield f"data: {json.dumps({'done': True})}\n\n"
        
        return Response(
            generate_response(),
            mimetype='text/plain',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )
    
    except Exception as e:
        logger.error(f"Error in streaming chat interface: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@enhanced_openai_bp.route('/api/openai/portfolio-analysis', methods=['POST'])
@login_required
def ai_portfolio_analysis():
    """AI-powered portfolio analysis and optimization"""
    try:
        data = request.get_json()
        portfolio_data = data.get('portfolio', {})
        analysis_type = data.get('analysis_type', 'comprehensive')
        risk_tolerance = data.get('risk_tolerance', 'moderate')
        
        client = EnhancedOpenAIClient(user_id=str(current_user.id))
        
        # Perform portfolio analysis
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Create portfolio analysis prompt
            portfolio_prompt = f"""
            Analyze the following portfolio for optimization opportunities:
            
            Portfolio Holdings:
            {json.dumps(portfolio_data, indent=2)}
            
            Analysis Type: {analysis_type}
            Risk Tolerance: {risk_tolerance}
            
            Provide comprehensive analysis including:
            1. Current portfolio allocation assessment
            2. Risk exposure and diversification analysis
            3. Performance attribution and metrics
            4. Rebalancing recommendations
            5. Optimization opportunities
            6. Risk-adjusted return projections
            
            Format as detailed JSON with specific recommendations and rationale.
            """
            
            response = loop.run_until_complete(
                client.async_client.chat.completions.create(
                    model=client.models["analysis"],
                    messages=[
                        {"role": "system", "content": "You are an expert portfolio analyst with deep knowledge of modern portfolio theory and risk management."},
                        {"role": "user", "content": portfolio_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2
                )
            )
            
            portfolio_analysis = json.loads(response.choices[0].message.content)
            
            return jsonify({
                'success': True,
                'portfolio_analysis': portfolio_analysis
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error in portfolio analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@enhanced_openai_bp.route('/api/openai/risk-assessment', methods=['POST'])
@login_required
def ai_risk_assessment():
    """AI-powered risk assessment for trading decisions"""
    try:
        data = request.get_json()
        trade_details = data.get('trade_details', {})
        portfolio_context = data.get('portfolio_context', {})
        market_conditions = data.get('market_conditions', {})
        
        client = EnhancedOpenAIClient(user_id=str(current_user.id))
        
        # Perform risk assessment
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            risk_prompt = f"""
            Perform comprehensive risk assessment for the following trading scenario:
            
            Proposed Trade:
            {json.dumps(trade_details, indent=2)}
            
            Current Portfolio Context:
            {json.dumps(portfolio_context, indent=2)}
            
            Market Conditions:
            {json.dumps(market_conditions, indent=2)}
            
            Analyze:
            1. Position-specific risks (concentration, volatility, correlation)
            2. Portfolio impact and diversification effects
            3. Market timing and macroeconomic risks
            4. Liquidity and execution risks
            5. Regulatory and operational risks
            6. Scenario analysis (best/worst/expected cases)
            7. Risk mitigation strategies
            8. Position sizing recommendations
            
            Provide risk score (0-100) and detailed risk breakdown.
            Format as comprehensive JSON with quantitative metrics.
            """
            
            response = loop.run_until_complete(
                client.async_client.chat.completions.create(
                    model=client.models["analysis"],
                    messages=[
                        {"role": "system", "content": "You are an expert risk analyst specializing in trading and portfolio risk management."},
                        {"role": "user", "content": risk_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
            )
            
            risk_assessment = json.loads(response.choices[0].message.content)
            
            return jsonify({
                'success': True,
                'risk_assessment': risk_assessment
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error in risk assessment: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@enhanced_openai_bp.route('/api/openai/client-status', methods=['GET'])
@login_required
def get_openai_client_status():
    """Get OpenAI client status and capabilities"""
    try:
        client = EnhancedOpenAIClient(user_id=str(current_user.id))
        status = client.get_client_status()
        
        return jsonify({
            'success': True,
            'client_status': status
        })
    
    except Exception as e:
        logger.error(f"Error getting client status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@enhanced_openai_bp.route('/api/openai/demo-natural-language', methods=['POST'])
@login_required
def demo_natural_language_trading():
    """
    Comprehensive demo of natural language trading capabilities
    Shows various command types and AI processing
    """
    try:
        data = request.get_json()
        demo_commands = data.get('demo_commands', [
            "Buy 100 shares of Apple when it drops below $150",
            "Analyze the cryptocurrency market sentiment for Bitcoin and Ethereum",
            "What's the risk of holding too much Tesla stock in my portfolio?",
            "Generate a conservative investment strategy for $50,000",
            "Set an alert when NVIDIA hits a new 52-week high"
        ])
        
        client = EnhancedOpenAIClient(user_id=str(current_user.id))
        
        # Process multiple demo commands
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            demo_results = []
            
            for i, command in enumerate(demo_commands[:5]):  # Limit to 5 commands
                try:
                    result = loop.run_until_complete(
                        client.process_natural_language_command(command)
                    )
                    
                    demo_results.append({
                        'command_number': i + 1,
                        'original_command': command,
                        'processing_result': result,
                        'command_type': 'natural_language_processing'
                    })
                    
                except Exception as cmd_error:
                    demo_results.append({
                        'command_number': i + 1,
                        'original_command': command,
                        'error': str(cmd_error)
                    })
            
            return jsonify({
                'success': True,
                'message': 'Natural language trading demo completed',
                'demo_results': demo_results,
                'commands_processed': len(demo_results)
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error in natural language demo: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500