"""
Enhanced Schwab Trader API Client for Arbion Platform
Production-ready integration with OAuth2 3-legged authentication flow

FIXED VERSION - Corrects the credential loading bug where the code tried to
decrypt OAuthClientCredential.encrypted_credentials which doesn't exist.

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
        """
        Get Schwab client credentials from database or environment
        
        FIXED: The OAuthClientCredential model stores client_id and client_secret
        as plain text fields, NOT as encrypted_credentials. The previous code
        tried to decrypt a field that doesn't exist, causing failures.
        """
        try:
            if self.user_id:
                # Try to get user-specific credentials from database
                from models import OAuthClientCredential
                
                client_cred = OAuthClientCredential.query.filter_by(
                    user_id=self.user_id,
                    provider='schwab',
                    is_active=True
                ).first()
                
                if client_cred:
                    # FIXED: Access plain text fields directly instead of trying to decrypt
                    logger.info(f"Found Schwab client credentials for user {self.user_id}")
                    return client_cred.client_id, client_cred.client_secret
            
            # Fallback to environment variables (check both naming conventions)
            client_id = os.environ.get('SCHWAB_APP_KEY') or os.environ.get('SCHWAB_CLIENT_ID')
            client_secret = os.environ.get('SCHWAB_APP_SECRET') or os.environ.get('SCHWAB_CLIENT_SECRET')
            
            if client_id and client_secret:
                logger.info("Using Schwab credentials from environment variables")
                return client_id, client_secret
                
            logger.warning("No Schwab client credentials found in database or environment")
            return None, None
            
        except Exception as e:
            logger.error(f"Error getting Schwab client credentials: {e}")
            import traceback
            traceback.print_exc()
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
            logger.error("Schwab client credentials not available for token refresh")
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
            
            # Get stored credentials (these are the OAuth TOKENS, not client credentials)
            schwab_cred = APICredential.query.filter_by(
                user_id=self.user_id,
                provider='schwab',
                is_active=True
            ).first()
            
            if not schwab_cred:
                logger.warning(f"No Schwab API credentials (tokens) found for user: {self.user_id}")
                return None
            
            # Decrypt and parse token data
            try:
                decrypted = decrypt_credentials(schwab_cred.encrypted_credentials)
            except Exception as e:
                logger.error(f"Failed to decrypt Schwab credentials for user {self.user_id}: {e}")
                return None
            
            if 'access_token' not in decrypted:
                logger.warning(f"No access_token in decrypted credentials for user: {self.user_id}")
                return None
            
            # Check if token is expired
            expires_at_str = decrypted.get('expires_at') or decrypted.get('token_expiry')
            if expires_at_str:
                try:
                    # Handle various datetime formats
                    if expires_at_str.endswith('Z'):
                        expires_at_str = expires_at_str[:-1] + '+00:00'
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
                                from app import db
                                
                                schwab_cred.encrypted_credentials = encrypt_credentials(new_token_data)
                                schwab_cred.updated_at = datetime.utcnow()
                                db.session.commit()
                                
                                logger.info(f"Successfully refreshed and saved Schwab tokens for user {self.user_id}")
                                return new_token_data['access_token']
                        
                        logger.error(f"Failed to refresh Schwab token for user: {self.user_id}")
                        return None
                except Exception as e:
                    logger.warning(f"Error parsing token expiry for user {self.user_id}: {e}")
                    # Continue with existing token
            
            return decrypted['access_token']
            
        except Exception as e:
            logger.error(f"Error getting valid access token for user {self.user_id}: {e}")
            import traceback
            traceback.print_exc()
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
            logger.info(f"Making Schwab API request: {method} {endpoint}")
            response = self.session.request(method, url, timeout=30, **kwargs)
            
            logger.info(f"Schwab API response: {response.status_code}")
            
            # Handle 401 Unauthorized - try token refresh
            if response.status_code == 401:
                logger.warning(f"Received 401 for Schwab API, attempting token refresh for user: {self.user_id}")
                
                # Force token refresh by getting fresh token
                from models import APICredential
                from utils.encryption import decrypt_credentials
                
                schwab_cred = APICredential.query.filter_by(
                    user_id=self.user_id,
                    provider='schwab',
                    is_active=True
                ).first()
                
                if schwab_cred:
                    decrypted = decrypt_credentials(schwab_cred.encrypted_credentials)
                    refresh_token = decrypted.get('refresh_token')
                    
                    if refresh_token:
                        new_token_data = self.refresh_access_token(refresh_token)
                        if new_token_data:
                            # Update stored credentials
                            from utils.encryption import encrypt_credentials
                            from app import db
                            
                            schwab_cred.encrypted_credentials = encrypt_credentials(new_token_data)
                            db.session.commit()
                            
                            # Retry request with new token
                            headers['Authorization'] = f'Bearer {new_token_data["access_token"]}'
                            response = self.session.request(method, url, timeout=30, **kwargs)
                            logger.info(f"Retry response after token refresh: {response.status_code}")
            
            return response
            
        except Exception as e:
            logger.error(f"Error making Schwab API request: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_accounts(self) -> Optional[Dict[str, Any]]:
        """
        Fetch user accounts from Schwab API
        
        Returns:
            Account data or None if failed
        """
        response = self.make_authenticated_request('GET', '/trader/v1/accounts')
        
        if response and response.status_code == 200:
            data = response.json()
            logger.info(f"Successfully fetched Schwab accounts for user: {self.user_id}")
            return data
        elif response:
            logger.error(f"Failed to fetch Schwab accounts: {response.status_code} - {response.text}")
            return None
        else:
            logger.error("No response from Schwab API")
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
        endpoint = f'/trader/v1/accounts/{account_hash}?fields=positions'
        response = self.make_authenticated_request('GET', endpoint)
        
        if response and response.status_code == 200:
            logger.info(f"Successfully fetched Schwab positions for user: {self.user_id}")
            return response.json()
        elif response:
            logger.error(f"Failed to fetch Schwab positions: {response.status_code} - {response.text}")
            return None
        else:
            return None
    
    def place_order(self, account_hash: str, order_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Place a trading order
        
        Args:
            account_hash: Account hash identifier
            order_data: Order specification dictionary
            
        Returns:
            Order response or None if failed
        """
        endpoint = f'/trader/v1/accounts/{account_hash}/orders'
        response = self.make_authenticated_request(
            'POST', 
            endpoint, 
            json=order_data,
            headers={'Content-Type': 'application/json'}
        )
        
        if response and response.status_code in [200, 201]:
            logger.info(f"Successfully placed Schwab order for user: {self.user_id}")
            return response.json() if response.text else {'success': True}
        elif response:
            logger.error(f"Failed to place Schwab order: {response.status_code} - {response.text}")
            return None
        else:
            return None
    
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get market quote for a symbol
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Quote data or None if failed
        """
        endpoint = f'/marketdata/v1/quotes?symbols={symbol}'
        response = self.make_authenticated_request('GET', endpoint)
        
        if response and response.status_code == 200:
            return response.json()
        elif response:
            logger.error(f"Failed to get quote for {symbol}: {response.status_code}")
            return None
        else:
            return None
