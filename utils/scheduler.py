import os
import logging
import schedule
import time
import threading
from datetime import datetime, timedelta
from tasks.auto_trading_tasks import run_auto_trading
from models import SystemLog, AutoTradingSettings
from app import db

class TaskScheduler:
    """Background task scheduler for automated trading and system maintenance"""
    
    def __init__(self, use_celery=False):
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.scheduler_thread = None
        self.use_celery = use_celery
        
    def start(self):
        """Start the background scheduler"""
        if self.running:
            self.logger.warning("Scheduler is already running")
            return
        
        self.running = True
        self.logger.info("Starting task scheduler...")
        
        if self.use_celery:
            self.logger.info("Using Celery for task scheduling - tasks will be handled by Celery Beat")
            # Celery beat will handle scheduling automatically
            return
        else:
            # Fall back to threading for local development
            self.logger.info("Using threading for task scheduling")
            
            # Schedule auto-trading tasks
            schedule.every(15).minutes.do(self._run_auto_trading)
            
            # Schedule system maintenance tasks
            schedule.every(1).hour.do(self._cleanup_old_logs)
            schedule.every(6).hours.do(self._update_api_status)
            schedule.every().day.at("00:00").do(self._daily_maintenance)
            
            # Schedule token maintenance for persistent connections
            schedule.every(5).minutes.do(self._run_token_maintenance)
            
            # Start scheduler in a separate thread
            self.scheduler_thread = threading.Thread(target=self._scheduler_loop)
            self.scheduler_thread.daemon = True
            self.scheduler_thread.start()
            
        self.logger.info("Task scheduler started successfully")
    
    def stop(self):
        """Stop the background scheduler"""
        self.running = False
        self.logger.info("Task scheduler stopped")
    
    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {str(e)}")
                time.sleep(60)  # Wait longer on error
    
    def _run_auto_trading(self):
        """Execute auto-trading cycle"""
        try:
            from app import app
            with app.app_context():
                settings = AutoTradingSettings.get_settings()
                
                if not settings.is_enabled:
                    return
                
                # Check if enough time has passed since last run
                if settings.last_run:
                    time_since_last = datetime.utcnow() - settings.last_run
                    if time_since_last < timedelta(minutes=10):
                        return
                
                self.logger.info("Starting scheduled auto-trading cycle")
                
                # Run auto-trading in a separate thread to avoid blocking
                trading_thread = threading.Thread(target=run_auto_trading)
                trading_thread.daemon = True
                trading_thread.start()
                
                # Log the execution
                self._log_system_event('info', 'Auto-trading cycle initiated by scheduler')
            
        except Exception as e:
            self.logger.error(f"Error in scheduled auto-trading: {str(e)}")
            try:
                from app import app
                with app.app_context():
                    self._log_system_event('error', f'Scheduled auto-trading failed: {str(e)}')
            except:
                pass
    
    def _cleanup_old_logs(self):
        """Clean up old system logs"""
        try:
            from app import app
            with app.app_context():
                # Delete logs older than 30 days
                cutoff_date = datetime.utcnow() - timedelta(days=30)
                
                old_logs = SystemLog.query.filter(
                    SystemLog.created_at < cutoff_date
                ).count()
                
                if old_logs > 0:
                    SystemLog.query.filter(
                        SystemLog.created_at < cutoff_date
                    ).delete()
                    
                    db.session.commit()
                    
                    self.logger.info(f"Cleaned up {old_logs} old log entries")
                    self._log_system_event('info', f'Cleaned up {old_logs} old log entries')
        
        except Exception as e:
            self.logger.error(f"Error cleaning up logs: {str(e)}")
            try:
                from app import app
                with app.app_context():
                    self._log_system_event('error', f'Log cleanup failed: {str(e)}')
            except:
                pass
    
    def _update_api_status(self):
        """Update API connection status for all users"""
        try:
            from models import APICredential
            from utils.coinbase_connector import CoinbaseConnector
            from utils.schwab_connector import SchwabConnector
            from utils.openai_trader import OpenAITrader
            from utils.encryption import decrypt_credentials
            
            # Get all active API credentials
            credentials = APICredential.query.filter_by(is_active=True).all()
            
            updated_count = 0
            for cred in credentials:
                try:
                    # Decrypt credentials
                    decrypted_creds = decrypt_credentials(cred.encrypted_credentials)
                    
                    # Test connection based on provider
                    if cred.provider == 'coinbase':
                        connector = CoinbaseConnector(
                            decrypted_creds['api_key'],
                            decrypted_creds['secret'],
                            decrypted_creds['passphrase']
                        )
                        result = connector.test_connection()
                    
                    elif cred.provider == 'schwab':
                        connector = SchwabConnector(
                            decrypted_creds['api_key'],
                            decrypted_creds['secret']
                        )
                        result = connector.test_connection()
                    
                    elif cred.provider == 'openai':
                        trader = OpenAITrader(decrypted_creds['api_key'])
                        result = trader.test_connection()
                    
                    else:
                        continue
                    
                    # Update status
                    cred.test_status = 'success' if result['success'] else 'failed'
                    cred.last_tested = datetime.utcnow()
                    updated_count += 1
                
                except Exception as e:
                    cred.test_status = 'failed'
                    cred.last_tested = datetime.utcnow()
                    self.logger.error(f"Error testing API for user {cred.user_id}, provider {cred.provider}: {str(e)}")
            
            db.session.commit()
            
            if updated_count > 0:
                self.logger.info(f"Updated API status for {updated_count} credentials")
                self._log_system_event('info', f'Updated API status for {updated_count} credentials')
        
        except Exception as e:
            self.logger.error(f"Error updating API status: {str(e)}")
            self._log_system_event('error', f'API status update failed: {str(e)}')
    
    def _daily_maintenance(self):
        """Perform daily maintenance tasks"""
        try:
            self.logger.info("Starting daily maintenance tasks")
            
            # Clean up old trades (simulation trades older than 7 days)
            from models import Trade
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            
            old_sim_trades = Trade.query.filter(
                Trade.is_simulation == True,
                Trade.created_at < cutoff_date
            ).count()
            
            if old_sim_trades > 0:
                Trade.query.filter(
                    Trade.is_simulation == True,
                    Trade.created_at < cutoff_date
                ).delete()
                
                db.session.commit()
                
                self.logger.info(f"Cleaned up {old_sim_trades} old simulation trades")
            
            # Generate daily system report
            from models import User, Trade
            
            total_users = User.query.count()
            active_users = User.query.filter_by(is_active=True).count()
            today_trades = Trade.query.filter(
                Trade.created_at >= datetime.utcnow().date()
            ).count()
            
            report = f"Daily Report - Users: {total_users} (Active: {active_users}), Today's Trades: {today_trades}"
            
            self.logger.info(report)
            self._log_system_event('info', report)
            
            self.logger.info("Daily maintenance completed")
        
        except Exception as e:
            self.logger.error(f"Error in daily maintenance: {str(e)}")
            self._log_system_event('error', f'Daily maintenance failed: {str(e)}')
    
    def _log_system_event(self, level: str, message: str):
        """Log system events"""
        try:
            log_entry = SystemLog(
                level=level,
                message=message,
                module='scheduler'
            )
            db.session.add(log_entry)
            db.session.commit()
        except Exception as e:
            self.logger.error(f"Error logging system event: {str(e)}")
    
    def add_custom_task(self, task_func, schedule_time: str, task_name: str = None):
        """Add a custom scheduled task"""
        try:
            if task_name:
                self.logger.info(f"Adding custom task: {task_name}")
            
            # Parse schedule time and add task
            if schedule_time.startswith('every'):
                # Handle 'every X minutes/hours'
                parts = schedule_time.split()
                if len(parts) >= 3:
                    interval = int(parts[1])
                    unit = parts[2]
                    
                    if unit.startswith('minute'):
                        schedule.every(interval).minutes.do(task_func)
                    elif unit.startswith('hour'):
                        schedule.every(interval).hours.do(task_func)
                    elif unit.startswith('day'):
                        schedule.every(interval).days.do(task_func)
            elif 'at' in schedule_time:
                # Handle 'daily at HH:MM'
                time_part = schedule_time.split('at')[1].strip()
                schedule.every().day.at(time_part).do(task_func)
            
            self.logger.info(f"Custom task scheduled: {schedule_time}")
        
        except Exception as e:
            self.logger.error(f"Error adding custom task: {str(e)}")

# Global scheduler instance
_scheduler = None

def start_scheduler():
    """Start the global task scheduler"""
    try:
        global _scheduler
        if _scheduler is None:
            # Check if running in Heroku/production environment with Redis
            use_celery = os.environ.get('REDIS_URL') is not None
            _scheduler = TaskScheduler(use_celery=use_celery)
        _scheduler.start()
    except Exception as e:
        logging.error(f"Failed to start scheduler: {e}")

def stop_scheduler():
    """Stop the global task scheduler"""
    try:
        global _scheduler
        if _scheduler is not None:
            _scheduler.stop()
    except Exception as e:
        logging.error(f"Failed to stop scheduler: {e}")

# Add token maintenance method to TaskScheduler class
def add_token_maintenance_method():
    """Add token maintenance method to TaskScheduler"""
    def _run_token_maintenance(self):
        """Run token maintenance for persistent connections"""
        try:
            self.logger.info("Running token maintenance for persistent connections")
            from app import app
            with app.app_context():
                from tasks.token_maintenance import run_token_maintenance
                run_token_maintenance()
        except Exception as e:
            self.logger.error(f"Error in token maintenance: {str(e)}")
    
    # Add the method to the TaskScheduler class
    TaskScheduler._run_token_maintenance = _run_token_maintenance

# Add the method when the module is imported
add_token_maintenance_method()