from app import create_app
from celery import Celery
import os

# Create Flask app
app = create_app()

# Initialize Celery
def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
        broker=os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    )
    celery.conf.update(app.config)
    
    class ContextTask(celery.Task):
        """Make celery tasks work with Flask app context."""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery

# Create Celery instance
celery = make_celery(app)

# Configure Celery Beat schedule for periodic tasks
celery.conf.beat_schedule = {
    'monitor-stop-losses': {
        'task': 'worker.monitor_stop_losses',
        'schedule': 60.0,  # Run every 60 seconds (CRITICAL for position protection)
    },
    'token-maintenance': {
        'task': 'worker.run_token_maintenance_task',
        'schedule': 300.0,  # Run every 5 minutes — has its own startup grace period
    },
    'cleanup-old-logs': {
        'task': 'worker.cleanup_old_logs',
        'schedule': 86400.0,  # Run daily
    },
    'update-api-status': {
        'task': 'worker.update_api_status',
        'schedule': 3600.0,  # Run hourly
    },
}
celery.conf.timezone = 'UTC'

# Celery worker optimization for Heroku dyno memory limits
celery.conf.worker_prefetch_multiplier = 1  # Reduce memory usage by processing one task at a time
celery.conf.worker_max_tasks_per_child = 100  # Restart worker after 100 tasks to prevent memory leaks
celery.conf.task_acks_late = True  # Only acknowledge task after completion
celery.conf.task_reject_on_worker_lost = True  # Reject task if worker dies

@celery.task
def run_token_maintenance_task():
    """Celery task for periodic OAuth token refresh.
    Has a built-in startup grace period — safe to schedule on Heroku boot."""
    try:
        from tasks.token_maintenance import run_token_maintenance
        run_token_maintenance()
        return {"status": "ok"}
    except Exception as e:
        print(f"Token maintenance task failed: {e}")
        return {"error": str(e)}


@celery.task
def run_auto_trading_task():
    """Celery task for auto-trading"""
    try:
        from tasks.auto_trading_tasks import run_auto_trading
        return run_auto_trading()
    except Exception as e:
        print(f"Auto-trading task failed: {e}")
        return {"error": str(e)}

@celery.task
def cleanup_old_logs():
    """Celery task for cleaning up old system logs"""
    try:
        from models import SystemLog
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        old_logs = SystemLog.query.filter(SystemLog.created_at < cutoff_date).count()
        
        if old_logs > 0:
            SystemLog.query.filter(SystemLog.created_at < cutoff_date).delete()
            from app import db
            db.session.commit()
            
        return {"cleaned_logs": old_logs}
    except Exception as e:
        print(f"Log cleanup task failed: {e}")
        return {"error": str(e)}

@celery.task
def update_api_status():
    """Celery task for updating API connection status.
    Handles both OAuth and API-key credential formats."""
    try:
        from models import APICredential
        from utils.encryption import decrypt_credentials
        from datetime import datetime

        credentials = APICredential.query.filter_by(is_active=True).all()
        updated_count = 0

        for cred in credentials:
            try:
                # Skip OAuth creds that need reauth (token_maintenance handles those)
                if hasattr(cred, 'status') and cred.status == 'reauth_required':
                    continue

                try:
                    decrypted_creds = decrypt_credentials(cred.encrypted_credentials)
                except Exception as decrypt_err:
                    print(f"Skipping credential {cred.id} - decryption failed: {decrypt_err}")
                    cred.test_status = 'failed'
                    cred.last_tested = datetime.utcnow()
                    continue

                result = None

                if cred.provider == 'coinbase':
                    # Coinbase may be OAuth (has access_token) or API-key (has api_key)
                    if decrypted_creds.get('access_token'):
                        from utils.coinbase_oauth import CoinbaseOAuth
                        oauth = CoinbaseOAuth(user_id=cred.user_id)
                        result = oauth.test_connection(decrypted_creds['access_token'])
                    elif decrypted_creds.get('api_key'):
                        from utils.coinbase_connector import CoinbaseConnector
                        connector = CoinbaseConnector(
                            decrypted_creds['api_key'],
                            decrypted_creds.get('secret', ''),
                            decrypted_creds.get('passphrase', '')
                        )
                        result = connector.test_connection()

                elif cred.provider == 'schwab':
                    if decrypted_creds.get('access_token'):
                        from utils.schwab_oauth import SchwabOAuth
                        oauth = SchwabOAuth(user_id=cred.user_id)
                        result = oauth.test_connection(decrypted_creds['access_token'])

                elif cred.provider == 'openai':
                    from utils.openai_trader import OpenAITrader
                    trader = OpenAITrader(decrypted_creds['api_key'])
                    result = trader.test_connection()

                else:
                    continue

                if result:
                    cred.test_status = 'success' if result.get('success') else 'failed'
                    cred.last_tested = datetime.utcnow()
                    updated_count += 1

            except Exception as e:
                cred.test_status = 'failed'
                cred.last_tested = datetime.utcnow()
                print(f"Error testing API for user {cred.user_id}: {e}")

        from app import db
        db.session.commit()

        return {"updated_credentials": updated_count}
    except Exception as e:
        print(f"API status update task failed: {e}")
        return {"error": str(e)}

@celery.task
def monitor_stop_losses():
    """
    CRITICAL: Celery task for monitoring and enforcing stop-losses
    This task should run every 1 minute to protect positions from excessive losses

    Configure in celery beat schedule:
    celery.conf.beat_schedule = {
        'monitor-stop-losses': {
            'task': 'worker.monitor_stop_losses',
            'schedule': 60.0,  # Every 60 seconds
        },
    }
    """
    try:
        from models import User, APICredential, Trade
        from utils.encryption import decrypt_credentials
        from utils.schwab_api import SchwabAPIClient
        from utils.risk_management import RiskManager
        from app import db
        from datetime import datetime
        import logging

        logger = logging.getLogger(__name__)
        logger.info("Starting stop-loss monitoring task")

        # Initialize risk manager with database session
        risk_manager = RiskManager(db=db)

        # Get all users with active trades that have stop losses
        users_with_stop_losses = db.session.query(Trade.user_id).filter(
            Trade.status == 'executed',
            Trade.stop_loss_price.isnot(None)
        ).distinct().all()

        total_monitored = 0
        total_triggered = 0
        total_closed = 0
        errors = []

        for user_tuple in users_with_stop_losses:
            user_id = user_tuple[0]

            try:
                # Get Schwab credentials for this user
                schwab_cred = APICredential.query.filter_by(
                    user_id=user_id,
                    provider='schwab',
                    is_active=True
                ).first()

                if not schwab_cred:
                    logger.warning(f"No Schwab credentials found for user {user_id}, skipping")
                    continue

                # Decrypt credentials and initialize API client
                decrypted = decrypt_credentials(schwab_cred.encrypted_credentials)
                access_token = decrypted.get('access_token')

                if not access_token:
                    logger.warning(f"No access token for user {user_id}, skipping")
                    continue

                api_client = SchwabAPIClient(access_token=access_token)

                # Monitor stop losses for this user
                result = risk_manager.monitor_stop_losses(user_id, api_client)

                total_monitored += result.get('trades_monitored', 0)
                total_triggered += result.get('stop_losses_triggered', 0)
                total_closed += result.get('positions_closed', 0)

                if result.get('errors'):
                    errors.extend(result['errors'])

                logger.info(
                    f"User {user_id}: monitored={result.get('trades_monitored', 0)}, "
                    f"triggered={result.get('stop_losses_triggered', 0)}, "
                    f"closed={result.get('positions_closed', 0)}"
                )

            except Exception as e:
                logger.error(f"Error monitoring stop losses for user {user_id}: {str(e)}")
                errors.append({
                    'user_id': user_id,
                    'error': str(e)
                })

        result_summary = {
            'users_processed': len(users_with_stop_losses),
            'total_trades_monitored': total_monitored,
            'total_stop_losses_triggered': total_triggered,
            'total_positions_closed': total_closed,
            'errors': errors,
            'timestamp': datetime.utcnow().isoformat()
        }

        logger.info(f"Stop-loss monitoring complete: {result_summary}")
        return result_summary

    except Exception as e:
        logger.error(f"Stop-loss monitoring task failed: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}

if __name__ == '__main__':
    celery.start()