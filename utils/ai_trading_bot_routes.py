"""
AI Trading Bot Routes for Arbion Trading Platform
Flask endpoints for managing and controlling the AI-powered trading bot
"""

from flask import Blueprint, request, jsonify, session
from flask_login import login_required, current_user
import logging
import asyncio
from datetime import datetime, timedelta
from utils.ai_trading_bot import create_ai_trading_bot, get_ai_trading_bot_info

logger = logging.getLogger(__name__)

# Create blueprint for AI Trading Bot routes
ai_trading_bot_bp = Blueprint('ai_trading_bot', __name__)

# Store active bot instances per user
active_bots = {}

@ai_trading_bot_bp.route('/api/ai-trading-bot/info', methods=['GET'])
@login_required
def get_ai_trading_bot_information():
    """Get information about AI trading bot capabilities"""
    try:
        info = get_ai_trading_bot_info()
        return jsonify({
            'success': True,
            'ai_trading_bot_info': info
        })
    
    except Exception as e:
        logger.error(f"Error getting AI trading bot info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_trading_bot_bp.route('/api/ai-trading-bot/config', methods=['GET', 'POST'])
@login_required
def manage_bot_config():
    """Get or update AI trading bot configuration"""
    try:
        if request.method == 'GET':
            # Return default or user's current configuration
            bot = active_bots.get(str(current_user.id))
            if bot:
                config = bot.config
            else:
                # Return default config
                temp_bot = create_ai_trading_bot(str(current_user.id))
                config = temp_bot.config
            
            return jsonify({
                'success': True,
                'config': config
            })
        
        elif request.method == 'POST':
            # Update configuration
            data = request.get_json()
            new_config = data.get('config', {})
            
            # Validate configuration
            validation_result = _validate_bot_config(new_config)
            if not validation_result['valid']:
                return jsonify({
                    'success': False,
                    'error': 'Invalid configuration',
                    'validation_errors': validation_result['errors']
                }), 400
            
            # Update bot configuration
            user_id = str(current_user.id)
            if user_id in active_bots:
                # Update existing bot
                active_bots[user_id].config.update(new_config)
                message = 'Configuration updated for active bot'
            else:
                # Configuration will be used when bot is created
                message = 'Configuration saved for future bot creation'
            
            return jsonify({
                'success': True,
                'message': message,
                'config': new_config
            })
    
    except Exception as e:
        logger.error(f"Error managing bot config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_trading_bot_bp.route('/api/ai-trading-bot/start', methods=['POST'])
@login_required
def start_ai_trading_bot():
    """Start the AI trading bot"""
    try:
        user_id = str(current_user.id)
        
        # Check if bot is already running
        if user_id in active_bots and active_bots[user_id].is_running:
            return jsonify({
                'success': False,
                'error': 'Trading bot is already running'
            }), 400
        
        # Get configuration from request or use defaults
        data = request.get_json() or {}
        config = data.get('config', {})
        
        # Create or update bot instance
        if user_id not in active_bots:
            active_bots[user_id] = create_ai_trading_bot(user_id, config)
        else:
            # Update existing bot config
            active_bots[user_id].config.update(config)
        
        # Start the bot
        bot = active_bots[user_id]
        
        # Run async start method
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            start_result = loop.run_until_complete(bot.start_trading_bot())
        finally:
            loop.close()
        
        return jsonify(start_result)
    
    except Exception as e:
        logger.error(f"Error starting AI trading bot: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_trading_bot_bp.route('/api/ai-trading-bot/stop', methods=['POST'])
@login_required
def stop_ai_trading_bot():
    """Stop the AI trading bot"""
    try:
        user_id = str(current_user.id)
        
        if user_id not in active_bots:
            return jsonify({
                'success': False,
                'error': 'No active trading bot found'
            }), 404
        
        bot = active_bots[user_id]
        stop_result = bot.stop_trading_bot()
        
        return jsonify(stop_result)
    
    except Exception as e:
        logger.error(f"Error stopping AI trading bot: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_trading_bot_bp.route('/api/ai-trading-bot/status', methods=['GET'])
@login_required
def get_bot_status():
    """Get current AI trading bot status"""
    try:
        user_id = str(current_user.id)
        
        if user_id not in active_bots:
            return jsonify({
                'success': True,
                'bot_exists': False,
                'is_running': False
            })
        
        bot = active_bots[user_id]
        status = bot.get_bot_status()
        
        return jsonify({
            'success': True,
            'bot_exists': True,
            'status': status
        })
    
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_trading_bot_bp.route('/api/ai-trading-bot/analyze/<symbol>', methods=['POST'])
@login_required
def analyze_symbol_with_ai():
    """Run AI analysis on a specific symbol"""
    try:
        user_id = str(current_user.id)
        symbol = request.view_args['symbol'].upper()
        
        # Create temporary bot if none exists
        if user_id not in active_bots:
            active_bots[user_id] = create_ai_trading_bot(user_id)
        
        bot = active_bots[user_id]
        
        # Initialize multi-broker connections if needed
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            init_result = loop.run_until_complete(bot.initialize_connections())
            if not init_result.get('success'):
                return jsonify({
                    'success': False,
                    'error': 'Failed to initialize multi-broker connections',
                    'details': init_result
                }), 500
            
            # Run AI analysis
            analysis = loop.run_until_complete(bot.analyze_market_with_ai(symbol))
            
            return jsonify({
                'success': True,
                'symbol': symbol,
                'analysis': {
                    'symbol': analysis.symbol,
                    'current_price': analysis.current_price,
                    'trend_direction': analysis.trend_direction,
                    'sentiment_score': analysis.sentiment_score,
                    'technical_indicators': analysis.technical_indicators,
                    'fundamental_analysis': analysis.fundamental_analysis,
                    'ai_recommendation': analysis.ai_recommendation,
                    'confidence_level': analysis.confidence_level,
                    'timestamp': analysis.timestamp.isoformat()
                }
            })
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error analyzing symbol {symbol}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_trading_bot_bp.route('/api/ai-trading-bot/signal/<symbol>', methods=['POST'])
@login_required
def generate_trading_signal():
    """Generate trading signal for a specific symbol"""
    try:
        user_id = str(current_user.id)
        symbol = request.view_args['symbol'].upper()
        
        # Create temporary bot if none exists
        if user_id not in active_bots:
            active_bots[user_id] = create_ai_trading_bot(user_id)
        
        bot = active_bots[user_id]
        
        # Initialize connections and generate signal
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            init_result = loop.run_until_complete(bot.initialize_connections())
            if not init_result.get('success'):
                return jsonify({
                    'success': False,
                    'error': 'Failed to initialize bot connections'
                }), 500
            
            # Generate trading signal
            signal = loop.run_until_complete(bot.generate_trading_signal(symbol))
            
            # Validate signal
            validation = bot.validate_trading_signal(signal)
            
            return jsonify({
                'success': True,
                'symbol': symbol,
                'signal': {
                    'symbol': signal.symbol,
                    'action': signal.action,
                    'confidence': signal.confidence,
                    'quantity': signal.quantity,
                    'price_target': signal.price_target,
                    'stop_loss': signal.stop_loss,
                    'reasoning': signal.reasoning,
                    'risk_level': signal.risk_level,
                    'time_horizon': signal.time_horizon,
                    'timestamp': signal.timestamp.isoformat()
                },
                'validation': validation
            })
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error generating signal for {symbol}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_trading_bot_bp.route('/api/ai-trading-bot/execute/<symbol>', methods=['POST'])
@login_required
def execute_trading_signal_for_symbol():
    """Execute trading signal for a specific symbol"""
    try:
        user_id = str(current_user.id)
        symbol = request.view_args['symbol'].upper()
        
        if user_id not in active_bots:
            return jsonify({
                'success': False,
                'error': 'No active trading bot found'
            }), 404
        
        bot = active_bots[user_id]
        
        # Generate and execute signal
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Generate signal
            signal = loop.run_until_complete(bot.generate_trading_signal(symbol))
            
            # Execute signal
            execution_result = loop.run_until_complete(bot.execute_trading_signal(signal))
            
            return jsonify({
                'success': True,
                'symbol': symbol,
                'signal_executed': signal.action,
                'execution_result': execution_result
            })
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error executing signal for {symbol}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_trading_bot_bp.route('/api/ai-trading-bot/cycle', methods=['POST'])
@login_required
def run_trading_cycle():
    """Run one complete trading cycle"""
    try:
        user_id = str(current_user.id)
        
        if user_id not in active_bots:
            return jsonify({
                'success': False,
                'error': 'No active trading bot found'
            }), 404
        
        bot = active_bots[user_id]
        
        # Run trading cycle
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            cycle_result = loop.run_until_complete(bot.run_trading_cycle())
            
            return jsonify({
                'success': True,
                'cycle_result': cycle_result
            })
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error running trading cycle: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_trading_bot_bp.route('/api/ai-trading-bot/performance', methods=['GET'])
@login_required
def get_trading_performance():
    """Get trading performance metrics"""
    try:
        user_id = str(current_user.id)
        
        if user_id not in active_bots:
            return jsonify({
                'success': True,
                'performance': {
                    'total_trades': 0,
                    'paper_trades': 0,
                    'real_trades': 0,
                    'trades_today': 0,
                    'daily_pnl': 0.0
                }
            })
        
        bot = active_bots[user_id]
        performance = bot.get_trading_performance()
        
        return jsonify({
            'success': True,
            'performance': performance
        })
    
    except Exception as e:
        logger.error(f"Error getting trading performance: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_trading_bot_bp.route('/api/ai-trading-bot/history', methods=['GET'])
@login_required
def get_trading_history():
    """Get trading history"""
    try:
        user_id = str(current_user.id)
        
        if user_id not in active_bots:
            return jsonify({
                'success': True,
                'trading_history': [],
                'analysis_history': []
            })
        
        bot = active_bots[user_id]
        
        # Get optional filters
        limit = request.args.get('limit', 50, type=int)
        include_analysis = request.args.get('include_analysis', 'false').lower() == 'true'
        
        # Get recent trading history
        trading_history = bot.trading_history[-limit:] if bot.trading_history else []
        
        response_data = {
            'success': True,
            'trading_history': trading_history,
            'total_trades': len(bot.trading_history)
        }
        
        if include_analysis:
            analysis_history = bot.market_analysis_history[-limit:] if bot.market_analysis_history else []
            # Convert analysis objects to dicts for JSON serialization
            analysis_dicts = []
            for analysis in analysis_history:
                analysis_dicts.append({
                    'symbol': analysis.symbol,
                    'current_price': analysis.current_price,
                    'trend_direction': analysis.trend_direction,
                    'sentiment_score': analysis.sentiment_score,
                    'technical_indicators': analysis.technical_indicators,
                    'fundamental_analysis': analysis.fundamental_analysis,
                    'ai_recommendation': analysis.ai_recommendation,
                    'confidence_level': analysis.confidence_level,
                    'timestamp': analysis.timestamp.isoformat()
                })
            
            response_data['analysis_history'] = analysis_dicts
            response_data['total_analyses'] = len(bot.market_analysis_history)
        
        return jsonify(response_data)
    
    except Exception as e:
        logger.error(f"Error getting trading history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_trading_bot_bp.route('/api/ai-trading-bot/accounts', methods=['GET'])
@login_required
def get_connected_accounts():
    """Get all connected broker accounts"""
    try:
        user_id = str(current_user.id)
        
        # Create temporary bot to check connections
        bot = create_ai_trading_bot(user_id)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            init_result = loop.run_until_complete(bot.initialize_connections())
            
            return jsonify({
                'success': True,
                'connected_accounts': init_result.get('connected_accounts', {}),
                'total_accounts': init_result.get('total_accounts', 0),
                'broker_connections': init_result.get('broker_connections', {})
            })
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error getting connected accounts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ai_trading_bot_bp.route('/api/ai-trading-bot/demo', methods=['POST'])
@login_required
def demo_ai_trading_bot():
    """Comprehensive demo of multi-account AI trading bot capabilities"""
    try:
        user_id = str(current_user.id)
        demo_symbol = request.get_json().get('symbol', 'AAPL')
        
        # Create demo bot with multi-account support
        demo_bot = create_ai_trading_bot(user_id, {'paper_trading': True})
        
        demo_results = []
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Test 1: Initialize multi-broker connections
            init_result = loop.run_until_complete(demo_bot.initialize_connections())
            demo_results.append({
                'test': 'multi_broker_connection_initialization',
                'result': {
                    'success': init_result.get('success'),
                    'total_accounts': init_result.get('total_accounts', 0),
                    'broker_connections': init_result.get('broker_connections', {}),
                    'connected_accounts': init_result.get('connected_accounts', {})
                }
            })
            
            if init_result.get('success'):
                # Test 2: Market analysis
                analysis = loop.run_until_complete(demo_bot.analyze_market_with_ai(demo_symbol))
                demo_results.append({
                    'test': 'market_analysis',
                    'symbol': demo_symbol,
                    'result': {
                        'trend_direction': analysis.trend_direction,
                        'sentiment_score': analysis.sentiment_score,
                        'confidence_level': analysis.confidence_level,
                        'has_recommendation': bool(analysis.ai_recommendation)
                    }
                })
                
                # Test 3: Trading signal generation
                signal = loop.run_until_complete(demo_bot.generate_trading_signal(demo_symbol))
                demo_results.append({
                    'test': 'signal_generation',
                    'symbol': demo_symbol,
                    'result': {
                        'action': signal.action,
                        'confidence': signal.confidence,
                        'risk_level': signal.risk_level,
                        'has_reasoning': bool(signal.reasoning)
                    }
                })
                
                # Test 4: Paper trade execution
                if signal.action in ['BUY', 'SELL']:
                    execution_result = loop.run_until_complete(demo_bot.execute_trading_signal(signal))
                    demo_results.append({
                        'test': 'paper_trade_execution',
                        'result': {
                            'success': execution_result.get('success'),
                            'paper_trade': execution_result.get('paper_trade', True)
                        }
                    })
            
        finally:
            loop.close()
        
        return jsonify({
            'success': True,
            'message': 'AI Trading Bot demo completed',
            'demo_results': demo_results,
            'tests_completed': len(demo_results)
        })
    
    except Exception as e:
        logger.error(f"Error in AI trading bot demo: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def _validate_bot_config(config: dict) -> dict:
    """Validate bot configuration"""
    validation_result = {
        'valid': True,
        'errors': []
    }
    
    # Check required fields and ranges
    if 'max_position_size' in config:
        if not isinstance(config['max_position_size'], (int, float)) or config['max_position_size'] <= 0:
            validation_result['valid'] = False
            validation_result['errors'].append('max_position_size must be a positive number')
    
    if 'confidence_threshold' in config:
        if not isinstance(config['confidence_threshold'], (int, float)) or not (0 <= config['confidence_threshold'] <= 1):
            validation_result['valid'] = False
            validation_result['errors'].append('confidence_threshold must be between 0 and 1')
    
    if 'max_daily_trades' in config:
        if not isinstance(config['max_daily_trades'], int) or config['max_daily_trades'] < 0:
            validation_result['valid'] = False
            validation_result['errors'].append('max_daily_trades must be a non-negative integer')
    
    if 'allowed_symbols' in config:
        if not isinstance(config['allowed_symbols'], list):
            validation_result['valid'] = False
            validation_result['errors'].append('allowed_symbols must be a list')
    
    return validation_result