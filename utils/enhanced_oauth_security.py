"""
Enhanced OAuth Security Implementation
Comprehensive RFC-compliant OAuth2 security with Bearer token validation,
rate limiting, error handling, and prompt injection protection
"""

import os
import logging
from typing import Dict, Tuple, Any, Optional
from datetime import datetime, timedelta
from flask import request, session, g
from functools import wraps

from utils.rfc6750_validator import rfc6750_validator
from utils.prompt_injection_protection import prompt_protector
from utils.oauth_security import oauth_security

logger = logging.getLogger(__name__)

class EnhancedOAuthSecurity:
    """Enhanced OAuth security manager with RFC compliance"""
    
    def __init__(self):
        self.rfc6750_validator = rfc6750_validator
        self.prompt_protector = prompt_protector
        self.oauth_security = oauth_security
    
    def validate_bearer_token_request(self, required_scopes: list = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Comprehensive Bearer token validation per RFC 6750
        
        Args:
            required_scopes: List of required scopes for the operation
            
        Returns:
            Tuple of (is_valid, validation_result)
        """
        try:
            auth_header = request.headers.get('Authorization', '')
            
            # RFC 6750 Section 2.1 validation
            is_valid, message, token = self.rfc6750_validator.validate_authorization_header(auth_header)
            
            if not is_valid:
                return False, {
                    'error': 'invalid_token',
                    'error_description': message,
                    'www_authenticate': self.rfc6750_validator.generate_www_authenticate_header(
                        realm='api',
                        error='invalid_token',
                        error_description=message
                    )
                }
            
            # Load token info from database and validate
            token_info = self._load_token_info(token)
            if not token_info:
                return False, {
                    'error': 'invalid_token',
                    'error_description': 'Token not found or invalid',
                    'www_authenticate': self.rfc6750_validator.generate_www_authenticate_header(
                        realm='api',
                        error='invalid_token'
                    )
                }
            
            # Validate token expiry
            is_valid_expiry, expiry_message = self.rfc6750_validator.validate_token_expiry(
                token_info.get('expires_at', '')
            )
            
            if not is_valid_expiry and 'expired' in expiry_message:
                return False, {
                    'error': 'invalid_token',
                    'error_description': 'Token has expired',
                    'www_authenticate': self.rfc6750_validator.generate_www_authenticate_header(
                        realm='api',
                        error='invalid_token',
                        error_description='Token has expired'
                    )
                }
            
            # Validate scopes if required
            if required_scopes:
                token_scopes = token_info.get('scope', '').split()
                is_valid_scope, scope_message = self.rfc6750_validator.validate_token_scope(
                    required_scopes, token_scopes
                )
                
                if not is_valid_scope:
                    return False, {
                        'error': 'insufficient_scope',
                        'error_description': scope_message,
                        'www_authenticate': self.rfc6750_validator.generate_www_authenticate_header(
                            realm='api',
                            scope=' '.join(required_scopes),
                            error='insufficient_scope'
                        )
                    }
            
            return True, {
                'token_info': token_info,
                'user_id': token_info.get('user_id'),
                'expires_soon': 'expires soon' in expiry_message
            }
            
        except Exception as e:
            logger.error(f"Error validating Bearer token request: {e}")
            return False, {
                'error': 'invalid_request',
                'error_description': 'Token validation failed',
                'www_authenticate': self.rfc6750_validator.generate_www_authenticate_header(realm='api')
            }
    
    def _load_token_info(self, token: str) -> Optional[Dict[str, Any]]:
        """Load token information from database"""
        try:
            from models import APICredential
            
            # Find token in database (simplified - in production use proper token lookup)
            api_cred = APICredential.query.filter_by(
                access_token=token,
                is_active=True
            ).first()
            
            if api_cred:
                return {
                    'user_id': api_cred.user_id,
                    'provider': api_cred.provider,
                    'expires_at': api_cred.token_expiry,
                    'scope': 'wallet:read accounts:read trading:execute'  # Default scopes
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error loading token info: {e}")
            return None
    
    def validate_trading_prompt(self, prompt: str, user_id: str = None) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validate trading prompt for injection attacks
        
        Args:
            prompt: Trading instruction prompt
            user_id: User identifier
            
        Returns:
            Tuple of (is_safe, sanitized_prompt, analysis_report)
        """
        return self.prompt_protector.validate_prompt(prompt, user_id)
    
    def check_rate_limits(self, user_id: str, action: str = "api_request") -> Tuple[bool, str]:
        """
        Check rate limits for API requests
        
        Args:
            user_id: User identifier
            action: Type of action being rate limited
            
        Returns:
            Tuple of (is_allowed, message)
        """
        return self.oauth_security.check_rate_limiting(user_id, action)
    
    def format_rfc_error_response(self, error_code: str, error_description: str = None) -> Dict[str, Any]:
        """Format RFC-compliant error response"""
        return self.rfc6750_validator.format_error_response(error_code, error_description)
    
    def bearer_token_required(self, required_scopes: list = None):
        """
        Decorator for endpoints requiring Bearer token authentication
        
        Args:
            required_scopes: List of required OAuth scopes
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                is_valid, result = self.validate_bearer_token_request(required_scopes)
                
                if not is_valid:
                    from flask import jsonify
                    
                    response = jsonify(result)
                    response.status_code = 401
                    
                    # Add WWW-Authenticate header per RFC 6750 Section 3
                    if 'www_authenticate' in result:
                        response.headers['WWW-Authenticate'] = result['www_authenticate']
                    
                    return response
                
                # Store token info in Flask g for use in the endpoint
                g.token_info = result['token_info']
                g.current_user_id = result['user_id']
                
                # Warn if token expires soon
                if result.get('expires_soon'):
                    logger.warning(f"Token expires soon for user {result['user_id']}")
                
                return f(*args, **kwargs)
            
            return decorated_function
        return decorator
    
    def rate_limited(self, action: str = "api_request"):
        """
        Decorator for rate limiting API endpoints
        
        Args:
            action: Type of action being rate limited
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                user_id = getattr(g, 'current_user_id', None)
                
                if user_id:
                    is_allowed, message = self.check_rate_limits(user_id, action)
                    
                    if not is_allowed:
                        from flask import jsonify
                        
                        error_response = self.format_rfc_error_response(
                            'invalid_request',
                            f'Rate limit exceeded: {message}'
                        )
                        
                        response = jsonify(error_response)
                        response.status_code = 429
                        response.headers['Retry-After'] = '300'  # 5 minutes
                        
                        return response
                
                return f(*args, **kwargs)
            
            return decorated_function
        return decorator
    
    def prompt_injection_protected(self):
        """Decorator for endpoints processing trading prompts"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                from flask import request, jsonify
                
                # Extract prompt from request
                prompt = request.json.get('prompt', '') if request.is_json else request.form.get('prompt', '')
                user_id = getattr(g, 'current_user_id', None)
                
                if prompt:
                    is_safe, sanitized_prompt, analysis = self.validate_trading_prompt(prompt, user_id)
                    
                    if not is_safe:
                        logger.warning(f"Prompt injection attempt blocked for user {user_id}: {analysis}")
                        
                        error_response = self.format_rfc_error_response(
                            'invalid_request',
                            'Prompt validation failed - potential security threat detected'
                        )
                        
                        response = jsonify(error_response)
                        response.status_code = 400
                        
                        return response
                    
                    # Replace original prompt with sanitized version
                    if request.is_json:
                        request.json['prompt'] = sanitized_prompt
                    else:
                        request.form = request.form.copy()
                        request.form['prompt'] = sanitized_prompt
                
                return f(*args, **kwargs)
            
            return decorated_function
        return decorator

# Global enhanced OAuth security instance
enhanced_oauth_security = EnhancedOAuthSecurity()