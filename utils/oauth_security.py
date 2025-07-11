"""
Enhanced OAuth2 security module with comprehensive authentication and connection security
"""

import os
import secrets
import hashlib
import base64
import time
import logging
from datetime import datetime, timedelta
from flask import session, request, g
from functools import wraps

logger = logging.getLogger(__name__)

class OAuthSecurityManager:
    """Comprehensive OAuth2 security management"""
    
    def __init__(self):
        self.max_attempts = 3
        self.lockout_duration = 300  # 5 minutes
        self.state_expiry = 600  # 10 minutes
        self.failed_attempts = {}
        
    def generate_secure_state(self, user_id=None):
        """Generate cryptographically secure state parameter with additional entropy"""
        try:
            # Generate base state with high entropy
            base_state = secrets.token_urlsafe(32)
            
            # Add timestamp for expiry checking
            timestamp = int(time.time())
            
            # Add user context if available
            user_context = str(user_id) if user_id else "anonymous"
            
            # Create compound state with integrity check
            state_data = f"{base_state}:{timestamp}:{user_context}"
            
            # Add HMAC for integrity
            secret_key = os.environ.get('FLASK_SECRET_KEY', 'fallback-key')
            hmac_hash = hashlib.sha256(f"{state_data}:{secret_key}".encode()).hexdigest()[:16]
            
            final_state = f"{base_state}:{timestamp}:{hmac_hash}"
            
            logger.info(f"Generated secure state parameter for user {user_id}")
            return final_state
            
        except Exception as e:
            logger.error(f"Failed to generate secure state: {e}")
            # Fallback to basic secure state
            return secrets.token_urlsafe(32)
    
    def validate_state_security(self, stored_state, received_state, user_id=None):
        """Comprehensive state parameter validation with security checks"""
        try:
            if not stored_state or not received_state:
                logger.error("Missing state parameters in OAuth validation")
                return False, "Missing state parameters"
            
            if stored_state != received_state:
                logger.error(f"State parameter mismatch - potential CSRF attack")
                self._log_security_event("state_mismatch", user_id)
                return False, "Invalid state parameter"
            
            # Check state expiry if using enhanced state format
            if ':' in received_state:
                try:
                    parts = received_state.split(':')
                    if len(parts) >= 3:
                        timestamp = int(parts[1])
                        current_time = int(time.time())
                        
                        if current_time - timestamp > self.state_expiry:
                            logger.error("OAuth state parameter expired")
                            return False, "State parameter expired"
                        
                        # Validate HMAC if present
                        if len(parts) >= 4:
                            expected_hmac = parts[3]
                            secret_key = os.environ.get('FLASK_SECRET_KEY', 'fallback-key')
                            state_data = f"{parts[0]}:{parts[1]}:{parts[2] if len(parts) > 3 else ''}"
                            calculated_hmac = hashlib.sha256(f"{state_data}:{secret_key}".encode()).hexdigest()[:16]
                            
                            if expected_hmac != calculated_hmac:
                                logger.error("State parameter HMAC validation failed")
                                return False, "Invalid state parameter"
                        
                except (ValueError, IndexError):
                    logger.warning("Invalid state parameter format, proceeding with basic validation")
            
            logger.info(f"State parameter validation successful for user {user_id}")
            return True, "Valid state parameter"
            
        except Exception as e:
            logger.error(f"State validation error: {e}")
            return False, "State validation failed"
    
    def check_rate_limiting(self, user_id, action="oauth_attempt"):
        """Rate limiting for OAuth attempts"""
        try:
            current_time = time.time()
            user_key = f"{user_id}:{action}"
            
            if user_key in self.failed_attempts:
                attempts_data = self.failed_attempts[user_key]
                
                # Check if still in lockout period
                if current_time - attempts_data['last_attempt'] < self.lockout_duration:
                    if attempts_data['count'] >= self.max_attempts:
                        logger.warning(f"Rate limit exceeded for user {user_id}")
                        return False, f"Too many attempts. Try again in {self.lockout_duration} seconds."
                else:
                    # Reset attempts if lockout period expired
                    del self.failed_attempts[user_key]
            
            return True, "Rate limit check passed"
            
        except Exception as e:
            logger.error(f"Rate limiting check failed: {e}")
            return True, "Rate limiting unavailable"
    
    def record_failed_attempt(self, user_id, action="oauth_attempt"):
        """Record failed authentication attempts"""
        try:
            current_time = time.time()
            user_key = f"{user_id}:{action}"
            
            if user_key in self.failed_attempts:
                self.failed_attempts[user_key]['count'] += 1
                self.failed_attempts[user_key]['last_attempt'] = current_time
            else:
                self.failed_attempts[user_key] = {
                    'count': 1,
                    'last_attempt': current_time,
                    'first_attempt': current_time
                }
            
            logger.warning(f"Recorded failed attempt for user {user_id}: {self.failed_attempts[user_key]['count']}")
            
        except Exception as e:
            logger.error(f"Failed to record attempt: {e}")
    
    def clear_successful_attempt(self, user_id, action="oauth_attempt"):
        """Clear failed attempts after successful authentication"""
        try:
            user_key = f"{user_id}:{action}"
            if user_key in self.failed_attempts:
                del self.failed_attempts[user_key]
                logger.info(f"Cleared failed attempts for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to clear attempts: {e}")
    
    def _log_security_event(self, event_type, user_id=None):
        """Log security events for monitoring"""
        try:
            from models import SystemLog
            from app import db
            
            security_log = SystemLog(
                level='warning',
                message=f"OAuth security event: {event_type}",
                module='oauth_security',
                user_id=user_id
            )
            
            db.session.add(security_log)
            db.session.commit()
            
        except Exception as e:
            logger.error(f"Failed to log security event: {e}")
    
    def validate_redirect_uri(self, redirect_uri):
        """Validate redirect URI security"""
        try:
            if not redirect_uri:
                return False, "Missing redirect URI"
            
            if not redirect_uri.startswith('https://'):
                return False, "Redirect URI must use HTTPS"
            
            # Check for localhost/development URIs in production
            if any(dev_host in redirect_uri for dev_host in ['localhost', '127.0.0.1', '0.0.0.0']):
                if os.environ.get('FLASK_ENV') == 'production':
                    return False, "Development URIs not allowed in production"
            
            # Validate against allowed domains
            allowed_domains = ['arbion.ai', 'www.arbion.ai']
            if not any(domain in redirect_uri for domain in allowed_domains):
                return False, "Redirect URI domain not allowed"
            
            return True, "Valid redirect URI"
            
        except Exception as e:
            logger.error(f"Redirect URI validation error: {e}")
            return False, "Redirect URI validation failed"
    
    def secure_session_cleanup(self, keys_to_remove=None):
        """Secure cleanup of OAuth session data"""
        try:
            default_keys = [
                'coinbase_oauth_state',
                'schwab_oauth_state',
                'oauth_code_verifier',
                'oauth_user_id'
            ]
            
            keys_to_clean = keys_to_remove or default_keys
            
            for key in keys_to_clean:
                if key in session:
                    del session[key]
                    logger.debug(f"Cleaned session key: {key}")
            
            logger.info("OAuth session cleanup completed")
            
        except Exception as e:
            logger.error(f"Session cleanup error: {e}")

# Global security manager instance
oauth_security = OAuthSecurityManager()

def require_oauth_security(f):
    """Decorator for OAuth routes requiring enhanced security"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Check if user is authenticated
            from flask_login import current_user
            if not current_user.is_authenticated:
                logger.error("Unauthenticated OAuth attempt")
                return {"error": "Authentication required"}, 401
            
            # Rate limiting check
            allowed, message = oauth_security.check_rate_limiting(current_user.id)
            if not allowed:
                logger.warning(f"Rate limit exceeded for user {current_user.id}")
                return {"error": message}, 429
            
            # Execute the original function
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.error(f"OAuth security check failed: {e}")
            return {"error": "Security check failed"}, 500
    
    return decorated_function