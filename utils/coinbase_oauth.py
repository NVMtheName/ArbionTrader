import os
import requests
import logging
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode
from flask import session, request, redirect, url_for, flash
from utils.encryption import encrypt_credentials, decrypt_credentials

logger = logging.getLogger(__name__)

class CoinbaseOAuth:
    """Coinbase OAuth2 integration for secure authentication - Multi-user compatible"""
    
    def __init__(self, user_id=None):
        self.user_id = user_id
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = None
        self.auth_url = 'https://www.coinbase.com/oauth/authorize'
        self.token_url = 'https://api.coinbase.com/oauth/token'
        self.api_base_url = 'https://api.coinbase.com/v2'
        
        # Load client credentials from database if user_id provided
        if user_id:
            self._load_client_credentials(user_id)
    
    def _load_client_credentials(self, user_id):
        """Load OAuth2 client credentials from database for the user"""
        try:
            from models import OAuthClientCredential
            
            client_cred = OAuthClientCredential.query.filter_by(
                user_id=user_id,
                provider='coinbase',
                is_active=True
            ).first()
            
            if client_cred:
                self.client_id = client_cred.client_id
                self.client_secret = client_cred.client_secret
                self.redirect_uri = client_cred.redirect_uri
                logger.info(f"Loaded Coinbase OAuth credentials for user {user_id}")
            else:
                logger.warning(f"No active Coinbase OAuth client credentials found for user {user_id}")
                
        except Exception as e:
            logger.error(f"Failed to load Coinbase OAuth credentials for user {user_id}: {e}")
    
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
                provider='coinbase'
            ).first()
            
            if existing_cred:
                existing_cred.client_id = client_id
                existing_cred.client_secret = client_secret
                existing_cred.redirect_uri = redirect_uri
                existing_cred.updated_at = datetime.utcnow()
                existing_cred.is_active = True
            else:
                new_cred = OAuthClientCredential(
                    user_id=user_id,
                    provider='coinbase',
                    client_id=client_id,
                    client_secret=client_secret,
                    redirect_uri=redirect_uri
                )
                db.session.add(new_cred)
            
            db.session.commit()
            logger.info(f"Saved Coinbase OAuth client credentials for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save Coinbase OAuth client credentials: {e}")
            return False
    
    def get_authorization_url(self):
        """Generate authorization URL with state parameter"""
        try:
            if not self.client_id:
                raise ValueError("Coinbase OAuth client credentials not configured for this user. Please configure your OAuth2 client credentials first.")
            
            # Generate secure state parameter
            state = secrets.token_urlsafe(32)
            session['coinbase_oauth_state'] = state
            
            # Build authorization URL with required scopes
            auth_params = {
                'response_type': 'code',
                'client_id': self.client_id,
                'redirect_uri': self.redirect_uri,
                'state': state,
                'scope': 'wallet:user:read wallet:accounts:read wallet:transactions:read'
            }
            
            auth_url = f"{self.auth_url}?{urlencode(auth_params)}"
            
            logger.info(f"Generated Coinbase authorization URL for user {self.user_id}")
            return auth_url
        
        except Exception as e:
            logger.error(f"Error generating Coinbase authorization URL: {str(e)}")
            raise
    
    def exchange_code_for_token(self, auth_code, state):
        """Exchange authorization code for access token"""
        try:
            if not self.client_id or not self.client_secret:
                raise ValueError("Coinbase OAuth2 credentials not configured")
            
            # Validate state parameter (RFC 6749 Section 10.12 - CSRF Protection)
            stored_state = session.get('coinbase_oauth_state')
            logger.info(f"State validation - stored: {stored_state}, received: {state}")
            
            if not state:
                logger.error("No state parameter received in callback - potential CSRF attack")
                from utils.oauth_errors import InvalidStateError
                raise InvalidStateError("Missing state parameter in OAuth callback")
            
            if not stored_state:
                logger.error("No stored state found in session - session may have expired")
                from utils.oauth_errors import InvalidStateError
                raise InvalidStateError("No OAuth state found in session")
            
            if stored_state != state:
                logger.error(f"State parameter mismatch - potential CSRF attack. Expected: {stored_state}, Got: {state}")
                from utils.oauth_errors import InvalidStateError
                raise InvalidStateError(f"Invalid state parameter. Expected: {stored_state}, Got: {state}")
            
            # Prepare token request
            token_data = {
                'grant_type': 'authorization_code',
                'code': auth_code,
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'redirect_uri': self.redirect_uri
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # Make token request
            logger.info(f"Making token request to {self.token_url}")
            logger.info(f"Token request data: {token_data}")
            
            response = requests.post(
                self.token_url,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'User-Agent': 'Arbion Trading Platform/1.0'
                },
                data=token_data,
                timeout=30
            )
            
            logger.info(f"Token response status: {response.status_code}")
            logger.info(f"Token response content: {response.text}")
            
            if response.status_code == 200:
                token_info = response.json()
                
                # Calculate expiry time
                expires_in = token_info.get('expires_in', 7200)
                expiry_time = datetime.utcnow() + timedelta(seconds=expires_in)
                
                # Prepare credentials for storage
                credentials = {
                    'access_token': token_info['access_token'],
                    'refresh_token': token_info.get('refresh_token'),
                    'token_expiry': expiry_time.isoformat(),
                    'scope': token_info.get('scope', 'wallet:accounts:read,wallet:transactions:read')
                }
                
                # Clean up session
                session.pop('coinbase_oauth_state', None)
                
                logger.info("Successfully exchanged Coinbase OAuth code for tokens")
                return {
                    'success': True,
                    'credentials': credentials
                }
            else:
                error_msg = f"Token exchange failed with status {response.status_code}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'message': error_msg
                }
        
        except Exception as e:
            logger.error(f"Error during Coinbase token exchange: {str(e)}")
            return {
                'success': False,
                'message': f'Token exchange failed: {str(e)}'
            }
    
    def refresh_token(self, refresh_token):
        """Refresh access token using refresh token"""
        try:
            if not self.client_id or not self.client_secret:
                raise ValueError("Coinbase OAuth2 credentials not configured")
            
            token_data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            response = requests.post(
                self.token_url,
                headers=headers,
                data=token_data,
                timeout=30
            )
            
            if response.status_code == 200:
                token_info = response.json()
                
                # Calculate expiry time
                expires_in = token_info.get('expires_in', 7200)
                expiry_time = datetime.utcnow() + timedelta(seconds=expires_in)
                
                credentials = {
                    'access_token': token_info['access_token'],
                    'refresh_token': token_info.get('refresh_token', refresh_token),
                    'token_expiry': expiry_time.isoformat(),
                    'scope': token_info.get('scope', 'wallet:accounts:read,wallet:transactions:read')
                }
                
                logger.info("Successfully refreshed Coinbase OAuth token")
                return {
                    'success': True,
                    'credentials': credentials
                }
            else:
                error_msg = f"Token refresh failed with status {response.status_code}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'message': error_msg
                }
        
        except Exception as e:
            logger.error(f"Error refreshing Coinbase OAuth token: {str(e)}")
            return {
                'success': False,
                'message': f'Token refresh failed: {str(e)}'
            }
    
    def is_token_expired(self, credentials):
        """Check if access token is expired"""
        try:
            expiry_str = credentials.get('token_expiry')
            if not expiry_str:
                return True
            
            expiry_time = datetime.fromisoformat(expiry_str)
            return datetime.utcnow() >= expiry_time
        
        except Exception as e:
            logger.error(f"Error checking token expiration: {str(e)}")
            return True
    
    def get_valid_token(self, encrypted_credentials):
        """Get a valid access token, refreshing if necessary"""
        try:
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
            logger.error(f"Error getting valid Coinbase token: {str(e)}")
            return None
    
    def test_connection(self, access_token):
        """Test the connection with Coinbase API"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Test with user endpoint
            response = requests.get(
                f'{self.api_base_url}/user',
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'message': 'Coinbase API connection successful'
                }
            else:
                return {
                    'success': False,
                    'message': f'Coinbase API connection failed: {response.status_code}'
                }
        
        except Exception as e:
            logger.error(f"Error testing Coinbase connection: {str(e)}")
            return {
                'success': False,
                'message': f'Connection test failed: {str(e)}'
            }
    
    def get_accounts(self, access_token):
        """Get user's Coinbase accounts"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f'{self.api_base_url}/accounts',
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get accounts: {response.status_code}")
                return None
        
        except Exception as e:
            logger.error(f"Error getting Coinbase accounts: {str(e)}")
            return None
    
    def get_account_transactions(self, access_token, account_id, limit=25):
        """Get transactions for a specific account"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            params = {'limit': limit}
            
            response = requests.get(
                f'{self.api_base_url}/accounts/{account_id}/transactions',
                headers=headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get transactions: {response.status_code}")
                return None
        
        except Exception as e:
            logger.error(f"Error getting Coinbase transactions: {str(e)}")
            return None