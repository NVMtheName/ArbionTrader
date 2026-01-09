#!/usr/bin/env python3
"""
Diagnostic script to check Schwab OAuth credentials and test API connection
Run on Heroku: heroku run python scripts/check_schwab_connection.py --app trading-botv1
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from models import APICredential, User
from utils.encryption import decrypt_credentials
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_schwab_credentials():
    """Check Schwab OAuth credentials and test connection"""
    app = create_app()

    with app.app_context():
        logger.info("=" * 60)
        logger.info("SCHWAB OAUTH CREDENTIALS DIAGNOSTIC")
        logger.info("=" * 60)

        # Get all users with Schwab credentials
        schwab_creds = APICredential.query.filter_by(
            provider='schwab',
            is_active=True
        ).all()

        logger.info(f"\nFound {len(schwab_creds)} active Schwab credentials")

        if not schwab_creds:
            logger.warning("❌ No Schwab credentials found!")
            logger.info("\nPossible reasons:")
            logger.info("1. OAuth flow not completed")
            logger.info("2. Credentials were deactivated")
            logger.info("3. Database connection issue")
            return

        for cred in schwab_creds:
            user = User.query.get(cred.user_id)
            logger.info(f"\n{'=' * 60}")
            logger.info(f"User: {user.username} (ID: {user.id}, Role: {user.role})")
            logger.info(f"Credential ID: {cred.id}")
            logger.info(f"Provider: {cred.provider}")
            logger.info(f"Active: {cred.is_active}")
            logger.info(f"Test Status: {cred.test_status}")
            logger.info(f"Created: {cred.created_at}")
            logger.info(f"Updated: {cred.updated_at}")

            # Try to decrypt credentials
            try:
                decrypted = decrypt_credentials(cred.encrypted_credentials)
                logger.info(f"\n✅ Credentials decrypted successfully")

                # Check what keys are present
                keys = list(decrypted.keys())
                logger.info(f"Credential keys: {keys}")

                # Check for required OAuth tokens
                required_keys = ['access_token', 'refresh_token', 'expires_at']
                missing_keys = [k for k in required_keys if k not in decrypted]

                if missing_keys:
                    logger.warning(f"⚠️  Missing required keys: {missing_keys}")
                else:
                    logger.info(f"✅ All required OAuth keys present")

                # Check token expiration
                if 'expires_at' in decrypted:
                    from datetime import datetime
                    try:
                        expires_at = datetime.fromisoformat(decrypted['expires_at'])
                        now = datetime.utcnow()
                        if now < expires_at:
                            time_left = expires_at - now
                            logger.info(f"✅ Token valid for {time_left}")
                        else:
                            logger.warning(f"⚠️  Token expired! Needs refresh.")
                    except Exception as e:
                        logger.error(f"Error parsing expiration: {e}")

                # Test API connection
                logger.info(f"\nTesting Schwab API connection...")
                try:
                    from utils.schwab_trader_client import SchwabTraderClient

                    client = SchwabTraderClient(user_id=user.id)
                    accounts = client.get_accounts()

                    if accounts:
                        logger.info(f"✅ Successfully fetched {len(accounts)} account(s)")
                        for i, acc in enumerate(accounts):
                            logger.info(f"\n  Account {i+1}:")
                            logger.info(f"    Type: {acc.get('type', 'unknown')}")
                            logger.info(f"    Number: {acc.get('accountNumber', 'N/A')}")
                            if 'currentBalances' in acc:
                                balances = acc['currentBalances']
                                logger.info(f"    Balance: ${balances.get('liquidationValue', 0):,.2f}")
                    else:
                        logger.warning(f"⚠️  No accounts returned from API")

                except Exception as api_error:
                    logger.error(f"❌ API connection failed: {api_error}")
                    import traceback
                    traceback.print_exc()

            except Exception as decrypt_error:
                logger.error(f"❌ Failed to decrypt credentials: {decrypt_error}")
                logger.error("This credential cannot be used and should be removed.")

        logger.info(f"\n{'=' * 60}")
        logger.info("DIAGNOSTIC COMPLETE")
        logger.info("=" * 60)

if __name__ == '__main__':
    try:
        check_schwab_credentials()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
