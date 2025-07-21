import os
import requests
import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote
from flask import session, request, redirect, url_for, flash
from utils.pkce_utils import generate_pkce_pair
from utils.encryption import encrypt_credentials, decrypt_credentials

logger = logging.getLogger(__name__)

class SchwabOAuth:
    """Schwab OAuth2 integration with PKCE"""
    
    def __init__(self):
        # Load environment variables explicitly
        from dotenv import load_dotenv
        load_dotenv()
        
        self.client_id = os.environ.get('SCHWAB_CLIENT_ID')
        # Use development redirect URI for testing
        self.redirect_uri = os.environ.get('SCHWAB_REDIRECT_URI', 'https://www.arbion.ai/oauth_callback/broker')
        self.auth_url = 'https://api.schwabapi.com/v1/oauth/authorize'
        self.token_url = 'https://api.schwabapi.com/v1/oauth/token'
        
        if not self.client_id:
            logger.warning(f"SCHWAB_CLIENT_ID environment variable not set. Available env vars: {list(os.environ.keys())[:10]}")
            logger.info(f"Current working directory: {os.getcwd()}")
            logger.info(f"Looking for .env file: {os.path.exists('.env')}")
            # Try to load from .env file one more time
            try:
                with open('.env', 'r') as f:
                    for line in f:
                        if line.startswith('SCHWAB_CLIENT_ID='):
                            self.client_id = line.split('=', 1)[1].strip()
                            logger.info(f"Loaded SCHWAB_CLIENT_ID from .env file: {self.client_id[:10]}...")
                            break
            except Exception as e:
                logger.error(f"Failed to read .env file: {e}")
    
    def get_authorization_url(self):
        """Generate authorization URL with PKCE"""
        try:
            # Double-check client_id loading
            if not self.client_id:
                # Try to load from .env file again
                from dotenv import load_dotenv
                load_dotenv()
                self.client_id = os.environ.get('SCHWAB_CLIENT_ID')
                if not self.client_id:
                    # Final fallback - read directly from .env
                    try:
                        with open('.env', 'r') as f:
                            for line in f:
                                if line.startswith('SCHWAB_CLIENT_ID='):
                                    self.client_id = line.split('=', 1)[1].strip()
                                    break
                    except:
                        pass
            
            if not self.client_id:
                raise ValueError("Schwab client ID not configured. Please set SCHWAB_CLIENT_ID environment variable or contact support.")
            
            # Generate PKCE pair
            code_verifier, code_challenge = generate_pkce_pair()
            
            # Store code verifier in session for later use
            session['schwab_code_verifier'] = code_verifier
            
            # Build authorization URL
            auth_params = {
                'response_type': 'code',
                'client_id': self.client_id,
                'redirect_uri': self.redirect_uri,
                'code_challenge': code_challenge,
                'code_challenge_method': 'S256'
            }
            
            auth_url = f"{self.auth_url}?{urlencode(auth_params)}"
            
            logger.info("Generated Schwab authorization URL")
            return auth_url
        
        except Exception as e:
            logger.error(f"Error generating authorization URL: {str(e)}")
            raise
    
    def exchange_code_for_token(self, auth_code):
        """Exchange authorization code for access token"""
        try:
            if not self.client_id:
                raise ValueError("Schwab client ID not configured")
            
            code_verifier = session.get('schwab_code_verifier')
            if not code_verifier:
                raise ValueError("Code verifier not found in session")
            
            # Prepare token request
            token_data = {
                'grant_type': 'authorization_code',
                'code': auth_code,
                'client_id': self.client_id,
                'redirect_uri': self.redirect_uri,
                'code_verifier': code_verifier
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # Make token request
            response = requests.post(
                self.token_url,
                headers=headers,
                data=token_data,
                timeout=30
            )
            
            if response.status_code == 200:
                token_info = response.json()
                
                # Calculate expiry time
                expires_in = token_info.get('expires_in', 3600)
                expiry_time = datetime.utcnow() + timedelta(seconds=expires_in)
                
                # Prepare credentials for storage
                credentials = {
                    'access_token': token_info['access_token'],
                    'refresh_token': token_info.get('refresh_token'),
                    'token_expiry': expiry_time.isoformat(),
                    'client_id': self.client_id
                }
                
                # Clean up session
                session.pop('schwab_code_verifier', None)
                
                logger.info("Successfully exchanged code for Schwab token")
                return {
                    'success': True,
                    'credentials': credentials,
                    'message': 'Token exchange successful'
                }
            else:
                logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'message': f'Token exchange failed: {response.text}',
                    'status_code': response.status_code
                }
        
        except Exception as e:
            logger.error(f"Error during token exchange: {str(e)}")
            return {
                'success': False,
                'message': f'Token exchange error: {str(e)}'
            }
    
    def refresh_token(self, refresh_token):
        """Refresh access token using refresh token"""
        try:
            if not self.client_id:
                raise ValueError("Schwab client ID not configured")
            
            refresh_data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': self.client_id
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            response = requests.post(
                self.token_url,
                headers=headers,
                data=refresh_data,
                timeout=30
            )
            
            if response.status_code == 200:
                token_info = response.json()
                
                # Calculate expiry time
                expires_in = token_info.get('expires_in', 3600)
                expiry_time = datetime.utcnow() + timedelta(seconds=expires_in)
                
                # Prepare updated credentials
                credentials = {
                    'access_token': token_info['access_token'],
                    'refresh_token': token_info.get('refresh_token', refresh_token),
                    'token_expiry': expiry_time.isoformat(),
                    'client_id': self.client_id
                }
                
                logger.info("Successfully refreshed Schwab token")
                return {
                    'success': True,
                    'credentials': credentials,
                    'message': 'Token refresh successful'
                }
            else:
                logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'message': f'Token refresh failed: {response.text}',
                    'status_code': response.status_code
                }
        
        except Exception as e:
            logger.error(f"Error during token refresh: {str(e)}")
            return {
                'success': False,
                'message': f'Token refresh error: {str(e)}'
            }
    
    def is_token_expired(self, credentials):
        """Check if access token is expired"""
        try:
            if 'token_expiry' not in credentials:
                return True
            
            expiry_time = datetime.fromisoformat(credentials['token_expiry'])
            # Consider token expired if it expires within 5 minutes
            buffer_time = datetime.utcnow() + timedelta(minutes=5)
            
            return expiry_time <= buffer_time
        
        except Exception as e:
            logger.error(f"Error checking token expiry: {str(e)}")
            return True
    
    def get_valid_token(self, encrypted_credentials):
        """Get a valid access token, refreshing if necessary"""
        try:
            # Decrypt credentials
            credentials = decrypt_credentials(encrypted_credentials)
            
            # Check if token is expired
            if not self.is_token_expired(credentials):
                return {
                    'success': True,
                    'access_token': credentials['access_token'],
                    'credentials': credentials
                }
            
            # Token is expired, try to refresh
            refresh_token = credentials.get('refresh_token')
            if not refresh_token:
                return {
                    'success': False,
                    'message': 'No refresh token available, re-authorization required'
                }
            
            # Refresh the token
            refresh_result = self.refresh_token(refresh_token)
            
            if refresh_result['success']:
                return {
                    'success': True,
                    'access_token': refresh_result['credentials']['access_token'],
                    'credentials': refresh_result['credentials']
                }
            else:
                return {
                    'success': False,
                    'message': f'Token refresh failed: {refresh_result["message"]}'
                }
        
        except Exception as e:
            logger.error(f"Error getting valid token: {str(e)}")
            return {
                'success': False,
                'message': f'Token validation error: {str(e)}'
            }
    
    def test_connection(self, access_token):
        """Test the connection with Schwab API"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Test with accounts endpoint
            response = requests.get(
                'https://api.schwabapi.com/v1/accounts',
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
                    'message': f'API test failed: {response.status_code} - {response.text}'
                }
        
        except Exception as e:
            logger.error(f"Error testing Schwab connection: {str(e)}")
            return {
                'success': False,
                'message': f'Connection test error: {str(e)}'
            }