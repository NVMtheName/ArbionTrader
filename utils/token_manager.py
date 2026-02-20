"""
Token Manager for persistent API connections.

Handles automatic token refresh with:
- Retry with exponential backoff for transient errors (5xx, timeouts).
- State machine: active -> refreshing -> active (happy) or reauth_required (hard failure).
- Token rotation: if the provider returns a new refresh_token, it is persisted
  immediately to avoid stale-token failures (critical for Coinbase).
- API keys are never refreshed or deactivated.

NEVER sets is_active=False on a credential — the record must remain visible so
the UI can show a "Reconnect" CTA with the exact provider error.
"""

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

# Providers that use OAuth and require refresh
OAUTH_PROVIDERS = {'schwab', 'coinbase'}

# Retry configuration for transient failures
MAX_RETRIES = 3
RETRY_BASE_DELAY_SECONDS = 2  # 2s, 4s, 8s


class TokenManager:
    """
    Manages API tokens for persistent connections.
    Handles automatic refresh and background authentication.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def get_valid_token(user_id: int, provider: str) -> Optional[Dict[str, Any]]:
        """
        Get a valid token for the provider, refreshing if necessary.

        Returns:
            - Valid credentials dict on success.
            - Dict with 'reauth_required': True if the provider requires re-auth.
            - None on transient failure (caller should retry later).
        """
        try:
            credential = APICredential.query.filter_by(
                user_id=user_id,
                provider=provider,
                is_active=True,
            ).first()

            if not credential:
                logger.warning(f"No active credentials for user {user_id}, provider {provider}")
                return None

            # API keys never expire — return immediately
            if credential.is_api_key() or provider not in OAUTH_PROVIDERS:
                creds = decrypt_credentials(credential.encrypted_credentials)
                return creds

            # If credential already marked as needing reauth, tell the caller
            if credential.needs_reauth():
                return {
                    'reauth_required': True,
                    'message': credential.last_error or f'Please reconnect your {provider} account.',
                }

            creds = decrypt_credentials(credential.encrypted_credentials)

            if not TokenManager._needs_refresh(creds):
                return creds

            logger.info(f"Token needs refresh for user {user_id}, provider {provider}")

            # Attempt refresh with retry
            result = TokenManager._refresh_with_retry(user_id, provider, credential, creds)
            return result

        except Exception as e:
            logger.error(f"Error getting valid token for user {user_id}, provider {provider}: {e}")
            return None

    @staticmethod
    def validate_all_tokens() -> Dict[str, Any]:
        """
        Validate and refresh all tokens for all active users.
        Called by the token_maintenance background task.

        Returns:
            dict with counts and list of credentials requiring re-authentication.
        """
        result = {
            'refreshed': 0,
            'errors': 0,
            'reauth_required': [],
            'skipped_api_keys': 0,
        }

        try:
            logger.info("Starting token validation for all users")

            credentials = APICredential.query.filter_by(is_active=True).all()

            for credential in credentials:
                try:
                    provider = credential.provider
                    user_id = credential.user_id

                    # Skip non-OAuth providers (API keys, OpenAI, etc.)
                    if credential.is_api_key() or provider not in OAUTH_PROVIDERS:
                        result['skipped_api_keys'] += 1
                        continue

                    # Skip credentials already flagged for reauth
                    if credential.needs_reauth():
                        result['reauth_required'].append({
                            'user_id': user_id,
                            'provider': provider,
                            'reason': credential.last_error or 'Re-authentication required',
                        })
                        continue

                    current_creds = decrypt_credentials(credential.encrypted_credentials)

                    if not TokenManager._needs_refresh(current_creds):
                        continue  # Token is still valid

                    # Attempt refresh with retry
                    new_creds = TokenManager._refresh_with_retry(
                        user_id, provider, credential, current_creds
                    )

                    if new_creds and isinstance(new_creds, dict):
                        if new_creds.get('reauth_required'):
                            result['reauth_required'].append({
                                'user_id': user_id,
                                'provider': provider,
                                'reason': new_creds.get('message', 'Re-authentication required'),
                            })
                        elif 'access_token' in new_creds:
                            result['refreshed'] += 1
                        else:
                            result['errors'] += 1
                    else:
                        result['errors'] += 1

                except Exception as e:
                    logger.error(f"Error processing credential {credential.id}: {e}")
                    result['errors'] += 1

            # Single commit for all changes made during this cycle
            db.session.commit()

            # Log summary
            parts = [f"{result['refreshed']} refreshed", f"{result['errors']} errors"]
            if result['reauth_required']:
                parts.append(f"{len(result['reauth_required'])} need reauth")
            if result['skipped_api_keys']:
                parts.append(f"{result['skipped_api_keys']} API-key skipped")
            logger.info(f"Token validation complete: {', '.join(parts)}")

            for reauth in result['reauth_required']:
                logger.warning(
                    f"ACTION REQUIRED: User {reauth['user_id']} must reconnect "
                    f"{reauth['provider']}: {reauth['reason']}"
                )

        except Exception as e:
            logger.error(f"Error during token validation: {e}")
            db.session.rollback()

        return result

    # ------------------------------------------------------------------
    # Convenience client factories
    # ------------------------------------------------------------------

    @staticmethod
    def get_schwab_api_client(user_id: int):
        """Get a SchwabAPIClient with a valid token."""
        try:
            from utils.schwab_api import SchwabAPIClient

            credentials = TokenManager.get_valid_token(user_id, 'schwab')
            if not credentials or credentials.get('reauth_required'):
                logger.error(f"No valid Schwab credentials for user {user_id}")
                return None

            access_token = credentials.get('access_token')
            if not access_token:
                logger.error(f"No access token in Schwab credentials for user {user_id}")
                return None

            return SchwabAPIClient(access_token)

        except Exception as e:
            logger.error(f"Error creating Schwab API client for user {user_id}: {e}")
            return None

    @staticmethod
    def get_coinbase_api_client(user_id: int):
        """Get a CoinbaseConnector with a valid token."""
        try:
            from utils.coinbase_connector import CoinbaseConnector

            credentials = TokenManager.get_valid_token(user_id, 'coinbase')
            if not credentials or credentials.get('reauth_required'):
                logger.error(f"No valid Coinbase credentials for user {user_id}")
                return None

            access_token = credentials.get('access_token')
            if not access_token:
                logger.error(f"No access token in Coinbase credentials for user {user_id}")
                return None

            return CoinbaseConnector(
                api_key=access_token,
                secret='',
                passphrase='',
                sandbox=False,
                oauth_mode=True,
            )

        except Exception as e:
            logger.error(f"Error creating Coinbase API client for user {user_id}: {e}")
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _needs_refresh(credentials: Dict[str, Any]) -> bool:
        """Check if token needs to be refreshed (5-minute buffer)."""
        try:
            if 'expires_at' not in credentials:
                return True

            expires_at = datetime.fromisoformat(credentials['expires_at'])
            return datetime.utcnow() + timedelta(minutes=5) >= expires_at

        except Exception as e:
            logger.error(f"Error checking token expiration: {e}")
            return True

    @staticmethod
    def _refresh_with_retry(
        user_id: int,
        provider: str,
        credential: APICredential,
        current_creds: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt token refresh with exponential backoff.

        On success: persists new tokens, marks credential active, returns creds.
        On hard failure: marks credential reauth_required, returns reauth dict.
        On transient failure after all retries: increments failure counter, returns None.
        """
        refresh_token_value = current_creds.get('refresh_token')
        if not refresh_token_value:
            logger.error(f"No refresh token for user {user_id}, provider {provider}")
            credential.mark_refresh_failure(
                f'No refresh token stored. Please reconnect your {provider} account.',
                is_hard_failure=True,
            )
            db.session.commit()
            return {
                'reauth_required': True,
                'message': f'No refresh token stored. Please reconnect your {provider} account.',
            }

        credential.status = 'refreshing'
        last_result = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                refresh_result = TokenManager._call_provider_refresh(
                    user_id, provider, refresh_token_value,
                )

                if refresh_result and refresh_result.get('success'):
                    # --- Success ---
                    new_creds = refresh_result['credentials']
                    credential.encrypted_credentials = encrypt_credentials(new_creds)
                    credential.mark_refresh_success()
                    db.session.commit()
                    logger.info(
                        f"Token refreshed for user {user_id}, provider {provider} "
                        f"(attempt {attempt})"
                    )
                    return new_creds

                # --- Failure ---
                last_result = refresh_result or {}

                if last_result.get('reauth_required'):
                    # Hard failure — no point retrying
                    error_msg = last_result.get('message', 'Re-authentication required')
                    credential.mark_refresh_failure(error_msg, is_hard_failure=True)
                    db.session.commit()
                    logger.warning(
                        f"Hard refresh failure for user {user_id}, provider {provider}: {error_msg}"
                    )
                    return {
                        'reauth_required': True,
                        'message': error_msg,
                    }

                # Transient failure — retry with backoff
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        f"Transient refresh failure for user {user_id}, provider {provider} "
                        f"(attempt {attempt}/{MAX_RETRIES}): {last_result.get('message')}. "
                        f"Retrying in {delay}s."
                    )
                    time.sleep(delay)

            except Exception as e:
                logger.error(
                    f"Exception during refresh attempt {attempt} for "
                    f"user {user_id}, provider {provider}: {e}"
                )
                last_result = {'message': str(e)}
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                    time.sleep(delay)

        # All retries exhausted — mark transient failure
        error_msg = (last_result or {}).get('message', 'Token refresh failed after retries')
        credential.mark_refresh_failure(error_msg, is_hard_failure=False)
        db.session.commit()
        logger.error(
            f"All {MAX_RETRIES} refresh attempts failed for user {user_id}, "
            f"provider {provider}: {error_msg}"
        )
        return None

    @staticmethod
    def _call_provider_refresh(
        user_id: int, provider: str, refresh_token_value: str,
    ) -> Optional[Dict[str, Any]]:
        """Dispatch refresh to the correct provider OAuth class."""
        if provider == 'schwab':
            oauth = SchwabOAuth(user_id=user_id)
            return oauth.refresh_token(refresh_token_value)
        elif provider == 'coinbase':
            oauth = CoinbaseOAuth(user_id=user_id)
            return oauth.refresh_token(refresh_token_value)
        else:
            logger.error(f"Unknown OAuth provider for refresh: {provider}")
            return None
