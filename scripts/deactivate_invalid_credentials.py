#!/usr/bin/env python3
"""
Deactivate API credentials that can't be decrypted with the current encryption key.
This typically happens after rotating encryption keys.

Users will need to re-enter their API credentials through the web interface.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from models import APICredential
from utils.encryption import decrypt_credentials
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def deactivate_invalid_credentials():
    """
    Deactivate credentials that can't be decrypted with the current encryption key
    """
    app = create_app()

    with app.app_context():
        logger.info("Checking all API credentials for decryption issues...")

        all_credentials = APICredential.query.filter_by(is_active=True).all()
        logger.info(f"Found {len(all_credentials)} active credentials")

        deactivated_count = 0
        valid_count = 0

        for credential in all_credentials:
            try:
                # Try to decrypt the credential
                decrypt_credentials(credential.encrypted_credentials)
                valid_count += 1
                logger.info(f"✓ Credential {credential.id} (user={credential.user_id}, provider={credential.provider}) - Valid")

            except Exception as e:
                # Decryption failed - deactivate this credential
                logger.warning(
                    f"✗ Credential {credential.id} (user={credential.user_id}, provider={credential.provider}) "
                    f"- Cannot decrypt: {str(e)}"
                )

                credential.is_active = False
                credential.test_status = 'failed'
                credential.label = f"[INVALID] {credential.label or credential.provider}"
                deactivated_count += 1

        # Commit changes
        if deactivated_count > 0:
            db.session.commit()
            logger.info(f"\n✓ Deactivated {deactivated_count} invalid credentials")
            logger.info(f"✓ {valid_count} credentials remain active")
            logger.info("\nUsers with deactivated credentials will need to re-enter their API keys.")
        else:
            logger.info(f"\n✓ All {valid_count} credentials are valid - no changes needed")

        return {
            'total': len(all_credentials),
            'valid': valid_count,
            'deactivated': deactivated_count
        }

if __name__ == '__main__':
    try:
        result = deactivate_invalid_credentials()
        print(f"\nSummary:")
        print(f"  Total credentials checked: {result['total']}")
        print(f"  Valid credentials: {result['valid']}")
        print(f"  Deactivated credentials: {result['deactivated']}")

        sys.exit(0)

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
