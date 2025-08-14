"""
API Compliance Routes
Flask routes for API compliance testing and monitoring
"""

import logging
from datetime import datetime
from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required, current_user

from utils.api_compliance_test import run_compliance_test
from utils.api_compliance_checker import api_compliance_checker

logger = logging.getLogger(__name__)

api_compliance_bp = Blueprint('api_compliance', __name__)

@api_compliance_bp.route('/api/compliance/test', methods=['POST'])
@login_required
def run_compliance_tests():
    """Run comprehensive API compliance tests"""
    try:
        # Only allow admins to run compliance tests
        if not current_user.is_admin():
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Admin access required for compliance testing'
            }), 403
        
        test_results = run_compliance_test()
        
        return jsonify({
            'success': True,
            'message': 'API compliance tests completed',
            'results': test_results
        })
        
    except Exception as e:
        logger.error(f"Error running compliance tests: {e}")
        return jsonify({
            'error': 'Test execution failed',
            'message': str(e)
        }), 500

@api_compliance_bp.route('/api/compliance/audit', methods=['POST'])
@login_required
def run_compliance_audit():
    """Run comprehensive API compliance audit"""
    try:
        # Only allow admins to run compliance audits
        if not current_user.is_admin():
            return jsonify({
                'error': 'Unauthorized', 
                'message': 'Admin access required for compliance auditing'
            }), 403
        
        audit_results = api_compliance_checker.audit_all_apis()
        
        return jsonify({
            'success': True,
            'message': 'API compliance audit completed',
            'results': audit_results
        })
        
    except Exception as e:
        logger.error(f"Error running compliance audit: {e}")
        return jsonify({
            'error': 'Audit execution failed',
            'message': str(e)
        }), 500

@api_compliance_bp.route('/api/compliance/report', methods=['GET'])
@login_required
def get_compliance_report():
    """Get formatted compliance report"""
    try:
        # Only allow admins to view compliance reports
        if not current_user.is_admin():
            return jsonify({
                'error': 'Unauthorized',
                'message': 'Admin access required for compliance reports'
            }), 403
        
        report = api_compliance_checker.generate_compliance_report()
        
        return jsonify({
            'success': True,
            'report': report,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error generating compliance report: {e}")
        return jsonify({
            'error': 'Report generation failed',
            'message': str(e)
        }), 500

@api_compliance_bp.route('/api/compliance/status', methods=['GET'])
@login_required
def get_compliance_status():
    """Get current API compliance status"""
    try:
        # Basic compliance status check
        status = {
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': current_user.id,
            'components': {
                'rfc6750_validator': False,
                'prompt_injection_protection': False,
                'oauth_security': False,
                'enhanced_security': False
            },
            'overall_status': 'unknown'
        }
        
        # Check component availability
        try:
            from utils.rfc6750_validator import rfc6750_validator
            status['components']['rfc6750_validator'] = True
        except ImportError:
            pass
        
        try:
            from utils.prompt_injection_protection import prompt_protector
            status['components']['prompt_injection_protection'] = True
        except ImportError:
            pass
        
        try:
            from utils.oauth_security import oauth_security
            status['components']['oauth_security'] = True
        except ImportError:
            pass
        
        try:
            from utils.enhanced_oauth_security import enhanced_oauth_security
            status['components']['enhanced_security'] = True
        except ImportError:
            pass
        
        # Calculate overall status
        available_components = sum(status['components'].values())
        total_components = len(status['components'])
        
        if available_components == total_components:
            status['overall_status'] = 'compliant'
        elif available_components >= total_components * 0.75:
            status['overall_status'] = 'mostly_compliant'
        elif available_components > 0:
            status['overall_status'] = 'partially_compliant'
        else:
            status['overall_status'] = 'non_compliant'
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Error getting compliance status: {e}")
        return jsonify({
            'error': 'Status check failed',
            'message': str(e)
        }), 500

@api_compliance_bp.route('/compliance/dashboard')
@login_required
def compliance_dashboard():
    """Render compliance dashboard page"""
    try:
        # Only allow admins to view compliance dashboard
        if not current_user.is_admin():
            return render_template('error.html', 
                                 error_message='Admin access required for compliance dashboard'), 403
        
        return render_template('compliance_dashboard.html')
        
    except Exception as e:
        logger.error(f"Error rendering compliance dashboard: {e}")
        return render_template('error.html', 
                             error_message=f'Dashboard error: {e}'), 500

@api_compliance_bp.route('/api/compliance/validate-bearer-token', methods=['POST'])
@login_required
def validate_bearer_token():
    """Test Bearer token validation endpoint"""
    try:
        auth_header = request.headers.get('Authorization', '')
        
        from utils.rfc6750_validator import rfc6750_validator
        is_valid, message, token = rfc6750_validator.validate_authorization_header(auth_header)
        
        return jsonify({
            'success': True,
            'is_valid': is_valid,
            'message': message,
            'token_present': bool(token)
        })
        
    except Exception as e:
        logger.error(f"Error validating Bearer token: {e}")
        return jsonify({
            'error': 'Token validation failed',
            'message': str(e)
        }), 500

@api_compliance_bp.route('/api/compliance/test-prompt-protection', methods=['POST'])
@login_required
def test_prompt_protection():
    """Test prompt injection protection endpoint"""
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        
        if not prompt:
            return jsonify({
                'error': 'Missing prompt',
                'message': 'Prompt field is required'
            }), 400
        
        from utils.prompt_injection_protection import prompt_protector
        is_safe, sanitized_prompt, analysis = prompt_protector.validate_prompt(prompt, str(current_user.id))
        
        return jsonify({
            'success': True,
            'is_safe': is_safe,
            'sanitized_prompt': sanitized_prompt,
            'analysis': analysis
        })
        
    except Exception as e:
        logger.error(f"Error testing prompt protection: {e}")
        return jsonify({
            'error': 'Prompt protection test failed',
            'message': str(e)
        }), 500