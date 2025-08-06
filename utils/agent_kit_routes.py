"""
Agent Kit Flask Routes
REST API endpoints for Coinbase Agent Kit functionality in Arbion platform
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import asyncio
import logging
from utils.coinbase_agent_kit import CoinbaseAgentKit, create_trading_agent, get_agent_kit_info

logger = logging.getLogger(__name__)

# Create blueprint for agent kit routes
agent_kit_bp = Blueprint('agent_kit', __name__)

@agent_kit_bp.route('/api/agent-kit/info', methods=['GET'])
@login_required
def get_agent_kit_information():
    """Get information about Agent Kit capabilities"""
    try:
        info = get_agent_kit_info()
        return jsonify({
            'success': True,
            'agent_kit_info': info
        })
    
    except Exception as e:
        logger.error(f"Error getting agent kit info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@agent_kit_bp.route('/api/agent-kit/create-agent', methods=['POST'])
@login_required
def create_autonomous_agent():
    """Create a new autonomous trading agent"""
    try:
        data = request.get_json()
        
        agent_config = {
            'name': data.get('name', f'Agent_{current_user.id}'),
            'type': data.get('type', 'general_trader'),
            'networks': data.get('networks', ['base-sepolia']),
            'risk_tolerance': data.get('risk_tolerance', 'medium'),
            'focus_markets': data.get('focus_markets', ['crypto']),
            'trading_style': data.get('trading_style', 'swing')
        }
        
        # Create agent using asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            agent = loop.run_until_complete(
                create_trading_agent(str(current_user.id), agent_config)
            )
            
            # Create custom agent profile
            agent_profile = loop.run_until_complete(
                agent.create_custom_trading_agent(agent_config)
            )
            
            return jsonify({
                'success': True,
                'message': 'Autonomous trading agent created successfully',
                'agent_profile': agent_profile.get('agent_profile'),
                'agent_status': agent.get_agent_status()
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error creating autonomous agent: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@agent_kit_bp.route('/api/agent-kit/initialize-wallets', methods=['POST'])
@login_required
def initialize_agent_wallets():
    """Initialize wallets for autonomous agent"""
    try:
        data = request.get_json()
        networks = data.get('networks', ['base-sepolia'])
        
        agent = CoinbaseAgentKit(user_id=str(current_user.id))
        
        # Initialize wallets using asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            wallet_addresses = loop.run_until_complete(
                agent.initialize_agent_wallets(networks)
            )
            
            return jsonify({
                'success': True,
                'message': 'Agent wallets initialized successfully',
                'wallet_addresses': wallet_addresses,
                'networks': list(wallet_addresses.keys())
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error initializing agent wallets: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@agent_kit_bp.route('/api/agent-kit/analyze-market', methods=['POST'])
@login_required
def analyze_market_with_ai():
    """Use AI to analyze market conditions for autonomous trading"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        action_type = data.get('action_type', 'trade_analysis')
        
        if not symbol:
            return jsonify({
                'success': False,
                'error': 'Symbol is required'
            }), 400
        
        agent = CoinbaseAgentKit(user_id=str(current_user.id))
        
        # Perform AI analysis using asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            analysis_result = loop.run_until_complete(
                agent.analyze_market_with_ai(symbol, action_type)
            )
            
            if analysis_result.get('error'):
                return jsonify({
                    'success': False,
                    'error': analysis_result['error']
                }), 500
            
            return jsonify({
                'success': True,
                'symbol': symbol,
                'analysis': analysis_result
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error in AI market analysis: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@agent_kit_bp.route('/api/agent-kit/execute-autonomous-trade', methods=['POST'])
@login_required
def execute_autonomous_trade():
    """Execute trades autonomously based on AI analysis"""
    try:
        data = request.get_json()
        analysis = data.get('analysis')
        network = data.get('network', 'base-sepolia')
        
        if not analysis:
            return jsonify({
                'success': False,
                'error': 'Analysis data is required'
            }), 400
        
        agent = CoinbaseAgentKit(user_id=str(current_user.id))
        
        # Execute autonomous trade using asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Initialize wallets if needed
            if not agent.agent_wallet_addresses:
                await_result = loop.run_until_complete(
                    agent.initialize_agent_wallets([network])
                )
            
            trade_result = loop.run_until_complete(
                agent.execute_autonomous_trade(analysis, network)
            )
            
            return jsonify({
                'success': True,
                'trade_result': trade_result,
                'network': network
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error executing autonomous trade: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@agent_kit_bp.route('/api/agent-kit/batch-portfolio-operations', methods=['POST'])
@login_required
def batch_portfolio_operations():
    """Execute multiple portfolio operations in a single batch transaction"""
    try:
        data = request.get_json()
        operations = data.get('operations', [])
        network = data.get('network', 'base-sepolia')
        
        if not operations:
            return jsonify({
                'success': False,
                'error': 'Operations list is required'
            }), 400
        
        agent = CoinbaseAgentKit(user_id=str(current_user.id))
        
        # Execute batch operations using asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Initialize wallets if needed
            if not agent.agent_wallet_addresses:
                loop.run_until_complete(
                    agent.initialize_agent_wallets([network])
                )
            
            batch_result = loop.run_until_complete(
                agent.batch_portfolio_operations(operations, network)
            )
            
            return jsonify({
                'success': True,
                'batch_result': batch_result
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error in batch portfolio operations: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@agent_kit_bp.route('/api/agent-kit/run-strategy', methods=['POST'])
@login_required
def run_autonomous_strategy():
    """Run autonomous trading strategy with continuous monitoring"""
    try:
        data = request.get_json()
        
        strategy_config = {
            'name': data.get('name', 'DefaultStrategy'),
            'symbols': data.get('symbols', ['BTC-USD', 'ETH-USD']),
            'check_interval': data.get('check_interval', 300),
            'max_trades_per_hour': data.get('max_trades_per_hour', 4),
            'risk_tolerance': data.get('risk_tolerance', 'medium'),
            'strategy_type': data.get('strategy_type', 'trend_following')
        }
        
        agent = CoinbaseAgentKit(user_id=str(current_user.id))
        
        # Run strategy using asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Initialize wallets if needed
            if not agent.agent_wallet_addresses:
                loop.run_until_complete(
                    agent.initialize_agent_wallets(['base-sepolia'])
                )
            
            strategy_results = loop.run_until_complete(
                agent.monitor_and_execute_strategy(strategy_config)
            )
            
            return jsonify({
                'success': True,
                'strategy_results': strategy_results
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error running autonomous strategy: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@agent_kit_bp.route('/api/agent-kit/agent-status', methods=['GET'])
@login_required
def get_agent_status():
    """Get current status and capabilities of the user's agent"""
    try:
        agent = CoinbaseAgentKit(user_id=str(current_user.id))
        status = agent.get_agent_status()
        
        return jsonify({
            'success': True,
            'agent_status': status
        })
    
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@agent_kit_bp.route('/api/agent-kit/demo-full-workflow', methods=['POST'])
@login_required
def demo_full_agent_workflow():
    """
    Comprehensive demo of Agent Kit capabilities
    Creates agent, analyzes market, and executes autonomous trades
    """
    try:
        data = request.get_json()
        demo_symbol = data.get('symbol', 'ETH-USD')
        demo_network = data.get('network', 'base-sepolia')
        
        agent = CoinbaseAgentKit(
            user_id=str(current_user.id),
            agent_name="DemoTradingAgent"
        )
        
        # Run full workflow using asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            workflow_results = {
                'step_1_wallet_initialization': None,
                'step_2_ai_analysis': None,
                'step_3_autonomous_trade': None,
                'step_4_agent_status': None
            }
            
            # Step 1: Initialize agent wallets
            wallet_result = loop.run_until_complete(
                agent.initialize_agent_wallets([demo_network])
            )
            workflow_results['step_1_wallet_initialization'] = {
                'success': bool(wallet_result),
                'wallets_created': len(wallet_result),
                'networks': list(wallet_result.keys())
            }
            
            # Step 2: AI market analysis
            analysis_result = loop.run_until_complete(
                agent.analyze_market_with_ai(demo_symbol)
            )
            workflow_results['step_2_ai_analysis'] = analysis_result
            
            # Step 3: Execute autonomous trade (if analysis is positive)
            if not analysis_result.get('error') and analysis_result.get('confidence', 0) > 0.5:
                trade_result = loop.run_until_complete(
                    agent.execute_autonomous_trade(analysis_result, demo_network)
                )
                workflow_results['step_3_autonomous_trade'] = trade_result
            else:
                workflow_results['step_3_autonomous_trade'] = {
                    'action': 'skipped',
                    'reason': 'Low confidence or analysis error'
                }
            
            # Step 4: Get final agent status
            workflow_results['step_4_agent_status'] = agent.get_agent_status()
            
            return jsonify({
                'success': True,
                'message': 'Agent Kit demo workflow completed successfully',
                'demo_results': workflow_results,
                'symbol_analyzed': demo_symbol,
                'network_used': demo_network
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error in agent workflow demo: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500