"""
OAuth 2.0 Error Response Handler
RFC 6749 Section 5.2 - Error Response Format
"""

import logging
from flask import jsonify

logger = logging.getLogger(__name__)

class OAuthError(Exception):
    """Base OAuth error class following RFC 6749 Section 5.2"""
    
    def __init__(self, error_code, error_description=None, error_uri=None):
        self.error_code = error_code
        self.error_description = error_description
        self.error_uri = error_uri
        super().__init__(error_description or error_code)
    
    def to_dict(self):
        """Convert to RFC 6749 compliant error response"""
        error_response = {
            'error': self.error_code
        }
        
        if self.error_description:
            error_response['error_description'] = self.error_description
        
        if self.error_uri:
            error_response['error_uri'] = self.error_uri
        
        return error_response
    
    def to_json_response(self, status_code=400):
        """Return Flask JSON response with proper HTTP status"""
        return jsonify(self.to_dict()), status_code

# RFC 6749 Section 5.2 - Standard Error Codes
class InvalidRequestError(OAuthError):
    """invalid_request - Missing required parameter or invalid parameter value"""
    def __init__(self, description=None):
        super().__init__('invalid_request', description)

class InvalidClientError(OAuthError):
    """invalid_client - Client authentication failed"""
    def __init__(self, description=None):
        super().__init__('invalid_client', description)

class InvalidGrantError(OAuthError):
    """invalid_grant - Invalid authorization code or refresh token"""
    def __init__(self, description=None):
        super().__init__('invalid_grant', description)

class UnauthorizedClientError(OAuthError):
    """unauthorized_client - Client not authorized for this grant type"""
    def __init__(self, description=None):
        super().__init__('unauthorized_client', description)

class UnsupportedGrantTypeError(OAuthError):
    """unsupported_grant_type - Authorization grant type not supported"""
    def __init__(self, description=None):
        super().__init__('unsupported_grant_type', description)

class InvalidScopeError(OAuthError):
    """invalid_scope - Requested scope is invalid or exceeds granted scope"""
    def __init__(self, description=None):
        super().__init__('invalid_scope', description)

class ServerError(OAuthError):
    """server_error - Internal server error"""
    def __init__(self, description=None):
        super().__init__('server_error', description)
        
    def to_json_response(self, status_code=500):
        return super().to_json_response(status_code)

class TemporarilyUnavailableError(OAuthError):
    """temporarily_unavailable - Service temporarily unavailable"""
    def __init__(self, description=None):
        super().__init__('temporarily_unavailable', description)
        
    def to_json_response(self, status_code=503):
        return super().to_json_response(status_code)

# Additional errors for enhanced security
class InvalidStateError(OAuthError):
    """invalid_state - State parameter validation failed (CSRF protection)"""
    def __init__(self, description=None):
        super().__init__('invalid_state', description or 'State parameter validation failed')

class ExpiredTokenError(OAuthError):
    """expired_token - Token has expired"""
    def __init__(self, description=None):
        super().__init__('expired_token', description or 'Access token has expired')

def handle_oauth_error(error):
    """Handle OAuth errors with proper logging and response formatting"""
    if isinstance(error, OAuthError):
        logger.error(f"OAuth error: {error.error_code} - {error.error_description}")
        return error.to_json_response()
    else:
        logger.error(f"Unexpected error in OAuth flow: {str(error)}")
        server_error = ServerError(f"Internal server error: {str(error)}")
        return server_error.to_json_response()