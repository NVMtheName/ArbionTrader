"""
Token Manager for persistent API connections
Handles automatic token refresh and persistent authentication
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from models import APICredential, User
from utils.encryption import decrypt_credentials, encrypt_credentials
from utils.schwab_oauth import SchwabOAuth
from utils.coinbase_oauth import CoinbaseOAuth
from app import db

logger = logging.getLogger(__name__)

class TokenManager:
    """
    Manages API tokens for persistent connections
    Handles automatic refresh and background authentication
    """
    
    @staticmethod
    def get_valid_token(user_id: int, provider: str) -> Optional[Dict[str, Any]]:
        """
        Get a valid token for the provider, refreshing if necessary
        
        Args:
            user_id: User ID
            provider: API provider (schwab, coinbase)
            
        Returns:
            Valid token data or None
        """
        try:
            # Get stored credentials
            credential = APICredential.query.filter_by(
                user_id=user_id,
                provider=provider,
                is_active=True
            ).first()
            
            if not credential:
                logger.warning(f"No credentials found for user {user_id}, provider {provider}")
                return None
            
            # Decrypt credentials
            credentials = decrypt_credentials(credential.encrypted_credentials)
            
            # Check if token needs refresh
            if TokenManager._needs_refresh(credentials):
                logger.info(f"Token needs refresh for user {user_id}, provider {provider}")

                # Refresh token
                new_credentials = TokenManager._refresh_token(user_id, provider, credentials)

                if new_credentials and isinstance(new_credentials, dict) and new_credentials.get('reauth_required'):
                    # Permanent failure - deactivate credential
                    credential.is_active = False
                    credential.test_status = 'failed'
                    credential.updated_at = datetime.utcnow()
                    db.session.commit()
                    logger.warning(
                        f"Deactivated {provider} credential for user {user_id}: "
                        f"{new_credentials.get('message')}. User must re-authenticate."
                    )
                    return None
                elif new_credentials and 'access_token' in new_credentials:
                    # Update stored credentials
                    credential.encrypted_credentials = encrypt_credentials(new_credentials)
                    credential.updated_at = datetime.utcnow()
                    db.session.commit()

                    logger.info(f"Token refreshed successfully for user {user_id}, provider {provider}")
                    return new_credentials
                else:
                    logger.error(f"Failed to refresh token for user {user_id}, provider {provider}")
                    return None
            else:
                logger.info(f"Token is still valid for user {user_id}, provider {provider}")
                return credentials
                
        except Exception as e:
            logger.error(f"Error getting valid token for user {user_id}, provider {provider}: {str(e)}")
            return None
    
    @staticmethod
    def _needs_refresh(credentials: Dict[str, Any]) -> bool:
        """
        Check if token needs to be refreshed
        
        Args:
            credentials: Token credentials
            
        Returns:
            True if token needs refresh
        """
        try:
            if 'expires_at' not in credentials:
                logger.warning("No expiration time found in credentials")
                return True
            
            expires_at = datetime.fromisoformat(credentials['expires_at'])
            current_time = datetime.utcnow()
            
            # Refresh if token expires within 5 minutes
            buffer_time = timedelta(minutes=5)
            needs_refresh = current_time + buffer_time >= expires_at
            
            if needs_refresh:
                logger.info(f"Token expires at {expires_at}, current time {current_time} - needs refresh")
            
            return needs_refresh
            
        except Exception as e:
            logger.error(f"Error checking token expiration: {str(e)}")
            return True
    
    @staticmethod
    def _refresh_token(user_id: int, provider: str, credentials: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Refresh token for the specified provider
        
        Args:
            user_id: User ID
            provider: API provider
            credentials: Current credentials
            
        Returns:
            New credentials or None
        """
        try:
            if provider == 'schwab':
                return TokenManager._refresh_schwab_token(user_id, credentials)
            elif provider == 'coinbase':
                return TokenManager._refresh_coinbase_token(user_id, credentials)
            else:
                logger.error(f"Unknown provider for token refresh: {provider}")
                return None
                
        except Exception as e:
            logger.error(f"Error refreshing token for provider {provider}: {str(e)}")
            return None
    
    @staticmethod
    def _refresh_schwab_token(user_id: int, credentials: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Refresh Schwab token

        Args:
            user_id: User ID
            credentials: Current credentials

        Returns:
            Dict with 'credentials' key on success, or dict with 'reauth_required' key on permanent failure, or None
        """
        try:
            refresh_token = credentials.get('refresh_token')
            if not refresh_token:
                logger.error("No refresh token available for Schwab")
                return {'reauth_required': True, 'message': 'No refresh token available. Please re-authenticate with Schwab.'}

            # Use SchwabOAuth to refresh token
            schwab_oauth = SchwabOAuth(user_id=user_id)
            refresh_result = schwab_oauth.refresh_token(refresh_token)

            if refresh_result and refresh_result.get('success'):
                logger.info(f"Schwab token refreshed successfully for user {user_id}")
                return refresh_result.get('credentials')
            else:
                error_msg = refresh_result.get('message', 'Unknown error')
                logger.error(f"Failed to refresh Schwab token: {error_msg}")
                if refresh_result and refresh_result.get('reauth_required'):
                    return {'reauth_required': True, 'message': error_msg}
                return None

        except Exception as e:
            logger.error(f"Error refreshing Schwab token: {str(e)}")
            return None

    @staticmethod
    def _refresh_coinbase_token(user_id: int, credentials: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Refresh Coinbase token

        Args:
            user_id: User ID
            credentials: Current credentials

        Returns:
            Dict with 'credentials' key on success, or dict with 'reauth_required' key on permanent failure, or None
        """
        try:
            refresh_token = credentials.get('refresh_token')
            if not refresh_token:
                logger.error("No refresh token available for Coinbase")
                return {'reauth_required': True, 'message': 'No refresh token available. Please re-authenticate with Coinbase.'}

            # Use CoinbaseOAuth to refresh token
            coinbase_oauth = CoinbaseOAuth(user_id=user_id)
            refresh_result = coinbase_oauth.refresh_token(refresh_token)

            if refresh_result and refresh_result.get('success'):
                logger.info(f"Coinbase token refreshed successfully for user {user_id}")
                return refresh_result.get('credentials')
            else:
                error_msg = refresh_result.get('message', 'Unknown error')
                logger.error(f"Failed to refresh Coinbase token: {error_msg}")
                if refresh_result and refresh_result.get('reauth_required'):
                    return {'reauth_required': True, 'message': error_msg}
                return None

        except Exception as e:
            logger.error(f"Error refreshing Coinbase token: {str(e)}")
            return None
    
    @staticmethod
    def validate_all_tokens():
        """
        Validate and refresh all tokens for all active users
        This method is called by background tasks

        Returns:
            dict with counts and list of credentials requiring re-authentication
        """
        result = {
            'refreshed': 0,
            'errors': 0,
            'deactivated': 0,
            'reauth_required': []
        }

        try:
            logger.info("Starting token validation for all users")

            # Get all active API credentials
            credentials = APICredential.query.filter_by(is_active=True).all()

            for credential in credentials:
                try:
                    provider = credential.provider
                    user_id = credential.user_id

                    # Skip OpenAI as it doesn't use refresh tokens
                    if provider == 'openai':
                        continue

                    # Check if token needs refresh
                    current_creds = decrypt_credentials(credential.encrypted_credentials)

                    if TokenManager._needs_refresh(current_creds):
                        new_creds = TokenManager._refresh_token(user_id, provider, current_creds)

                        if new_creds and isinstance(new_creds, dict) and new_creds.get('reauth_required'):
                            # Permanent failure - deactivate to stop repeated retries
                            credential.is_active = False
                            credential.test_status = 'failed'
                            credential.updated_at = datetime.utcnow()
                            result['deactivated'] += 1
                            result['reauth_required'].append({
                                'user_id': user_id,
                                'provider': provider,
                                'reason': new_creds.get('message', 'Re-authentication required')
                            })
                            logger.warning(
                                f"Deactivated {provider} credential for user {user_id}: "
                                f"{new_creds.get('message')}. User must re-authenticate."
                            )
                        elif new_creds and 'access_token' in new_creds:
                            credential.encrypted_credentials = encrypt_credentials(new_creds)
                            credential.updated_at = datetime.utcnow()
                            credential.test_status = 'success'
                            result['refreshed'] += 1
                            logger.info(f"Refreshed token for user {user_id}, provider {provider}")
                        else:
                            # Temporary failure - keep active for retry
                            credential.test_status = 'failed'
                            result['errors'] += 1
                            logger.error(f"Failed to refresh token for user {user_id}, provider {provider} (will retry)")

                except Exception as e:
                    logger.error(f"Error processing credential {credential.id}: {str(e)}")
                    result['errors'] += 1

            # Commit all changes
            db.session.commit()

            # Log summary
            summary_parts = [f"{result['refreshed']} refreshed", f"{result['errors']} errors"]
            if result['deactivated'] > 0:
                summary_parts.append(f"{result['deactivated']} deactivated (re-auth required)")
            logger.info(f"Token validation complete: {', '.join(summary_parts)}")

            # Log each credential that needs re-authentication
            for reauth in result['reauth_required']:
                logger.warning(
                    f"ACTION REQUIRED: User {reauth['user_id']} must re-authenticate with "
                    f"{reauth['provider']}: {reauth['reason']}"
                )

        except Exception as e:
            logger.error(f"Error during token validation: {str(e)}")
            db.session.rollback()

        return result
    
    @staticmethod
    def get_schwab_api_client(user_id: int):
        """
        Get a Schwab API client with valid token
        
        Args:
            user_id: User ID
            
        Returns:
            SchwabAPIClient instance or None
        """
        try:
            from utils.schwab_api import SchwabAPIClient
            
            credentials = TokenManager.get_valid_token(user_id, 'schwab')
            if not credentials:
                logger.error(f"No valid Schwab credentials for user {user_id}")
                return None
            
            access_token = credentials.get('access_token')
            if not access_token:
                logger.error(f"No access token in Schwab credentials for user {user_id}")
                return None
            
            return SchwabAPIClient(access_token)
            
        except Exception as e:
            logger.error(f"Error creating Schwab API client for user {user_id}: {str(e)}")
            return None
    
    @staticmethod
    def get_coinbase_api_client(user_id: int):
        """
        Get a Coinbase API client with valid token
        
        Args:
            user_id: User ID
            
        Returns:
            CoinbaseAPIClient instance or None
        """
        try:
            from utils.coinbase_connector import CoinbaseConnector
            
            credentials = TokenManager.get_valid_token(user_id, 'coinbase')
            if not credentials:
                logger.error(f"No valid Coinbase credentials for user {user_id}")
                return None
            
            access_token = credentials.get('access_token')
            if not access_token:
                logger.error(f"No access token in Coinbase credentials for user {user_id}")
                return None
            
            # Create Coinbase connector with OAuth token
            return CoinbaseConnector(
                api_key=access_token,
                secret='',  # OAuth doesn't use secret
                passphrase='',  # OAuth doesn't use passphrase
                sandbox=False,
                oauth_mode=True
            )
            
        except Exception as e:
            logger.error(f"Error creating Coinbase API client for user {user_id}: {str(e)}")
            return None