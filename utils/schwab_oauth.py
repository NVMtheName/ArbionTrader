import os
import logging
import base64
import hashlib
import secrets
import requests
import time
from datetime import datetime, timedelta
from flask import session, url_for
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Shared HTTP session for connection pooling
_http_session = None

def get_http_session():
    """Get or create shared HTTP session with connection pooling"""
    global _http_session
    if _http_session is None:
        _http_session = requests.Session()
        # Configure connection pooling
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=3,
            pool_block=False
        )
        _http_session.mount('http://', adapter)
        _http_session.mount('https://', adapter)
    return _http_session

class SchwabOAuth:
    """Schwab OAuth2 integration for secure authentication - Multi-user compatible"""

    def __init__(self, user_id=None):
        self.user_id = user_id
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = None
        self.auth_url = 'https://api.schwabapi.com/v1/oauth/authorize'
        self.token_url = 'https://api.schwabapi.com/v1/oauth/token'
        self.session = get_http_session()  # Use shared session for connection pooling

        # Load client credentials from database if user_id provided
        if user_id:
            self._load_client_credentials(user_id)
    
    def _load_client_credentials(self, user_id):
        """Load OAuth2 client credentials from database for the user"""
        try:
            from models import OAuthClientCredential
            
            client_cred = OAuthClientCredential.query.filter_by(
                user_id=user_id,
                provider='schwab',
                is_active=True
            ).first()
            
            if client_cred:
                self.client_id = client_cred.client_id
                self.client_secret = client_cred.client_secret
                self.redirect_uri = client_cred.redirect_uri
                logger.info(f"Loaded Schwab OAuth credentials for user {user_id}")
            else:
                logger.warning(f"No active Schwab OAuth client credentials found for user {user_id}")
                
        except Exception as e:
            logger.error(f"Failed to load Schwab OAuth credentials for user {user_id}: {e}")
    
    def set_client_credentials(self, client_id, client_secret, redirect_uri):
        """Set client credentials programmatically"""
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
    
    def save_client_credentials(self, user_id, client_id, client_secret, redirect_uri):
        """Save OAuth2 client credentials to database"""
        try:
            from models import OAuthClientCredential
            from app import db
            
            # Check if credentials already exist
            existing_cred = OAuthClientCredential.query.filter_by(
                user_id=user_id,
                provider='schwab'
            ).first()
            
            if existing_cred:
                existing_cred.client_id = client_id
                existing_cred.client_secret = client_secret
                existing_cred.redirect_uri = redirect_uri
                existing_cred.updated_at = datetime.utcnow()
                existing_cred.is_active = True
            else:
                new_cred = OAuthClientCredential()
                new_cred.user_id = user_id
                new_cred.provider = 'schwab'
                new_cred.client_id = client_id
                new_cred.client_secret = client_secret
                new_cred.redirect_uri = redirect_uri
                db.session.add(new_cred)
            
            db.session.commit()
            logger.info(f"Saved Schwab OAuth client credentials for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save Schwab OAuth client credentials: {e}")
            return False
    
    def get_authorization_url(self):
        """Generate authorization URL with enhanced security and PKCE"""
        try:
            if not self.client_id:
                raise ValueError("Schwab OAuth client credentials not configured for this user. Please configure your OAuth2 client credentials first.")
            
            # Enhanced security checks
            from utils.oauth_security import oauth_security
            
            # Validate redirect URI security
            is_valid, message = oauth_security.validate_redirect_uri(self.redirect_uri)
            if not is_valid:
                raise ValueError(f"Invalid redirect URI: {message}")
            
            # Generate PKCE parameters with enhanced security
            from utils.pkce_utils import generate_pkce_pair
            code_verifier, code_challenge = generate_pkce_pair()
            
            # Generate cryptographically secure state parameter
            state = oauth_security.generate_secure_state(self.user_id)
            
            # Store in session with security enhancements
            session['schwab_code_verifier'] = code_verifier
            session['schwab_oauth_state'] = state
            session['schwab_oauth_timestamp'] = int(time.time())
            
            # Build authorization URL with security parameters
            params = {
                'client_id': self.client_id,
                'redirect_uri': self.redirect_uri,
                'response_type': 'code',
                'scope': 'AccountAccess',
                'state': state,
                'code_challenge': code_challenge,
                'code_challenge_method': 'S256'
            }
            
            auth_url = f"{self.auth_url}?{urlencode(params)}"
            logger.info(f"Generated secure Schwab OAuth authorization URL for user {self.user_id}")
            logger.info(f"Using redirect URI: {self.redirect_uri}")
            return auth_url
            
        except Exception as e:
            logger.error(f"Error generating Schwab OAuth authorization URL: {e}")
            raise
    
    def exchange_code_for_token(self, auth_code, state):
        """Exchange authorization code for access token with enhanced security"""
        try:
            if not self.client_id or not self.client_secret:
                raise ValueError("Schwab OAuth client credentials not configured")
            
            # Enhanced security validation
            from utils.oauth_security import oauth_security
            
            # Check rate limiting
            allowed, message = oauth_security.check_rate_limiting(self.user_id, "schwab_token_exchange")
            if not allowed:
                logger.warning(f"Rate limit exceeded for Schwab token exchange - user {self.user_id}")
                return {'success': False, 'message': message}
            
            # Enhanced state parameter validation (strict - no fallback)
            stored_state = session.get('schwab_oauth_state')
            logger.info(f"Enhanced Schwab state validation - stored: {stored_state}, received: {state}")

            # Strict state validation - no fallbacks allowed for security
            is_valid, validation_message = oauth_security.validate_state_security(stored_state, state, self.user_id)
            if not is_valid:
                oauth_security.record_failed_attempt(self.user_id, "schwab_token_exchange")
                logger.error(f"State validation failed: {validation_message}")
                return {'success': False, 'message': f'State validation failed: {validation_message}'}

            # Check session timestamp to prevent replay attacks
            session_timestamp = session.get('schwab_oauth_timestamp', 0)
            current_time = int(time.time())
            if current_time - session_timestamp > 600:  # 10 minutes max
                logger.error("Schwab OAuth session expired - potential replay attack")
                return {'success': False, 'message': 'OAuth session expired. Please try authenticating again.'}

            # Get code verifier from session (required for PKCE)
            code_verifier = session.get('schwab_code_verifier')
            if not code_verifier:
                logger.error("Code verifier not found in session - PKCE validation failed")
                return {'success': False, 'message': 'PKCE validation failed. Please try authenticating again.'}
            
            # Prepare token request with security headers
            auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
            
            headers = {
                'Authorization': f'Basic {auth_header}',
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Arbion-Trading-Platform/1.0'
            }
            
            data = {
                'grant_type': 'authorization_code',
                'code': auth_code,
                'redirect_uri': self.redirect_uri,
                'code_verifier': code_verifier
            }
            
            response = self.session.post(self.token_url, headers=headers, data=data, timeout=30)
            response.raise_for_status()
            
            token_data = response.json()
            
            # Enhanced session cleanup with security manager
            from utils.oauth_security import oauth_security
            oauth_security.secure_session_cleanup([
                'schwab_code_verifier', 
                'schwab_oauth_state', 
                'schwab_oauth_timestamp'
            ])
            oauth_security.clear_successful_attempt(self.user_id, "schwab_token_exchange")
            
            # Calculate expiration time
            expires_in = token_data.get('expires_in', 3600)
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            credentials = {
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token'),
                'expires_at': expires_at.isoformat(),
                'scope': token_data.get('scope', 'AccountAccess')
            }
            
            logger.info(f"Successfully exchanged Schwab OAuth code for tokens")
            return {
                'success': True,
                'credentials': credentials
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error during Schwab token exchange: {e}")
            return {
                'success': False,
                'message': f'Token exchange failed: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Error during Schwab token exchange: {e}")
            return {
                'success': False,
                'message': f'Token exchange failed: {str(e)}'
            }
    
    def refresh_token(self, refresh_token):
        """Refresh access token using refresh token"""
        try:
            if not self.client_id or not self.client_secret:
                raise ValueError("Schwab OAuth client credentials not configured")

            auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()

            headers = {
                'Authorization': f'Basic {auth_header}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }

            data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token
            }

            response = self.session.post(self.token_url, headers=headers, data=data, timeout=30)

            if response.status_code == 200:
                token_data = response.json()

                # Calculate expiration time
                expires_in = token_data.get('expires_in', 3600)
                expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

                credentials = {
                    'access_token': token_data['access_token'],
                    'refresh_token': token_data.get('refresh_token', refresh_token),
                    'expires_at': expires_at.isoformat(),
                    'scope': token_data.get('scope', 'AccountAccess')
                }

                logger.info("Successfully refreshed Schwab OAuth token")
                return {
                    'success': True,
                    'credentials': credentials
                }

            # Parse error response body for details
            error_body = None
            try:
                error_body = response.json()
            except Exception:
                error_body = {'raw': response.text[:500] if response.text else 'No response body'}

            error_code = error_body.get('error', '') if isinstance(error_body, dict) else ''
            error_desc = error_body.get('error_description', '') if isinstance(error_body, dict) else ''

            # Handle specific HTTP status codes
            if response.status_code == 400:
                # 400 typically means invalid_grant - refresh token expired or revoked
                logger.error(
                    f"Schwab token refresh failed (400 Bad Request): {error_code} - {error_desc}. "
                    f"The refresh token has likely expired. User {self.user_id} must re-authenticate with Schwab."
                )
                return {
                    'success': False,
                    'message': f'Refresh token expired or invalid ({error_code}). Please re-authenticate with Schwab.',
                    'reauth_required': True,
                    'error_code': error_code
                }

            if response.status_code == 401:
                logger.error(
                    f"Schwab token refresh failed (401 Unauthorized): {error_code} - {error_desc}. "
                    f"Client credentials may be invalid. User {self.user_id} must re-configure Schwab OAuth."
                )
                return {
                    'success': False,
                    'message': f'Client authentication failed ({error_code}). Please verify your Schwab OAuth credentials.',
                    'reauth_required': True,
                    'error_code': error_code
                }

            if response.status_code == 403:
                logger.error(
                    f"Schwab token refresh failed (403 Forbidden): {error_code} - {error_desc}. "
                    f"Access has been revoked. User {self.user_id} must re-authenticate with Schwab."
                )
                return {
                    'success': False,
                    'message': f'Access revoked or forbidden ({error_code}). Please re-authenticate with Schwab.',
                    'reauth_required': True,
                    'error_code': error_code
                }

            if response.status_code >= 500:
                logger.warning(
                    f"Schwab token refresh failed (server error {response.status_code}): {error_code} - {error_desc}. "
                    f"This may be a temporary issue - will retry."
                )
                return {
                    'success': False,
                    'message': f'Schwab server error ({response.status_code}). Will retry automatically.',
                    'reauth_required': False,
                    'error_code': error_code
                }

            # Other status codes
            logger.error(
                f"Schwab token refresh failed (HTTP {response.status_code}): {error_code} - {error_desc}"
            )
            return {
                'success': False,
                'message': f'Token refresh failed with status {response.status_code}: {error_desc or error_code}',
                'reauth_required': response.status_code in (400, 401, 403),
                'error_code': error_code
            }

        except requests.exceptions.Timeout:
            logger.warning(f"Schwab token refresh timed out for user {self.user_id} - will retry")
            return {
                'success': False,
                'message': 'Token refresh request timed out. Will retry automatically.',
                'reauth_required': False
            }
        except requests.exceptions.RequestException as e:
            logger.warning(f"Schwab token refresh network error for user {self.user_id}: {e} - will retry")
            return {
                'success': False,
                'message': f'Network error during token refresh: {str(e)}. Will retry automatically.',
                'reauth_required': False
            }
        except Exception as e:
            logger.error(f"Unexpected error refreshing Schwab OAuth token for user {self.user_id}: {e}")
            return {
                'success': False,
                'message': f'Token refresh failed: {str(e)}'
            }
    
    def is_token_expired(self, credentials):
        """Check if access token is expired"""
        try:
            # Support both standardized field and legacy field for backwards compatibility
            expires_at_str = credentials.get('expires_at') or credentials.get('token_expiry')
            if not expires_at_str:
                return True

            expires_at = datetime.fromisoformat(expires_at_str)
            # Add 5-minute buffer before expiration for safety
            return datetime.utcnow() + timedelta(minutes=5) >= expires_at

        except Exception as e:
            logger.error(f"Error checking token expiration: {e}")
            return True
    
    def get_valid_token(self, encrypted_credentials):
        """Get a valid access token, refreshing if necessary and updating database"""
        try:
            from utils.encryption import decrypt_credentials, encrypt_credentials

            credentials = decrypt_credentials(encrypted_credentials)

            # Check if token is expired
            if not self.is_token_expired(credentials):
                logger.info(f"Schwab token is still valid for user {self.user_id}")
                return credentials['access_token']

            # Try to refresh token
            refresh_token = credentials.get('refresh_token')
            if not refresh_token:
                logger.error(f"No refresh token available for user {self.user_id}")
                return None

            logger.info(f"Refreshing expired Schwab token for user {self.user_id}")
            refresh_result = self.refresh_token(refresh_token)

            if refresh_result['success']:
                # Update the database with new tokens
                try:
                    from models import APICredential
                    from app import db

                    cred = APICredential.query.filter_by(
                        user_id=self.user_id,
                        provider='schwab',
                        is_active=True
                    ).first()

                    if cred:
                        cred.encrypted_credentials = encrypt_credentials(refresh_result['credentials'])
                        cred.updated_at = datetime.utcnow()
                        db.session.commit()
                        logger.info(f"Updated Schwab credentials in database for user {self.user_id}")
                    else:
                        logger.warning(f"No Schwab credential record found to update for user {self.user_id}")

                except Exception as db_error:
                    logger.error(f"Error updating Schwab credentials in database: {db_error}")
                    # Continue anyway - we still have the refreshed token

                return refresh_result['credentials']['access_token']
            else:
                logger.error(f"Failed to refresh Schwab token: {refresh_result.get('message')}")
                return None

        except Exception as e:
            logger.error(f"Error getting valid Schwab token: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def test_connection(self, access_token):
        """Test the connection with Schwab API"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Test with accounts endpoint
            response = self.session.get(
                'https://api.schwabapi.com/trader/v1/accounts',
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'message': 'Schwab API connection successful'
                }
            else:
                return {
                    'success': False,
                    'message': f'Schwab API connection failed: {response.status_code}'
                }
                
        except Exception as e:
            logger.error(f"Error testing Schwab connection: {e}")
            return {
                'success': False,
                'message': f'Connection test failed: {str(e)}'
            }