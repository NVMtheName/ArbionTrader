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
    """Coinbase OAuth2 integration for secure authentication"""
    
    def __init__(self):
        self.client_id = os.environ.get('COINBASE_CLIENT_ID')
        self.client_secret = os.environ.get('COINBASE_CLIENT_SECRET')
        self.redirect_uri = os.environ.get('COINBASE_REDIRECT_URI', 'https://www.arbion.ai/oauth_callback/coinbase')
        self.auth_url = 'https://www.coinbase.com/oauth/authorize'
        self.token_url = 'https://api.coinbase.com/oauth/token'
        self.api_base_url = 'https://api.coinbase.com/v2'
        
        if not self.client_id or not self.client_secret:
            logger.warning("Coinbase OAuth2 credentials not configured")
    
    def get_authorization_url(self):
        """Generate authorization URL with state parameter"""
        try:
            if not self.client_id:
                raise ValueError("Coinbase client ID not configured")
            
            # Generate secure state parameter
            state = secrets.token_urlsafe(32)
            session['coinbase_oauth_state'] = state
            
            # Build authorization URL with required scopes
            auth_params = {
                'response_type': 'code',
                'client_id': self.client_id,
                'redirect_uri': self.redirect_uri,
                'state': state,
                'scope': 'wallet:accounts:read,wallet:transactions:read'
            }
            
            auth_url = f"{self.auth_url}?{urlencode(auth_params)}"
            
            logger.info("Generated Coinbase authorization URL")
            return auth_url
        
        except Exception as e:
            logger.error(f"Error generating authorization URL: {str(e)}")
            raise
    
    def exchange_code_for_token(self, auth_code, state):
        """Exchange authorization code for access token"""
        try:
            if not self.client_id or not self.client_secret:
                raise ValueError("Coinbase OAuth2 credentials not configured")
            
            # Validate state parameter
            stored_state = session.get('coinbase_oauth_state')
            if not stored_state or stored_state != state:
                raise ValueError("Invalid state parameter")
            
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
                
                # Prepare credentials for storage
                credentials = {
                    'access_token': token_info['access_token'],
                    'refresh_token': token_info.get('refresh_token'),
                    'token_expiry': expiry_time.isoformat(),
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'scope': token_info.get('scope', 'wallet:accounts:read,wallet:transactions:read')
                }
                
                # Clean up session
                session.pop('coinbase_oauth_state', None)
                
                logger.info("Successfully exchanged code for Coinbase token")
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
            if not self.client_id or not self.client_secret:
                raise ValueError("Coinbase OAuth2 credentials not configured")
            
            refresh_data = {
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
                data=refresh_data,
                timeout=30
            )
            
            if response.status_code == 200:
                token_info = response.json()
                
                # Calculate expiry time
                expires_in = token_info.get('expires_in', 7200)
                expiry_time = datetime.utcnow() + timedelta(seconds=expires_in)
                
                # Prepare updated credentials
                credentials = {
                    'access_token': token_info['access_token'],
                    'refresh_token': token_info.get('refresh_token', refresh_token),
                    'token_expiry': expiry_time.isoformat(),
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'scope': token_info.get('scope', 'wallet:accounts:read,wallet:transactions:read')
                }
                
                logger.info("Successfully refreshed Coinbase token")
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
        """Test the connection with Coinbase API"""
        try:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            # Test with accounts endpoint
            response = requests.get(
                f'{self.api_base_url}/accounts',
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                accounts_data = response.json()
                account_count = len(accounts_data.get('data', []))
                
                return {
                    'success': True,
                    'message': f'Coinbase API connection successful. Found {account_count} accounts.'
                }
            else:
                return {
                    'success': False,
                    'message': f'API test failed: {response.status_code} - {response.text}'
                }
        
        except Exception as e:
            logger.error(f"Error testing Coinbase connection: {str(e)}")
            return {
                'success': False,
                'message': f'Connection test error: {str(e)}'
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
                return {
                    'success': True,
                    'data': response.json()
                }
            else:
                return {
                    'success': False,
                    'message': f'Failed to fetch accounts: {response.text}'
                }
        
        except Exception as e:
            logger.error(f"Error fetching accounts: {str(e)}")
            return {
                'success': False,
                'message': f'Account fetch error: {str(e)}'
            }
    
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
                return {
                    'success': True,
                    'data': response.json()
                }
            else:
                return {
                    'success': False,
                    'message': f'Failed to fetch transactions: {response.text}'
                }
        
        except Exception as e:
            logger.error(f"Error fetching transactions: {str(e)}")
            return {
                'success': False,
                'message': f'Transaction fetch error: {str(e)}'
            }