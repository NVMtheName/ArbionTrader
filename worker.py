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
    """Celery task for updating API connection status"""
    try:
        from models import APICredential
        from utils.encryption import decrypt_credentials
        from utils.coinbase_connector import CoinbaseConnector
        from utils.openai_trader import OpenAITrader
        from datetime import datetime
        
        credentials = APICredential.query.filter_by(is_active=True).all()
        updated_count = 0
        
        for cred in credentials:
            try:
                decrypted_creds = decrypt_credentials(cred.encrypted_credentials)
                
                if cred.provider == 'coinbase':
                    connector = CoinbaseConnector(
                        decrypted_creds['api_key'],
                        decrypted_creds['secret'],
                        decrypted_creds['passphrase']
                    )
                    result = connector.test_connection()
                    
                elif cred.provider == 'openai':
                    trader = OpenAITrader(decrypted_creds['api_key'])
                    result = trader.test_connection()
                    
                else:
                    continue
                
                cred.test_status = 'success' if result['success'] else 'failed'
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

if __name__ == '__main__':
    celery.start()