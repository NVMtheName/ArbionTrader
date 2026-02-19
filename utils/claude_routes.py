"""
Claude API Routes for Arbion Trading Platform
Flask endpoints for Claude-powered AI trading capabilities and natural language processing.
"""

from flask import Blueprint, request, jsonify, Response
from flask_login import login_required, current_user
import asyncio
import json
import logging

from utils.comprehensive_claude_client import (
    ComprehensiveClaudeClient,
    create_comprehensive_claude_client,
    get_claude_enhancement_info
)

logger = logging.getLogger(__name__)

# Create blueprint for Claude routes
claude_bp = Blueprint('claude', __name__)


@claude_bp.route('/api/claude/info', methods=['GET'])
@login_required
def get_claude_info():
    """Get information about Claude API capabilities"""
    try:
        info = get_claude_enhancement_info()
        return jsonify({
            'success': True,
            'claude_info': info
        })
    except Exception as e:
        logger.error(f"Error getting Claude info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@claude_bp.route('/api/claude/test-connection', methods=['POST'])
@login_required
def test_claude_connection():
    """Test Claude API connection"""
    try:
        client = create_comprehensive_claude_client(
            user_id=str(current_user.id)
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(client.test_connection())
            return jsonify({
                'success': result.get('success', False),
                'message': result.get('message', 'Connection test completed'),
                'details': result
            })
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Claude connection test failed: {e}")
        return jsonify({
            'success': False,
            'message': f'Connection test failed: {str(e)}'
        }), 500


@claude_bp.route('/api/claude/process-command', methods=['POST'])
@login_required
def process_claude_trading_command():
    """Process natural language trading commands via Claude"""
    try:
        data = request.get_json()
        command = data.get('command', '').strip()

        if not command:
            return jsonify({
                'success': False,
                'error': 'Command is required'
            }), 400

        client = ComprehensiveClaudeClient(
            user_id=str(current_user.id)
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                client.process_trading_command(command)
            )
            return jsonify({
                'success': True,
                'command_result': result
            })
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Error processing Claude trading command: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@claude_bp.route('/api/claude/market-analysis', methods=['POST'])
@login_required
def claude_market_analysis():
    """Perform market analysis using Claude"""
    try:
        data = request.get_json()
        symbols = data.get('symbols', [])

        if not symbols:
            # Support single symbol input too
            symbol = data.get('symbol')
            if symbol:
                symbols = [symbol]
            else:
                return jsonify({
                    'success': False,
                    'error': 'At least one symbol is required'
                }), 400

        client = ComprehensiveClaudeClient(
            user_id=str(current_user.id)
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            insights = loop.run_until_complete(
                client.generate_market_insights(symbols)
            )
            return jsonify({
                'success': True,
                'insights': insights,
                'provider': 'claude'
            })
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Error in Claude market analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@claude_bp.route('/api/claude/portfolio-analysis', methods=['POST'])
@login_required
def claude_portfolio_analysis():
    """AI-powered portfolio analysis via Claude"""
    try:
        data = request.get_json()
        positions = data.get('positions', [])
        target_allocation = data.get('target_allocation')

        client = ComprehensiveClaudeClient(
            user_id=str(current_user.id)
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                client.optimize_portfolio(positions, target_allocation)
            )
            return jsonify(result)
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Error in Claude portfolio analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@claude_bp.route('/api/claude/chat-stream', methods=['POST'])
@login_required
def claude_streaming_chat():
    """Streaming conversational trading interface via Claude"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        history = data.get('history', [])

        if not message:
            return jsonify({
                'success': False,
                'error': 'Message is required'
            }), 400

        client = ComprehensiveClaudeClient(
            user_id=str(current_user.id)
        )

        def generate_response():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Build messages from history
                messages = []
                for msg in history:
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
                messages.append({"role": "user", "content": message})

                # Use Claude streaming
                stream = loop.run_until_complete(
                    client.async_client.messages.create(
                        model=client.models["primary"],
                        max_tokens=4096,
                        system="""You are an expert AI trading assistant for the Arbion platform.
Analyze market data, provide trading insights, and help with portfolio management.
Be concise, data-driven, and always consider risk management in your recommendations.""",
                        messages=messages,
                        stream=True
                    )
                )

                # Process streaming events
                with stream as s:
                    for event in s:
                        if hasattr(event, 'type'):
                            if event.type == 'content_block_delta':
                                if hasattr(event.delta, 'text'):
                                    yield f"data: {json.dumps({'chunk': event.delta.text})}\n\n"

            except Exception as stream_err:
                logger.error(f"Claude streaming error: {stream_err}")
                yield f"data: {json.dumps({'error': str(stream_err)})}\n\n"
            finally:
                loop.close()

            yield f"data: {json.dumps({'done': True})}\n\n"

        return Response(
            generate_response(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )

    except Exception as e:
        logger.error(f"Error in Claude streaming chat: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@claude_bp.route('/api/claude/generate-strategy', methods=['POST'])
@login_required
def claude_generate_strategy():
    """Generate AI-powered trading strategy via Claude"""
    try:
        data = request.get_json()
        strategy_type = data.get('strategy_type', 'balanced')
        risk_tolerance = data.get('risk_tolerance', 'moderate')
        time_horizon = data.get('time_horizon', 'medium')
        capital = float(data.get('capital', 10000))

        client = ComprehensiveClaudeClient(
            user_id=str(current_user.id)
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            prompt = f"""Generate a trading strategy with these parameters:
Strategy Type: {strategy_type}
Risk Tolerance: {risk_tolerance}
Time Horizon: {time_horizon}
Capital: ${capital:,.2f}

Return a JSON object with:
{{
    "name": "strategy name",
    "description": "brief description",
    "entry_conditions": ["condition1", "condition2"],
    "exit_conditions": ["condition1", "condition2"],
    "risk_management": {{
        "stop_loss_pct": 0.0,
        "take_profit_pct": 0.0,
        "max_position_size_pct": 0.0
    }},
    "expected_return": 0.0,
    "risk_level": "low|medium|high",
    "confidence": 0.0-1.0,
    "recommended_symbols": ["SYM1", "SYM2"]
}}"""

            response = loop.run_until_complete(
                client.create_message(
                    messages=[{"role": "user", "content": prompt}],
                    system="You are an expert trading strategist. Respond only with valid JSON.",
                    model=client.models["analysis"],
                    temperature=0.2
                )
            )

            text_content = ""
            for block in response.content:
                if block.type == "text":
                    text_content = block.text
                    break

            try:
                strategy_data = json.loads(text_content)
                return jsonify({
                    'success': True,
                    'strategy_result': strategy_data,
                    'provider': 'claude'
                })
            except json.JSONDecodeError:
                return jsonify({
                    'success': True,
                    'strategy_result': {'raw_response': text_content},
                    'provider': 'claude'
                })

        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Error generating Claude trading strategy: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@claude_bp.route('/api/claude/client-status', methods=['GET'])
@login_required
def get_claude_client_status():
    """Get Claude client status and capabilities"""
    try:
        client = ComprehensiveClaudeClient(
            user_id=str(current_user.id)
        )
        return jsonify({
            'success': True,
            'client_status': {
                'models': client.models,
                'tools_count': len(client.trading_tools),
                'provider': 'anthropic',
                'connected': True
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'client_status': {
                'provider': 'anthropic',
                'connected': False
            }
        }), 500
