"""
E-trade OAuth 1.0a authentication handler
Manages OAuth flow for E-trade API access
"""

import json
import logging
import requests
import urllib.parse
import secrets
import time
import hashlib
import hmac
import base64
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class EtradeOAuth:
    """
    E-trade OAuth 1.0a authentication handler
    Manages the complete OAuth flow for E-trade API access
    """
    
    def __init__(self, client_key: str, client_secret: str, sandbox: bool = False):
        """
        Initialize E-trade OAuth handler
        
        Args:
            client_key: E-trade API client key
            client_secret: E-trade API client secret
            sandbox: Whether to use sandbox environment
        """
        self.client_key = client_key
        self.client_secret = client_secret
        self.sandbox = sandbox
        
        # Set base URLs based on environment
        if sandbox:
            self.base_url = "https://etwssandbox.etrade.com"
            self.oauth_base_url = "https://etwssandbox.etrade.com/oauth"
        else:
            self.base_url = "https://api.etrade.com"
            self.oauth_base_url = "https://api.etrade.com/oauth"
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Arbion-Trading-Platform/1.0',
            'Accept': 'application/json'
        })
    
    def _generate_oauth_signature(self, method: str, url: str, params: Dict[str, str], 
                                 token_secret: str = "") -> str:
        """
        Generate OAuth 1.0a signature
        
        Args:
            method: HTTP method
            url: Request URL
            params: Request parameters
            token_secret: OAuth token secret (empty for request token)
            
        Returns:
            OAuth signature
        """
        # Create signature base string
        normalized_params = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        signature_base = f"{method}&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(normalized_params, safe='')}"
        
        # Create signing key
        signing_key = f"{urllib.parse.quote(self.client_secret, safe='')}&{urllib.parse.quote(token_secret, safe='')}"
        
        # Generate signature
        signature = hmac.new(
            signing_key.encode('utf-8'),
            signature_base.encode('utf-8'),
            hashlib.sha1
        ).digest()
        
        return base64.b64encode(signature).decode('utf-8')
    
    def get_request_token(self) -> Tuple[str, str]:
        """
        Get OAuth request token (first step in OAuth flow)
        
        Returns:
            Tuple of (request_token, request_token_secret)
        """
        try:
            url = f"{self.oauth_base_url}/request_token"
            
            # OAuth parameters
            oauth_params = {
                'oauth_consumer_key': self.client_key,
                'oauth_nonce': secrets.token_hex(16),
                'oauth_signature_method': 'HMAC-SHA1',
                'oauth_timestamp': str(int(time.time())),
                'oauth_version': '1.0',
                'oauth_callback': 'oob'  # Out of band callback
            }
            
            # Generate signature
            signature = self._generate_oauth_signature('GET', url, oauth_params)
            oauth_params['oauth_signature'] = signature
            
            # Build authorization header
            auth_header = 'OAuth ' + ', '.join([f'{k}="{v}"' for k, v in oauth_params.items()])
            
            response = self.session.get(
                url,
                headers={'Authorization': auth_header},
                timeout=30
            )
            
            response.raise_for_status()
            
            # Parse response
            response_data = urllib.parse.parse_qs(response.text)
            request_token = response_data.get('oauth_token', [''])[0]
            request_token_secret = response_data.get('oauth_token_secret', [''])[0]
            
            if not request_token or not request_token_secret:
                raise Exception("Failed to get request token from E-trade")
            
            logger.info("Successfully obtained E-trade request token")
            return request_token, request_token_secret
            
        except Exception as e:
            logger.error(f"Failed to get request token: {str(e)}")
            raise
    
    def get_authorization_url(self, request_token: str) -> str:
        """
        Get authorization URL for user to approve access
        
        Args:
            request_token: OAuth request token
            
        Returns:
            Authorization URL
        """
        auth_url = f"{self.oauth_base_url}/authorize"
        params = {
            'key': self.client_key,
            'token': request_token
        }
        
        return f"{auth_url}?{urllib.parse.urlencode(params)}"
    
    def get_access_token(self, request_token: str, request_token_secret: str, 
                        verifier: str) -> Tuple[str, str]:
        """
        Exchange request token for access token (final step in OAuth flow)
        
        Args:
            request_token: OAuth request token
            request_token_secret: OAuth request token secret
            verifier: OAuth verifier code from user
            
        Returns:
            Tuple of (access_token, access_token_secret)
        """
        try:
            url = f"{self.oauth_base_url}/access_token"
            
            # OAuth parameters
            oauth_params = {
                'oauth_consumer_key': self.client_key,
                'oauth_nonce': secrets.token_hex(16),
                'oauth_signature_method': 'HMAC-SHA1',
                'oauth_timestamp': str(int(time.time())),
                'oauth_version': '1.0',
                'oauth_token': request_token,
                'oauth_verifier': verifier
            }
            
            # Generate signature
            signature = self._generate_oauth_signature('GET', url, oauth_params, request_token_secret)
            oauth_params['oauth_signature'] = signature
            
            # Build authorization header
            auth_header = 'OAuth ' + ', '.join([f'{k}="{v}"' for k, v in oauth_params.items()])
            
            response = self.session.get(
                url,
                headers={'Authorization': auth_header},
                timeout=30
            )
            
            response.raise_for_status()
            
            # Parse response
            response_data = urllib.parse.parse_qs(response.text)
            access_token = response_data.get('oauth_token', [''])[0]
            access_token_secret = response_data.get('oauth_token_secret', [''])[0]
            
            if not access_token or not access_token_secret:
                raise Exception("Failed to get access token from E-trade")
            
            logger.info("Successfully obtained E-trade access token")
            return access_token, access_token_secret
            
        except Exception as e:
            logger.error(f"Failed to get access token: {str(e)}")
            raise
    
    def test_access_token(self, access_token: str, access_token_secret: str) -> bool:
        """
        Test if access token is valid
        
        Args:
            access_token: OAuth access token
            access_token_secret: OAuth access token secret
            
        Returns:
            True if token is valid, False otherwise
        """
        try:
            from utils.etrade_api import EtradeAPIClient
            
            client = EtradeAPIClient(
                self.client_key,
                self.client_secret,
                access_token,
                access_token_secret,
                self.sandbox
            )
            
            result = client.test_connection()
            return result.get('success', False)
            
        except Exception as e:
            logger.error(f"Access token test failed: {str(e)}")
            return False
    
    def refresh_access_token(self, access_token: str, access_token_secret: str) -> Tuple[str, str]:
        """
        Refresh access token (E-trade access tokens don't expire but can be refreshed)
        
        Args:
            access_token: Current access token
            access_token_secret: Current access token secret
            
        Returns:
            Tuple of (new_access_token, new_access_token_secret)
        """
        try:
            url = f"{self.oauth_base_url}/renew_access_token"
            
            # OAuth parameters
            oauth_params = {
                'oauth_consumer_key': self.client_key,
                'oauth_nonce': secrets.token_hex(16),
                'oauth_signature_method': 'HMAC-SHA1',
                'oauth_timestamp': str(int(time.time())),
                'oauth_version': '1.0',
                'oauth_token': access_token
            }
            
            # Generate signature
            signature = self._generate_oauth_signature('GET', url, oauth_params, access_token_secret)
            oauth_params['oauth_signature'] = signature
            
            # Build authorization header
            auth_header = 'OAuth ' + ', '.join([f'{k}="{v}"' for k, v in oauth_params.items()])
            
            response = self.session.get(
                url,
                headers={'Authorization': auth_header},
                timeout=30
            )
            
            response.raise_for_status()
            
            # Parse response
            response_data = urllib.parse.parse_qs(response.text)
            new_access_token = response_data.get('oauth_token', [''])[0]
            new_access_token_secret = response_data.get('oauth_token_secret', [''])[0]
            
            if not new_access_token or not new_access_token_secret:
                raise Exception("Failed to refresh access token from E-trade")
            
            logger.info("Successfully refreshed E-trade access token")
            return new_access_token, new_access_token_secret
            
        except Exception as e:
            logger.error(f"Failed to refresh access token: {str(e)}")
            raise
    
    def revoke_access_token(self, access_token: str, access_token_secret: str) -> bool:
        """
        Revoke access token
        
        Args:
            access_token: Access token to revoke
            access_token_secret: Access token secret
            
        Returns:
            True if revocation successful, False otherwise
        """
        try:
            url = f"{self.oauth_base_url}/revoke_access_token"
            
            # OAuth parameters
            oauth_params = {
                'oauth_consumer_key': self.client_key,
                'oauth_nonce': secrets.token_hex(16),
                'oauth_signature_method': 'HMAC-SHA1',
                'oauth_timestamp': str(int(time.time())),
                'oauth_version': '1.0',
                'oauth_token': access_token
            }
            
            # Generate signature
            signature = self._generate_oauth_signature('GET', url, oauth_params, access_token_secret)
            oauth_params['oauth_signature'] = signature
            
            # Build authorization header
            auth_header = 'OAuth ' + ', '.join([f'{k}="{v}"' for k, v in oauth_params.items()])
            
            response = self.session.get(
                url,
                headers={'Authorization': auth_header},
                timeout=30
            )
            
            response.raise_for_status()
            
            logger.info("Successfully revoked E-trade access token")
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke access token: {str(e)}")
            return False