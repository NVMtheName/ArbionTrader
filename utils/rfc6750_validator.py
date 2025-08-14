"""
RFC 6750 Bearer Token Usage Validator
Implements comprehensive validation according to RFC 6750 standards
"""

import re
import logging
from typing import Dict, Tuple, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RFC6750Validator:
    """RFC 6750 Bearer Token Usage validator"""
    
    def __init__(self):
        # RFC 6750 Section 2.1 - Authorization Request Header Field format
        self.bearer_token_pattern = re.compile(r'^Bearer\s+([A-Za-z0-9\-._~+/]+=*)$')
        
        # RFC 6750 Section 3 - Error codes
        self.valid_error_codes = {
            'invalid_request',
            'invalid_token', 
            'insufficient_scope'
        }
    
    def validate_authorization_header(self, auth_header: str) -> Tuple[bool, str, Optional[str]]:
        """
        Validate Authorization header format per RFC 6750 Section 2.1
        
        Args:
            auth_header: Authorization header value
            
        Returns:
            Tuple of (is_valid, message, extracted_token)
        """
        try:
            if not auth_header:
                return False, "Missing Authorization header", None
            
            # Check Bearer token format
            match = self.bearer_token_pattern.match(auth_header.strip())
            if not match:
                return False, "Invalid Bearer token format - must be 'Bearer <token>'", None
            
            token = match.group(1)
            
            # Validate token format (base64url-safe characters)
            if not self._is_valid_token_format(token):
                return False, "Invalid token format - contains invalid characters", None
            
            return True, "Valid Bearer token format", token
            
        except Exception as e:
            logger.error(f"Error validating authorization header: {e}")
            return False, f"Header validation error: {e}", None
    
    def _is_valid_token_format(self, token: str) -> bool:
        """Validate token contains only valid characters per RFC 6750"""
        # RFC 6750 allows: ALPHA / DIGIT / "-" / "." / "_" / "~" / "+" / "/"
        valid_pattern = re.compile(r'^[A-Za-z0-9\-._~+/]+=*$')
        return bool(valid_pattern.match(token))
    
    def validate_token_scope(self, required_scopes: list, token_scopes: list) -> Tuple[bool, str]:
        """
        Validate token has sufficient scope per RFC 6750 Section 3.1
        
        Args:
            required_scopes: List of required scopes for the operation
            token_scopes: List of scopes granted to the token
            
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            if not required_scopes:
                return True, "No scope validation required"
            
            if not token_scopes:
                return False, "Token has no granted scopes"
            
            missing_scopes = set(required_scopes) - set(token_scopes)
            if missing_scopes:
                return False, f"Insufficient scope. Missing: {', '.join(missing_scopes)}"
            
            return True, "Sufficient scope granted"
            
        except Exception as e:
            logger.error(f"Error validating token scope: {e}")
            return False, f"Scope validation error: {e}"
    
    def format_error_response(self, error_code: str, error_description: str = None, 
                            error_uri: str = None) -> Dict[str, str]:
        """
        Format error response per RFC 6750 Section 3
        
        Args:
            error_code: RFC 6750 error code
            error_description: Human-readable error description
            error_uri: URI for additional error information
            
        Returns:
            Formatted error response dictionary
        """
        try:
            if error_code not in self.valid_error_codes:
                logger.warning(f"Non-standard error code used: {error_code}")
            
            error_response = {
                'error': error_code,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            if error_description:
                error_response['error_description'] = str(error_description)
            
            if error_uri:
                error_response['error_uri'] = str(error_uri)
            
            return error_response
            
        except Exception as e:
            logger.error(f"Error formatting error response: {e}")
            return {
                'error': 'invalid_request',
                'error_description': 'Internal error formatting response'
            }
    
    def validate_token_expiry(self, token_expiry: str) -> Tuple[bool, str]:
        """
        Validate token is not expired
        
        Args:
            token_expiry: ISO format expiry timestamp
            
        Returns:
            Tuple of (is_valid, message)
        """
        try:
            if not token_expiry:
                return False, "Token expiry not set"
            
            # Handle different datetime formats
            if token_expiry.endswith('Z'):
                expiry_time = datetime.fromisoformat(token_expiry.replace('Z', '+00:00'))
            else:
                expiry_time = datetime.fromisoformat(token_expiry)
            current_time = datetime.utcnow()
            
            if current_time >= expiry_time:
                return False, "Token has expired"
            
            # Check if token expires within 5 minutes (refresh warning)
            time_until_expiry = expiry_time - current_time
            if time_until_expiry < timedelta(minutes=5):
                return True, "Token expires soon - consider refreshing"
            
            return True, "Token is valid and not expired"
            
        except Exception as e:
            logger.error(f"Error validating token expiry: {e}")
            return False, f"Token expiry validation error: {e}"
    
    def generate_www_authenticate_header(self, realm: str = None, scope: str = None, 
                                       error: str = None, error_description: str = None) -> str:
        """
        Generate WWW-Authenticate header per RFC 6750 Section 3
        
        Args:
            realm: Authentication realm
            scope: Space-delimited scope values
            error: Error code for failed authentication
            error_description: Human-readable error description
            
        Returns:
            WWW-Authenticate header value
        """
        try:
            header_parts = ['Bearer']
            
            if realm:
                header_parts.append(f'realm="{str(realm)}"')
            
            if scope:
                header_parts.append(f'scope="{str(scope)}"')
            
            if error:
                header_parts.append(f'error="{str(error)}"')
            
            if error_description:
                header_parts.append(f'error_description="{str(error_description)}"')
            
            return ' '.join(header_parts)
            
        except Exception as e:
            logger.error(f"Error generating WWW-Authenticate header: {e}")
            return 'Bearer realm="api"'

# Global RFC 6750 validator instance
rfc6750_validator = RFC6750Validator()