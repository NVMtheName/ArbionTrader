"""
OpenAI Authentication Routes for Arbion Trading Platform
Flask endpoints for managing OpenAI authentication, connection testing, and monitoring
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import asyncio
import logging
from utils.openai_auth_manager import (
    create_auth_manager, 
    test_openai_connection, 
    validate_openai_setup
)

logger = logging.getLogger(__name__)

# Create blueprint for OpenAI authentication routes
openai_auth_bp = Blueprint('openai_auth', __name__)

@openai_auth_bp.route('/api/openai/auth/test', methods=['POST'])
@login_required
def test_openai_auth():
    """Test OpenAI authentication and connection"""
    try:
        user_id = str(current_user.id)
        
        # Run async test in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(test_openai_connection(user_id))
            
            return jsonify({
                'success': True,
                'test_result': result
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error testing OpenAI authentication: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@openai_auth_bp.route('/api/openai/auth/status', methods=['GET'])
@login_required
def get_openai_auth_status():
    """Get comprehensive OpenAI authentication status"""
    try:
        user_id = str(current_user.id)
        auth_manager = create_auth_manager(user_id)
        
        status_info = auth_manager.get_connection_info()
        
        return jsonify({
            'success': True,
            'auth_status': status_info
        })
    
    except Exception as e:
        logger.error(f"Error getting OpenAI auth status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@openai_auth_bp.route('/api/openai/auth/refresh', methods=['POST'])
@login_required
def refresh_openai_connection():
    """Refresh OpenAI connection and authentication"""
    try:
        user_id = str(current_user.id)
        auth_manager = create_auth_manager(user_id)
        
        # Run async refresh in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(auth_manager.refresh_connection())
            
            return jsonify({
                'success': True,
                'refresh_result': result
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error refreshing OpenAI connection: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@openai_auth_bp.route('/api/openai/auth/validate', methods=['GET'])
def validate_openai_configuration():
    """Validate OpenAI setup and configuration (no auth required for setup validation)"""
    try:
        validation_result = validate_openai_setup()
        
        return jsonify({
            'success': True,
            'validation': validation_result
        })
    
    except Exception as e:
        logger.error(f"Error validating OpenAI setup: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@openai_auth_bp.route('/api/openai/auth/health', methods=['GET'])
@login_required
def check_openai_health():
    """Check OpenAI service health and connection"""
    try:
        user_id = str(current_user.id)
        auth_manager = create_auth_manager(user_id)
        
        # Run async health check
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Ensure connection is healthy
            is_healthy = loop.run_until_complete(auth_manager.ensure_connection())
            
            health_info = {
                'healthy': is_healthy,
                'connection_info': auth_manager.get_connection_info(),
                'last_check': auth_manager.last_health_check.isoformat() if auth_manager.last_health_check else None
            }
            
            return jsonify({
                'success': True,
                'health': health_info
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error checking OpenAI health: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@openai_auth_bp.route('/api/openai/auth/rate-limits', methods=['GET'])
@login_required
def get_openai_rate_limits():
    """Get current OpenAI rate limit status"""
    try:
        user_id = str(current_user.id)
        auth_manager = create_auth_manager(user_id)
        
        rate_limit_info = {
            'can_make_request': auth_manager.rate_limit_manager.can_make_request(),
            'wait_time': auth_manager.rate_limit_manager.get_wait_time(),
            'current_usage': auth_manager.rate_limit_manager.current_usage,
            'rate_limits': auth_manager.rate_limit_manager.rate_limits,
            'recent_requests': len(auth_manager.rate_limit_manager.request_times)
        }
        
        return jsonify({
            'success': True,
            'rate_limits': rate_limit_info
        })
    
    except Exception as e:
        logger.error(f"Error getting rate limit info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@openai_auth_bp.route('/api/openai/auth/validate-key', methods=['POST'])
def validate_api_key_format():
    """Validate OpenAI API key format (for setup assistance)"""
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()
        
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API key is required'
            }), 400
        
        auth_manager = create_auth_manager()
        validation_result = auth_manager.validate_api_key_format(api_key)
        
        return jsonify({
            'success': True,
            'validation': validation_result
        })
    
    except Exception as e:
        logger.error(f"Error validating API key format: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@openai_auth_bp.route('/api/openai/auth/setup-guide', methods=['GET'])
def get_openai_setup_guide():
    """Get OpenAI setup guide and troubleshooting information"""
    try:
        setup_guide = {
            'steps': [
                {
                    'step': 1,
                    'title': 'Get OpenAI API Key',
                    'description': 'Visit https://platform.openai.com/api-keys to create an API key',
                    'details': [
                        'Sign up for OpenAI account if needed',
                        'Navigate to API Keys section',
                        'Click "Create new secret key"',
                        'Copy the generated key (starts with sk-)'
                    ]
                },
                {
                    'step': 2,
                    'title': 'Set Environment Variable',
                    'description': 'Add your API key to environment variables',
                    'details': [
                        'Set OPENAI_API_KEY=your_api_key_here',
                        'Restart your application after setting the variable',
                        'Verify the key is accessible in your environment'
                    ]
                },
                {
                    'step': 3,
                    'title': 'Test Connection',
                    'description': 'Use the test endpoint to verify your setup',
                    'details': [
                        'Call /api/openai/auth/test to test connection',
                        'Check for any authentication errors',
                        'Verify rate limits and usage quotas'
                    ]
                }
            ],
            'troubleshooting': {
                'authentication_failed': {
                    'issue': 'Invalid API key or authentication error',
                    'solutions': [
                        'Verify API key is correct and active',
                        'Check if key has necessary permissions',
                        'Ensure key is not expired or revoked',
                        'Try regenerating the API key'
                    ]
                },
                'rate_limit_exceeded': {
                    'issue': 'Too many requests in short period',
                    'solutions': [
                        'Wait before making more requests',
                        'Implement request spacing in your application',
                        'Consider upgrading your OpenAI plan',
                        'Use rate limiting features in the client'
                    ]
                },
                'connection_failed': {
                    'issue': 'Network or connectivity problems',
                    'solutions': [
                        'Check your internet connection',
                        'Verify firewall settings allow HTTPS to api.openai.com',
                        'Try again after a few minutes',
                        'Check OpenAI service status'
                    ]
                }
            },
            'best_practices': [
                'Keep your API key secure and never expose it in client-side code',
                'Monitor your usage to avoid unexpected charges',
                'Implement proper error handling and retry logic',
                'Use environment variables for configuration',
                'Set up rate limiting to respect API quotas',
                'Test thoroughly in development before production use'
            ]
        }
        
        return jsonify({
            'success': True,
            'setup_guide': setup_guide
        })
    
    except Exception as e:
        logger.error(f"Error getting setup guide: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@openai_auth_bp.route('/api/openai/auth/demo-connection', methods=['POST'])
@login_required
def demo_openai_connection():
    """
    Comprehensive demo of OpenAI authentication and connection features
    Shows connection testing, rate limiting, and error handling
    """
    try:
        user_id = str(current_user.id)
        
        # Run comprehensive connection demo
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            demo_results = []
            
            # Test 1: Basic connection test
            auth_manager = create_auth_manager(user_id)
            test_result = loop.run_until_complete(auth_manager.test_connection())
            demo_results.append({
                'test': 'basic_connection',
                'result': test_result
            })
            
            # Test 2: Health check
            health_check = loop.run_until_complete(auth_manager.ensure_connection())
            demo_results.append({
                'test': 'health_check',
                'result': {'healthy': health_check}
            })
            
            # Test 3: Rate limit check
            rate_limit_info = {
                'can_make_request': auth_manager.rate_limit_manager.can_make_request(),
                'wait_time': auth_manager.rate_limit_manager.get_wait_time(),
                'current_requests': len(auth_manager.rate_limit_manager.request_times)
            }
            demo_results.append({
                'test': 'rate_limits',
                'result': rate_limit_info
            })
            
            # Test 4: Connection info
            connection_info = auth_manager.get_connection_info()
            demo_results.append({
                'test': 'connection_info',
                'result': connection_info
            })
            
            return jsonify({
                'success': True,
                'message': 'OpenAI authentication demo completed',
                'demo_results': demo_results,
                'tests_completed': len(demo_results)
            })
            
        finally:
            loop.close()
    
    except Exception as e:
        logger.error(f"Error in OpenAI connection demo: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500