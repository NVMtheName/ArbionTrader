"""
Background task for maintaining persistent API connections
Handles automatic token refresh for uninterrupted auto-trading
"""

import logging
import time
from datetime import datetime
from utils.token_manager import TokenManager
from models import APICredential, SystemLog
from app import db

logger = logging.getLogger(__name__)

class TokenMaintenanceTask:
    """
    Background task for maintaining API tokens
    Ensures persistent connections for auto-trading
    """
    
    def __init__(self):
        self.last_run = None
        self.maintenance_interval = 300  # 5 minutes
    
    def run_maintenance(self):
        """
        Run token maintenance cycle
        """
        try:
            logger.info("Starting token maintenance cycle")
            start_time = datetime.utcnow()

            # Validate and refresh all tokens
            result = TokenManager.validate_all_tokens()

            # Update last run time
            self.last_run = datetime.utcnow()

            # Log maintenance completion
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Token maintenance completed in {duration:.2f} seconds")

            # Build summary message
            summary = f'Token maintenance completed in {duration:.2f}s'
            if result:
                parts = []
                if result.get('refreshed'):
                    parts.append(f"{result['refreshed']} refreshed")
                if result.get('errors'):
                    parts.append(f"{result['errors']} errors")
                if result.get('deactivated'):
                    parts.append(f"{result['deactivated']} deactivated")
                if parts:
                    summary += f" ({', '.join(parts)})"

            log_level = 'info'

            # Log re-authentication requirements as warnings
            if result and result.get('reauth_required'):
                log_level = 'warning'
                for reauth in result['reauth_required']:
                    reauth_msg = (
                        f"User {reauth['user_id']} must re-authenticate with "
                        f"{reauth['provider']}: {reauth['reason']}"
                    )
                    self._log_maintenance_event(level='warning', message=reauth_msg)

            self._log_maintenance_event(level=log_level, message=summary)

        except Exception as e:
            logger.error(f"Token maintenance failed: {str(e)}")
            self._log_maintenance_event(
                level='error',
                message=f'Token maintenance failed: {str(e)}'
            )
    
    def _log_maintenance_event(self, level: str, message: str):
        """
        Log maintenance event to system log
        
        Args:
            level: Log level (info, warning, error)
            message: Log message
        """
        try:
            log_entry = SystemLog(
                level=level,
                message=message,
                module='token_maintenance'
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            logger.error(f"Failed to log maintenance event: {str(e)}")
    
    def should_run(self) -> bool:
        """
        Check if maintenance should run
        
        Returns:
            True if maintenance should run
        """
        if self.last_run is None:
            return True
        
        elapsed = (datetime.utcnow() - self.last_run).total_seconds()
        return elapsed >= self.maintenance_interval
    
    def get_token_status(self) -> dict:
        """
        Get status of all API tokens
        
        Returns:
            Dictionary with token status information
        """
        try:
            credentials = APICredential.query.filter_by(is_active=True).all()
            
            status = {
                'total_tokens': len(credentials),
                'active_tokens': 0,
                'expired_tokens': 0,
                'failed_tokens': 0,
                'providers': {}
            }
            
            for credential in credentials:
                provider = credential.provider
                test_status = credential.test_status
                
                if provider not in status['providers']:
                    status['providers'][provider] = {
                        'total': 0,
                        'active': 0,
                        'expired': 0,
                        'failed': 0
                    }
                
                status['providers'][provider]['total'] += 1
                
                if test_status == 'success':
                    status['active_tokens'] += 1
                    status['providers'][provider]['active'] += 1
                elif test_status == 'failed':
                    status['failed_tokens'] += 1
                    status['providers'][provider]['failed'] += 1
                else:
                    status['expired_tokens'] += 1
                    status['providers'][provider]['expired'] += 1
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting token status: {str(e)}")
            return {'error': str(e)}

# Global instance for background tasks
token_maintenance_task = TokenMaintenanceTask()

def run_token_maintenance():
    """
    Entry point for token maintenance task
    """
    token_maintenance_task.run_maintenance()

def get_token_maintenance_status():
    """
    Get token maintenance status
    """
    return {
        'last_run': token_maintenance_task.last_run,
        'should_run': token_maintenance_task.should_run(),
        'token_status': token_maintenance_task.get_token_status()
    }