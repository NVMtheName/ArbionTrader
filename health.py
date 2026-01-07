"""
Health Check Endpoints for Production Monitoring
Provides liveness and readiness probes for load balancers and orchestrators
"""

from flask import Blueprint, jsonify
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health():
    """
    Basic health check endpoint - always returns 200 if app is running
    Use this for basic uptime monitoring

    Returns:
        JSON response with status "ok"
    """
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'arbion-trader'
    }), 200


@health_bp.route('/health/live', methods=['GET'])
def liveness():
    """
    Liveness probe - indicates if application is alive
    Returns 200 if app can handle requests
    Use this for Kubernetes liveness probes

    Returns:
        JSON response with status "alive"
    """
    return jsonify({
        'status': 'alive',
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@health_bp.route('/health/ready', methods=['GET'])
def readiness():
    """
    Readiness probe - indicates if application is ready to serve traffic
    Checks critical dependencies: database, Redis (Celery)
    Use this for Kubernetes readiness probes and load balancer health checks

    Returns:
        200 if ready, 503 if not ready
    """
    checks = {
        'database': False,
        'redis': False,
        'encryption': False
    }
    errors = []

    # Check database connection
    try:
        from app import db
        db.session.execute(db.text('SELECT 1'))
        checks['database'] = True
    except Exception as e:
        errors.append(f"Database: {str(e)}")
        logger.error(f"Health check - Database failed: {str(e)}")

    # Check Redis connection (Celery broker)
    try:
        from worker import celery
        # Ping Redis through Celery
        celery.control.inspect().ping(timeout=1.0)
        checks['redis'] = True
    except Exception as e:
        errors.append(f"Redis: {str(e)}")
        logger.warning(f"Health check - Redis failed: {str(e)}")

    # Check encryption configuration
    try:
        from utils.encryption import validate_encryption_config
        is_valid, message = validate_encryption_config()
        checks['encryption'] = is_valid
        if not is_valid:
            errors.append(f"Encryption: {message}")
    except Exception as e:
        errors.append(f"Encryption: {str(e)}")
        logger.error(f"Health check - Encryption failed: {str(e)}")

    # Determine overall health
    all_healthy = all(checks.values())
    critical_healthy = checks['database'] and checks['encryption']  # Redis is not critical

    if all_healthy:
        status_code = 200
        status = 'ready'
    elif critical_healthy:
        status_code = 200  # Still serve traffic if only Redis is down
        status = 'degraded'
    else:
        status_code = 503
        status = 'not_ready'

    response = {
        'status': status,
        'timestamp': datetime.utcnow().isoformat(),
        'checks': checks
    }

    if errors:
        response['errors'] = errors

    return jsonify(response), status_code


@health_bp.route('/health/startup', methods=['GET'])
def startup():
    """
    Startup probe - indicates if application has completed startup
    Checks if critical initialization is complete
    Use this for Kubernetes startup probes (slower than readiness)

    Returns:
        200 if started, 503 if still starting
    """
    checks = {
        'database_tables': False,
        'encryption_validated': False,
        'blueprints_registered': False
    }
    errors = []

    # Check if database tables exist
    try:
        from app import db
        from models import User  # Import to ensure table exists
        # Try to query User table
        db.session.query(User).first()
        checks['database_tables'] = True
    except Exception as e:
        errors.append(f"Database tables: {str(e)}")

    # Check encryption
    try:
        from utils.encryption import validate_encryption_config
        is_valid, _ = validate_encryption_config()
        checks['encryption_validated'] = is_valid
    except Exception as e:
        errors.append(f"Encryption: {str(e)}")

    # Check if Flask blueprints are registered (app initialized)
    try:
        from flask import current_app
        # If we can access current_app, blueprints are registered
        if len(current_app.blueprints) > 0:
            checks['blueprints_registered'] = True
    except Exception as e:
        errors.append(f"Blueprints: {str(e)}")

    all_started = all(checks.values())

    response = {
        'status': 'started' if all_started else 'starting',
        'timestamp': datetime.utcnow().isoformat(),
        'checks': checks
    }

    if errors:
        response['errors'] = errors

    status_code = 200 if all_started else 503
    return jsonify(response), status_code


@health_bp.route('/health/metrics', methods=['GET'])
def metrics():
    """
    Basic metrics endpoint for monitoring
    Provides counts of active trades, users, and system status

    Returns:
        JSON with system metrics
    """
    try:
        from app import db
        from models import User, Trade, SystemLog
        from datetime import timedelta

        # Count active trades (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        active_trades = Trade.query.filter(
            Trade.status == 'executed',
            Trade.created_at >= yesterday
        ).count()

        # Count total users
        total_users = User.query.count()

        # Count recent logs (last hour)
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_logs = SystemLog.query.filter(
            SystemLog.created_at >= hour_ago
        ).count()

        metrics_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'trades': {
                'active_24h': active_trades
            },
            'users': {
                'total': total_users
            },
            'logs': {
                'last_hour': recent_logs
            }
        }

        return jsonify(metrics_data), 200

    except Exception as e:
        logger.error(f"Metrics endpoint failed: {str(e)}")
        return jsonify({
            'error': 'Metrics unavailable',
            'message': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500
