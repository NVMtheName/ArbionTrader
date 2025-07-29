"""
Enhanced Schwab Trader API Client for Arbion Platform
Production-ready integration with OAuth2 3-legged authentication flow

This module provides a complete Schwab API integration that can be used
throughout the Arbion platform for account access, balance fetching,
and trading operations.
"""

import os
import json
import time
import logging
import hashlib
import secrets
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple

import requests
from cryptography.fernet import Fernet

# Configure logging
logger = logging.getLogger(__name__)

class SchwabTraderClient:
    """
    Production-ready Schwab Trader API client with full OAuth2 support
    
    Features:
    - 3-legged OAuth2 authentication flow
    - Automatic token refresh
    - Secure token storage integration
    - Complete error handling
    - Account and balance fetching
    - Integration with Arbion's multi-user architecture
    """
    
    def __init__(self, user_id: str = None):
        self.user_id = user_id
        self.base_url = 'https://api.schwabapi.com'
        self.auth_url = 'https://api.schwabapi.com/v1/oauth/authorize'
        self.token_url = 'https://api.schwabapi.com/v1/oauth/token'
        
        # Default redirect URI for Arbion platform
        self.redirect_uri = os.environ.get('SCHWAB_REDIRECT_URI', 'https://www.arbion.ai/oauth_callback/broker')
        
        # Initialize session with proper headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Arbion-AI-Trading-Platform/1.0',
            'Accept': 'application/json'
        })
    
    def _get_client_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """Get Schwab client credentials from database or environment"""
        try:
            if self.user_id:
                # Try to get user-specific credentials from database
                from models import OAuthClientCredential
                from utils.encryption import decrypt_credentials
                
                client_cred = OAuthClientCredential.query.filter_by(
                    user_id=self.user_id,
                    provider='schwab',
                    is_active=True
                ).first()
                
                if client_cred:
                    decrypted = decrypt_credentials(client_cred.encrypted_credentials)
                    return decrypted.get('client_id'), decrypted.get('client_secret')
            
            # Fallback to environment variables
            client_id = os.environ.get('SCHWAB_CLIENT_ID')
            client_secret = os.environ.get('SCHWAB_CLIENT_SECRET')
            
            if client_id and client_secret:
                return client_id, client_secret
                
            logger.warning("No Schwab client credentials found")
            return None, None
            
        except Exception as e:
            logger.error(f"Error getting client credentials: {e}")
            return None, None
    
    def generate_authorization_url(self, state: str = None) -> Tuple[str, str]:
        """
        Generate Schwab OAuth2 authorization URL
        
        Returns:
            Tuple of (authorization_url, state_parameter)
        """
        client_id, _ = self._get_client_credentials()
        
        if not client_id:
            raise ValueError("Schwab client ID not configured")
        
        if not state:
            state = secrets.token_urlsafe(32)
        
        params = {
            'client_id': client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': 'api',
            'state': state
        }
        
        auth_url = f"{self.auth_url}?{urllib.parse.urlencode(params)}"
        logger.info(f"Generated Schwab authorization URL for user: {self.user_id}")
        
        return auth_url, state
    
    def exchange_code_for_tokens(self, authorization_code: str) -> Optional[Dict[str, Any]]:
        """
        Exchange authorization code for access and refresh tokens
        
        Args:
            authorization_code: Authorization code from OAuth callback
            
        Returns:
            Token data dictionary or None if failed
        """
        client_id, client_secret = self._get_client_credentials()
        
        if not client_id or not client_secret:
            logger.error("Schwab client credentials not available")
            return None
        
        try:
            data = {
                'grant_type': 'authorization_code',
                'code': authorization_code,
                'redirect_uri': self.redirect_uri,
                'client_id': client_id,
                'client_secret': client_secret
            }
            
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            
            logger.info("Exchanging authorization code for Schwab tokens")
            response = self.session.post(
                self.token_url, 
                data=data, 
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Add expiration timestamp
                expires_in = token_data.get('expires_in', 1800)
                token_data['expires_at'] = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
                token_data['created_at'] = datetime.utcnow().isoformat()
                
                logger.info(f"Successfully obtained Schwab tokens for user: {self.user_id}")
                return token_data
            else:
                logger.error(f"Schwab token exchange failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error exchanging code for Schwab tokens: {e}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Refresh Schwab access token using refresh token
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New token data or None if failed
        """
        client_id, client_secret = self._get_client_credentials()
        
        if not client_id or not client_secret:
            logger.error("Schwab client credentials not available")
            return None
        
        try:
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': client_id,
                'client_secret': client_secret
            }
            
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            
            logger.info("Refreshing Schwab access token")
            response = self.session.post(
                self.token_url,
                data=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Update expiration timestamp
                expires_in = token_data.get('expires_in', 1800)
                token_data['expires_at'] = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
                token_data['created_at'] = datetime.utcnow().isoformat()
                
                # Preserve refresh token if not provided in response
                if 'refresh_token' not in token_data:
                    token_data['refresh_token'] = refresh_token
                
                logger.info(f"Successfully refreshed Schwab tokens for user: {self.user_id}")
                return token_data
            else:
                logger.error(f"Schwab token refresh failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error refreshing Schwab token: {e}")
            return None
    
    def get_valid_access_token(self) -> Optional[str]:
        """
        Get valid access token, refreshing if necessary
        
        Returns:
            Valid access token or None if authentication failed
        """
        if not self.user_id:
            logger.warning("No user ID provided for token retrieval")
            return None
        
        try:
            from models import APICredential
            from utils.encryption import decrypt_credentials
            
            # Get stored credentials
            schwab_cred = APICredential.query.filter_by(
                user_id=self.user_id,
                provider='schwab',
                is_active=True
            ).first()
            
            if not schwab_cred:
                logger.warning(f"No Schwab credentials found for user: {self.user_id}")
                return None
            
            # Decrypt and parse token data
            decrypted = decrypt_credentials(schwab_cred.encrypted_credentials)
            
            if 'access_token' not in decrypted:
                logger.warning(f"No access token found for user: {self.user_id}")
                return None
            
            # Check if token is expired
            expires_at_str = decrypted.get('expires_at')
            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                # Add 5-minute buffer before expiration
                if datetime.utcnow() + timedelta(minutes=5) >= expires_at:
                    logger.info(f"Schwab token expired for user {self.user_id}, attempting refresh")
                    
                    # Try to refresh token
                    refresh_token = decrypted.get('refresh_token')
                    if refresh_token:
                        new_token_data = self.refresh_access_token(refresh_token)
                        if new_token_data:
                            # Update stored credentials
                            from utils.encryption import encrypt_credentials
                            schwab_cred.encrypted_credentials = encrypt_credentials(new_token_data)
                            
                            from app import db
                            db.session.commit()
                            
                            return new_token_data['access_token']
                    
                    logger.error(f"Failed to refresh Schwab token for user: {self.user_id}")
                    return None
            
            return decrypted['access_token']
            
        except Exception as e:
            logger.error(f"Error getting valid access token: {e}")
            return None
    
    def make_authenticated_request(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        """
        Make authenticated request to Schwab API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., '/trader/v1/accounts')
            **kwargs: Additional request parameters
            
        Returns:
            Response object or None if failed
        """
        access_token = self.get_valid_access_token()
        
        if not access_token:
            logger.error(f"No valid access token available for user: {self.user_id}")
            return None
        
        headers = kwargs.get('headers', {})
        headers.update({
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        })
        kwargs['headers'] = headers
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            
            # Handle 401 Unauthorized - try token refresh
            if response.status_code == 401:
                logger.warning(f"Received 401 for Schwab API, attempting token refresh for user: {self.user_id}")
                
                # Get fresh token and retry
                access_token = self.get_valid_access_token()
                if access_token:
                    headers['Authorization'] = f'Bearer {access_token}'
                    response = self.session.request(method, url, timeout=30, **kwargs)
            
            return response
            
        except Exception as e:
            logger.error(f"Error making Schwab API request: {e}")
            return None
    
    def get_accounts(self) -> Optional[Dict[str, Any]]:
        """
        Fetch user accounts from Schwab API
        
        Returns:
            Account data or None if failed
        """
        response = self.make_authenticated_request('GET', '/trader/v1/accounts')
        
        if response and response.status_code == 200:
            logger.info(f"Successfully fetched Schwab accounts for user: {self.user_id}")
            return response.json()
        elif response:
            logger.error(f"Failed to fetch Schwab accounts: {response.status_code} - {response.text}")
            return None
        else:
            return None
    
    def get_account_balances(self, account_hash: str = None) -> Optional[Dict[str, Any]]:
        """
        Fetch account balances from Schwab API
        
        Args:
            account_hash: Specific account hash (optional)
            
        Returns:
            Balance data or None if failed
        """
        if account_hash:
            endpoint = f'/trader/v1/accounts/{account_hash}'
        else:
            endpoint = '/trader/v1/accounts'
        
        response = self.make_authenticated_request('GET', endpoint)
        
        if response and response.status_code == 200:
            logger.info(f"Successfully fetched Schwab balances for user: {self.user_id}")
            return response.json()
        elif response:
            logger.error(f"Failed to fetch Schwab balances: {response.status_code} - {response.text}")
            return None
        else:
            return None
    
    def get_account_positions(self, account_hash: str) -> Optional[Dict[str, Any]]:
        """
        Fetch account positions from Schwab API
        
        Args:
            account_hash: Account hash identifier
            
        Returns:
            Position data or None if failed
        """
        endpoint = f'/trader/v1/accounts/{account_hash}/positions'
        response = self.make_authenticated_request('GET', endpoint)
        
        if response and response.status_code == 200:
            logger.info(f"Successfully fetched Schwab positions for user: {self.user_id}")
            return response.json()
        elif response:
            logger.error(f"Failed to fetch Schwab positions: {response.status_code} - {response.text}")
            return None
        else:
            return None
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test Schwab API connection and authentication
        
        Returns:
            Connection test results
        """
        try:
            accounts_data = self.get_accounts()
            
            if accounts_data:
                return {
                    'success': True,
                    'message': 'Schwab API connection successful',
                    'account_count': len(accounts_data) if isinstance(accounts_data, list) else 1,
                    'timestamp': datetime.utcnow().isoformat()
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to fetch accounts from Schwab API',
                    'timestamp': datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error testing Schwab connection: {e}")
            return {
                'success': False,
                'message': f'Connection test failed: {str(e)}',
                'timestamp': datetime.utcnow().isoformat()
            }