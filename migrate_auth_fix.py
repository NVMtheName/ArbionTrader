#!/usr/bin/env python3
"""
Arbion Auth Fix Migration Script
=================================
This script:
1. Backs up the old schwabdev_integration.py
2. Replaces it with the fixed v2 version
3. Verifies the token loading pipeline works
4. Tests the connection if credentials exist

Run locally: python migrate_auth_fix.py
Run on Heroku: heroku run python migrate_auth_fix.py --app YOUR-APP-NAME
"""

import os
import sys
import shutil
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def step_1_backup():
    """Backup original schwabdev_integration.py"""
    src = 'utils/schwabdev_integration.py'
    dst = 'utils/schwabdev_integration_v1_backup.py'

    if os.path.exists(src):
        shutil.copy2(src, dst)
        logger.info(f"✅ Backed up {src} → {dst}")
    else:
        logger.warning(f"⚠️  {src} not found (already migrated?)")


def step_2_swap():
    """Replace v1 with v2"""
    v2_src = 'utils/schwabdev_integration_v2.py'
    target = 'utils/schwabdev_integration.py'

    if os.path.exists(v2_src):
        shutil.copy2(v2_src, target)
        logger.info(f"✅ Replaced {target} with v2 (unified auth)")
    else:
        logger.error(f"❌ {v2_src} not found! Make sure schwabdev_integration_v2.py is in utils/")
        sys.exit(1)


def step_3_verify_imports():
    """Verify the fixed module imports correctly"""
    try:
        # Need to set up Flask app context for DB access
        from app import create_app
        app = create_app()

        with app.app_context():
            from utils.schwabdev_integration import create_schwabdev_manager, get_schwabdev_info

            info = get_schwabdev_info()
            assert info['auth_version'] == 'v2_unified', "Wrong version loaded!"
            logger.info(f"✅ Imports working | auth_version={info['auth_version']}")
            logger.info(f"   Fixes applied: {info['fixes'][:2]}...")
            return True

    except Exception as e:
        logger.error(f"❌ Import verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def step_4_verify_token_loading(user_id=None):
    """Verify tokens load from APICredential table correctly"""
    try:
        from app import create_app
        app = create_app()

        with app.app_context():
            from utils.schwabdev_integration import create_schwabdev_manager

            # If no user_id, try to find one with Schwab credentials
            if not user_id:
                from models import APICredential
                cred = APICredential.query.filter_by(provider='schwab', is_active=True).first()
                if cred:
                    user_id = str(cred.user_id)
                    logger.info(f"Found Schwab credentials for user {user_id}")
                else:
                    logger.info("No existing Schwab credentials in DB - skipping token load test")
                    logger.info("✅ This is normal for first-time setup (needs OAuth flow)")
                    return True

            manager = create_schwabdev_manager(user_id)
            status = manager.get_connection_status()

            logger.info(f"✅ Connection status for user {user_id}:")
            logger.info(f"   has_app_key: {status['has_app_key']}")
            logger.info(f"   has_access_token: {status['has_access_token']}")
            logger.info(f"   has_refresh_token: {status['has_refresh_token']}")
            logger.info(f"   token_expired: {status['token_expired']}")
            logger.info(f"   auth_version: {status['auth_version']}")

            if status['issues']:
                logger.info(f"   ⚠️  Issues: {status['issues']}")
            if status['healthy']:
                logger.info(f"   🟢 Connection is HEALTHY")
            else:
                logger.info(f"   🟡 Connection needs attention (see issues above)")

            return True

    except Exception as e:
        logger.error(f"❌ Token loading test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def step_5_test_connection(user_id=None):
    """Test actual API connection if credentials exist"""
    try:
        from app import create_app
        app = create_app()

        with app.app_context():
            from utils.schwabdev_integration import create_schwabdev_manager

            if not user_id:
                from models import APICredential
                cred = APICredential.query.filter_by(provider='schwab', is_active=True).first()
                if not cred:
                    logger.info("⏭️  Skipping connection test - no credentials to test with")
                    return True
                user_id = str(cred.user_id)

            manager = create_schwabdev_manager(user_id)
            results = manager.test_connection()

            logger.info(f"\n📊 Connection Test Results:")
            for test in results['tests']:
                icon = "✅" if test['passed'] else "❌"
                logger.info(f"   {icon} {test['name']}: {test['detail']}")

            if results['all_passed']:
                logger.info(f"\n🎉 ALL TESTS PASSED - Real account data should now sync!")
            else:
                logger.info(f"\n⚠️  Some tests failed - check issues above")

            return results['all_passed']

    except Exception as e:
        logger.error(f"❌ Connection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    logger.info("=" * 60)
    logger.info("Arbion Auth Fix Migration")
    logger.info("=" * 60)

    user_id = sys.argv[1] if len(sys.argv) > 1 else None

    logger.info("\n📦 Step 1: Backup original...")
    step_1_backup()

    logger.info("\n🔄 Step 2: Swap to v2...")
    step_2_swap()

    logger.info("\n🔍 Step 3: Verify imports...")
    if not step_3_verify_imports():
        logger.error("Migration failed at import verification!")
        sys.exit(1)

    logger.info("\n🔑 Step 4: Verify token loading...")
    step_4_verify_token_loading(user_id)

    logger.info("\n🌐 Step 5: Test connection...")
    step_5_test_connection(user_id)

    logger.info("\n" + "=" * 60)
    logger.info("Migration complete!")
    logger.info("=" * 60)
    logger.info("\nNext steps:")
    logger.info("1. If tokens loaded → real account data should sync now")
    logger.info("2. If no tokens → complete OAuth flow: POST /api/schwabdev/auth/start")
    logger.info("3. Deploy to Heroku: git push heroku main")
    logger.info("4. Run on Heroku: heroku run python migrate_auth_fix.py --app YOUR-APP")


if __name__ == '__main__':
    main()
