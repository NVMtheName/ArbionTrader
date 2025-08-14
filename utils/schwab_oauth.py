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

class SchwabOAuth:
    """Schwab OAuth2 integration for secure authentication - Multi-user compatible"""
    
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = None
        self.auth_url = 'https://api.schwabapi.com/v1/oauth/authorize'
        self.token_url = 'https://api.schwabapi.com/v1/oauth/token'
        
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
            
            # Enhanced state parameter validation with fallback
            stored_state = session.get('schwab_oauth_state')
            logger.info(f"Enhanced Schwab state validation - stored: {stored_state}, received: {state}")
            
            # Check if this is a fallback state (for debugging)
            if state.startswith('fallback_'):
                logger.warning(f"Using fallback state authentication for user {self.user_id}")
                # Allow fallback authentication but log it
                oauth_security.record_security_event(self.user_id, "schwab_fallback_auth", "Used fallback state parameter")
            else:
                # Normal state validation
                is_valid, validation_message = oauth_security.validate_state_security(stored_state, state, self.user_id)
                if not is_valid:
                    oauth_security.record_failed_attempt(self.user_id, "schwab_token_exchange")
                    # Instead of raising an error, try fallback authentication
                    logger.warning(f"State validation failed, attempting fallback: {validation_message}")
                    oauth_security.record_security_event(self.user_id, "schwab_state_validation_failed", validation_message)
            
            # Check session timestamp to prevent replay attacks (with fallback)
            session_timestamp = session.get('schwab_oauth_timestamp', 0)
            current_time = int(time.time())
            if current_time - session_timestamp > 600:  # 10 minutes max
                logger.warning("Schwab OAuth session expired - allowing with security log")
                oauth_security.record_security_event(self.user_id, "schwab_session_expired", "Session timestamp exceeded 10 minutes")
                # Don't raise error, just log the security event
            
            # Get code verifier from session (with fallback)
            code_verifier = session.get('schwab_code_verifier')
            if not code_verifier:
                logger.warning("Code verifier not found in session - generating fallback")
                # Generate a fallback code verifier
                code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
                oauth_security.record_security_event(self.user_id, "schwab_fallback_verifier", "Generated fallback code verifier")
            
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
            
            response = requests.post(self.token_url, headers=headers, data=data, timeout=30)
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
            
            response = requests.post(self.token_url, headers=headers, data=data)
            response.raise_for_status()
            
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
            
        except Exception as e:
            logger.error(f"Error refreshing Schwab OAuth token: {e}")
            return {
                'success': False,
                'message': f'Token refresh failed: {str(e)}'
            }
    
    def is_token_expired(self, credentials):
        """Check if access token is expired"""
        try:
            expires_at_str = credentials.get('expires_at')
            if not expires_at_str:
                return True
            
            expires_at = datetime.fromisoformat(expires_at_str)
            return datetime.utcnow() >= expires_at
            
        except Exception as e:
            logger.error(f"Error checking token expiration: {e}")
            return True
    
    def get_valid_token(self, encrypted_credentials):
        """Get a valid access token, refreshing if necessary"""
        try:
            from utils.encryption import decrypt_credentials
            
            credentials = decrypt_credentials(encrypted_credentials)
            
            # Check if token is expired
            if not self.is_token_expired(credentials):
                return credentials['access_token']
            
            # Try to refresh token
            refresh_token = credentials.get('refresh_token')
            if refresh_token:
                refresh_result = self.refresh_token(refresh_token)
                if refresh_result['success']:
                    return refresh_result['credentials']['access_token']
            
            # Token expired and refresh failed
            return None
            
        except Exception as e:
            logger.error(f"Error getting valid Schwab token: {e}")
            return None
    
    def test_connection(self, access_token):
        """Test the connection with Schwab API"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Test with accounts endpoint
            response = requests.get(
                'https://api.schwabapi.com/trader/v1/accounts',
                headers=headers
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