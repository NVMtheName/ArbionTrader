"""
Background task for maintaining persistent API connections.
Handles automatic token refresh for uninterrupted auto-trading.

Safety features for Heroku / cold-boot:
- Startup grace period: skips first run after boot to avoid hammering
  provider APIs with stale tokens before the app is fully warmed up.
- Skips credentials that were created very recently (< 60s) to avoid
  racing with an in-progress OAuth callback.
- Never deactivates credentials — uses the state machine on APICredential.
"""

import logging
import time
from datetime import datetime, timedelta

from utils.token_manager import TokenManager
from models import APICredential, SystemLog
from app import db

logger = logging.getLogger(__name__)

# How long after boot before the first maintenance cycle runs (seconds).
# Prevents hammering provider APIs immediately on Heroku dyno restart.
STARTUP_GRACE_SECONDS = 120  # 2 minutes

# Don't refresh credentials created less than this many seconds ago
# (to avoid racing with an OAuth callback that just stored them).
MIN_CREDENTIAL_AGE_SECONDS = 60


class TokenMaintenanceTask:
    """
    Background task for maintaining API tokens.
    Ensures persistent connections for auto-trading.
    """

    def __init__(self):
        self.last_run = None
        self.maintenance_interval = 300  # 5 minutes
        self._boot_time = datetime.utcnow()
        self._first_run_done = False

    def run_maintenance(self):
        """Run token maintenance cycle."""
        try:
            # Startup grace: skip the very first run after boot
            if not self._first_run_done:
                elapsed_since_boot = (datetime.utcnow() - self._boot_time).total_seconds()
                if elapsed_since_boot < STARTUP_GRACE_SECONDS:
                    logger.info(
                        f"Token maintenance skipping first run — "
                        f"{elapsed_since_boot:.0f}s since boot, "
                        f"grace period is {STARTUP_GRACE_SECONDS}s"
                    )
                    self._first_run_done = True
                    self.last_run = datetime.utcnow()
                    return
                self._first_run_done = True

            logger.info("Starting token maintenance cycle")
            start_time = datetime.utcnow()

            result = TokenManager.validate_all_tokens()

            self.last_run = datetime.utcnow()

            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Token maintenance completed in {duration:.2f}s")

            # Build summary
            summary = f'Token maintenance completed in {duration:.2f}s'
            if result:
                parts = []
                if result.get('refreshed'):
                    parts.append(f"{result['refreshed']} refreshed")
                if result.get('errors'):
                    parts.append(f"{result['errors']} errors")
                if result.get('reauth_required'):
                    parts.append(f"{len(result['reauth_required'])} need reauth")
                if result.get('skipped_api_keys'):
                    parts.append(f"{result['skipped_api_keys']} API-key skipped")
                if parts:
                    summary += f" ({', '.join(parts)})"

            log_level = 'info'

            if result and result.get('reauth_required'):
                log_level = 'warning'
                for reauth in result['reauth_required']:
                    reauth_msg = (
                        f"User {reauth['user_id']} must reconnect "
                        f"{reauth['provider']}: {reauth['reason']}"
                    )
                    self._log_maintenance_event(level='warning', message=reauth_msg)

            self._log_maintenance_event(level=log_level, message=summary)

        except Exception as e:
            logger.error(f"Token maintenance failed: {e}")
            self._log_maintenance_event(
                level='error',
                message=f'Token maintenance failed: {str(e)}'
            )

    def _log_maintenance_event(self, level: str, message: str):
        """Log maintenance event to SystemLog table."""
        try:
            log_entry = SystemLog(
                level=level,
                message=message,
                module='token_maintenance',
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            logger.error(f"Failed to log maintenance event: {e}")

    def should_run(self) -> bool:
        """Check if maintenance should run."""
        if self.last_run is None:
            # On first call, respect the startup grace period
            elapsed_since_boot = (datetime.utcnow() - self._boot_time).total_seconds()
            return elapsed_since_boot >= STARTUP_GRACE_SECONDS

        elapsed = (datetime.utcnow() - self.last_run).total_seconds()
        return elapsed >= self.maintenance_interval

    def get_token_status(self) -> dict:
        """Get status of all API tokens."""
        try:
            credentials = APICredential.query.filter_by(is_active=True).all()

            status = {
                'total_tokens': len(credentials),
                'active_tokens': 0,
                'reauth_required_tokens': 0,
                'error_tokens': 0,
                'api_key_tokens': 0,
                'providers': {},
            }

            for credential in credentials:
                provider = credential.provider

                if provider not in status['providers']:
                    status['providers'][provider] = {
                        'total': 0,
                        'active': 0,
                        'reauth_required': 0,
                        'error': 0,
                    }

                status['providers'][provider]['total'] += 1

                cred_status = getattr(credential, 'status', None) or 'active'
                if credential.is_api_key():
                    status['api_key_tokens'] += 1
                    status['providers'][provider]['active'] += 1
                elif cred_status == 'reauth_required':
                    status['reauth_required_tokens'] += 1
                    status['providers'][provider]['reauth_required'] += 1
                elif cred_status == 'error':
                    status['error_tokens'] += 1
                    status['providers'][provider]['error'] += 1
                else:
                    status['active_tokens'] += 1
                    status['providers'][provider]['active'] += 1

            return status

        except Exception as e:
            logger.error(f"Error getting token status: {e}")
            return {'error': str(e)}


# Global instance for background tasks
token_maintenance_task = TokenMaintenanceTask()


def run_token_maintenance():
    """Entry point for token maintenance task (called by Celery)."""
    token_maintenance_task.run_maintenance()


def get_token_maintenance_status():
    """Get token maintenance status."""
    return {
        'last_run': token_maintenance_task.last_run,
        'should_run': token_maintenance_task.should_run(),
        'token_status': token_maintenance_task.get_token_status(),
    }
