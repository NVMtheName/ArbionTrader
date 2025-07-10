"""
Schwab API Client with RFC 6750 Bearer Token Usage Compliance
Implements proper Bearer token authentication for Schwab API requests
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

class SchwabAPIClient:
    """
    Schwab API Client implementing RFC 6750 Bearer Token Usage
    
    This client handles all Schwab API interactions with proper Bearer token
    authentication following RFC 6750 standards.
    """
    
    def __init__(self, user_id: int = None):
        self.user_id = user_id
        self.base_url = 'https://api.schwabapi.com'
        self.access_token = None
        self.token_expiry = None
        
        # Load user's OAuth credentials if user_id provided
        if user_id:
            self._load_user_credentials()
    
    def _load_user_credentials(self):
        """Load user's encrypted OAuth credentials from database"""
        try:
            from models import APICredential
            from utils.encryption import decrypt_credentials
            from utils.schwab_oauth import SchwabOAuth
            
            # Find user's Schwab credentials
            credential = APICredential.query.filter_by(
                user_id=self.user_id,
                provider='schwab',
                is_active=True
            ).first()
            
            if credential:
                # Decrypt credentials
                creds = decrypt_credentials(credential.encrypted_credentials)
                
                # Initialize OAuth handler
                oauth = SchwabOAuth(user_id=self.user_id)
                
                # Get valid token (refresh if necessary)
                self.access_token = oauth.get_valid_token(credential.encrypted_credentials)
                
                # Set token expiry
                expires_at = creds.get('expires_at')
                if expires_at:
                    self.token_expiry = datetime.fromisoformat(expires_at)
                
                logger.info(f"Loaded Schwab credentials for user {self.user_id}")
            else:
                logger.warning(f"No Schwab credentials found for user {self.user_id}")
                
        except Exception as e:
            logger.error(f"Failed to load Schwab credentials: {e}")
    
    def _make_authenticated_request(self, method: str, endpoint: str, params: dict = None, data: dict = None, headers: dict = None) -> requests.Response:
        """
        Make authenticated API request using RFC 6750 Bearer Token
        
        RFC 6750 Section 2.1 - Authorization Request Header Field:
        "When sending the access token in the "Authorization" request header 
        field defined by HTTP/1.1, the client uses the "Bearer" authentication 
        scheme to transmit the access token."
        """
        if not self.access_token:
            raise ValueError("No access token available. Please authenticate first.")
        
        # Build full URL
        url = f"{self.base_url}{endpoint}"
        
        # Prepare headers with Bearer token (RFC 6750 Section 2.1)
        request_headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        # Add custom headers if provided
        if headers:
            request_headers.update(headers)
        
        # Add query parameters if provided
        if params:
            url += '?' + urlencode(params)
        
        # Prepare request data
        request_data = None
        if data:
            request_data = json.dumps(data) if isinstance(data, dict) else data
        
        # Log request details (excluding sensitive token)
        logger.info(f"Making {method} request to {url}")
        logger.debug(f"Request headers: {dict((k, v if k != 'Authorization' else 'Bearer ***') for k, v in request_headers.items())}")
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=request_headers,
                data=request_data,
                timeout=30
            )
            
            # Log response status
            logger.info(f"Response status: {response.status_code}")
            
            # Handle bearer token specific errors (RFC 6750 Section 3.1)
            if response.status_code == 401:
                self._handle_bearer_token_error(response)
            
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise
    
    def _handle_bearer_token_error(self, response: requests.Response):
        """
        Handle bearer token errors according to RFC 6750 Section 3.1
        
        When a request fails, the resource server responds using the
        appropriate HTTP status code and includes one of the following
        error codes in the response: invalid_request, invalid_token, insufficient_scope
        """
        try:
            error_data = response.json()
            error_code = error_data.get('error', 'unknown_error')
            error_description = error_data.get('error_description', 'Unknown error')
            
            logger.error(f"Bearer token error: {error_code} - {error_description}")
            
            if error_code == 'invalid_token':
                logger.info("Token is invalid or expired. Attempting to refresh...")
                self._refresh_token()
            elif error_code == 'insufficient_scope':
                logger.error("Insufficient scope for this request")
                raise ValueError(f"Insufficient scope: {error_description}")
            else:
                logger.error(f"Bearer token authentication failed: {error_description}")
                raise ValueError(f"Authentication failed: {error_description}")
                
        except json.JSONDecodeError:
            logger.error("Failed to parse error response")
            raise ValueError("Bearer token authentication failed")
    
    def _refresh_token(self):
        """Refresh the access token using refresh token"""
        try:
            from utils.schwab_oauth import SchwabOAuth
            from models import APICredential
            from utils.encryption import decrypt_credentials, encrypt_credentials
            from app import db
            
            # Get current credentials
            credential = APICredential.query.filter_by(
                user_id=self.user_id,
                provider='schwab',
                is_active=True
            ).first()
            
            if not credential:
                raise ValueError("No Schwab credentials found for token refresh")
            
            # Decrypt current credentials
            creds = decrypt_credentials(credential.encrypted_credentials)
            refresh_token = creds.get('refresh_token')
            
            if not refresh_token:
                raise ValueError("No refresh token available")
            
            # Initialize OAuth handler and refresh token
            oauth = SchwabOAuth(user_id=self.user_id)
            refresh_result = oauth.refresh_token(refresh_token)
            
            if refresh_result['success']:
                # Update stored credentials
                new_creds = refresh_result['credentials']
                credential.encrypted_credentials = encrypt_credentials(new_creds)
                credential.updated_at = datetime.utcnow()
                db.session.commit()
                
                # Update client token
                self.access_token = new_creds['access_token']
                self.token_expiry = datetime.fromisoformat(new_creds['expires_at'])
                
                logger.info("Successfully refreshed Schwab access token")
            else:
                raise ValueError("Token refresh failed")
                
        except Exception as e:
            logger.error(f"Failed to refresh token: {e}")
            raise
    
    # Account Information APIs
    def get_accounts(self) -> Dict[str, Any]:
        """Get user's Schwab accounts"""
        response = self._make_authenticated_request('GET', '/trader/v1/accounts')
        response.raise_for_status()
        return response.json()
    
    def get_account_details(self, account_id: str) -> Dict[str, Any]:
        """Get detailed information for a specific account"""
        response = self._make_authenticated_request('GET', f'/trader/v1/accounts/{account_id}')
        response.raise_for_status()
        return response.json()
    
    def get_account_positions(self, account_id: str) -> Dict[str, Any]:
        """Get positions for a specific account"""
        response = self._make_authenticated_request('GET', f'/trader/v1/accounts/{account_id}/positions')
        response.raise_for_status()
        return response.json()
    
    # Market Data APIs
    def get_quotes(self, symbols: List[str]) -> Dict[str, Any]:
        """Get quotes for multiple symbols"""
        params = {'symbols': ','.join(symbols)}
        response = self._make_authenticated_request('GET', '/marketdata/v1/quotes', params=params)
        response.raise_for_status()
        return response.json()
    
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get quote for a single symbol"""
        response = self._make_authenticated_request('GET', f'/marketdata/v1/quotes/{symbol}')
        response.raise_for_status()
        return response.json()
    
    def get_option_chains(self, symbol: str, contract_type: str = None, strike_count: int = None) -> Dict[str, Any]:
        """Get option chains for a symbol"""
        params = {}
        if contract_type:
            params['contractType'] = contract_type
        if strike_count:
            params['strikeCount'] = strike_count
            
        response = self._make_authenticated_request('GET', f'/marketdata/v1/chains/{symbol}', params=params)
        response.raise_for_status()
        return response.json()
    
    # Trading APIs
    def place_order(self, account_id: str, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Place a trading order"""
        response = self._make_authenticated_request('POST', f'/trader/v1/accounts/{account_id}/orders', data=order_data)
        response.raise_for_status()
        return response.json()
    
    def get_orders(self, account_id: str, from_date: str = None, to_date: str = None) -> Dict[str, Any]:
        """Get orders for an account"""
        params = {}
        if from_date:
            params['fromEnteredTime'] = from_date
        if to_date:
            params['toEnteredTime'] = to_date
            
        response = self._make_authenticated_request('GET', f'/trader/v1/accounts/{account_id}/orders', params=params)
        response.raise_for_status()
        return response.json()
    
    def cancel_order(self, account_id: str, order_id: str) -> bool:
        """Cancel an order"""
        response = self._make_authenticated_request('DELETE', f'/trader/v1/accounts/{account_id}/orders/{order_id}')
        return response.status_code == 200
    
    # Utility Methods
    def test_connection(self) -> Dict[str, Any]:
        """Test API connection and bearer token validity"""
        try:
            accounts = self.get_accounts()
            return {
                'success': True,
                'message': 'Connection successful',
                'accounts_count': len(accounts) if isinstance(accounts, list) else 0
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Connection failed: {str(e)}'
            }
    
    def get_user_preferences(self) -> Dict[str, Any]:
        """Get user preferences"""
        response = self._make_authenticated_request('GET', '/trader/v1/userPreference')
        response.raise_for_status()
        return response.json()