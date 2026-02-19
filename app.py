import os
import logging
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(level=logging.INFO)

class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()
cache = Cache()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],  # Global rate limits
    storage_uri="memory://"  # Will be overridden to use Redis in create_app
)

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
    
    # Database configuration
    database_url = os.environ.get("DATABASE_URL", "postgresql://localhost/arbion_db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 1800,  # Increased from 300 to 1800 (30 minutes)
        "pool_pre_ping": True,
        "pool_size": 10,  # Default connection pool size
        "max_overflow": 20,  # Allow up to 20 connections beyond pool_size
        "pool_timeout": 30,  # Timeout for getting connection from pool
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Proxy fix for Heroku and custom domains
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_for=1)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # CSRF Protection Configuration
    app.config['WTF_CSRF_ENABLED'] = True
    app.config['WTF_CSRF_TIME_LIMIT'] = None  # Tokens don't expire (secured by session)
    app.config['WTF_CSRF_SSL_STRICT'] = os.environ.get('FLASK_ENV') == 'production'  # Enforce HTTPS in production
    app.config['WTF_CSRF_CHECK_DEFAULT'] = True  # Enable CSRF protection by default

    # Exempt OAuth callback endpoints (use state parameter for CSRF protection)
    csrf.exempt("github_routes.github_callback")
    csrf.exempt("utils.schwabdev_routes.*")  # Schwab OAuth callbacks
    csrf.exempt("utils.coinbase_v2_routes.*")  # Coinbase OAuth callbacks
    csrf.exempt("utils.openai_auth_routes.*")  # OpenAI OAuth callbacks

    # Redis Cache Configuration
    redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/1')  # Use DB 1 for cache (DB 0 for Celery)
    app.config['CACHE_TYPE'] = 'redis'
    app.config['CACHE_REDIS_URL'] = redis_url
    app.config['CACHE_DEFAULT_TIMEOUT'] = 300  # 5 minutes default
    app.config['CACHE_KEY_PREFIX'] = 'arbion_cache_'

    cache.init_app(app)
    logging.info(f"✓ Redis cache configured: {redis_url}")

    # Rate Limiting Configuration (uses same Redis)
    # Use DB 2 for rate limiting (separate from cache and Celery)
    rate_limit_redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/2').replace('/1', '/2').replace('/0', '/2')
    limiter.init_app(app)
    limiter.storage_uri = rate_limit_redis_url

    # Exempt health checks from rate limiting
    limiter.exempt(lambda: request.blueprint == 'health' if hasattr(request, 'blueprint') else False)

    logging.info(f"✓ Rate limiting configured: {rate_limit_redis_url}")

    # Login manager configuration
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        from models import User
        return User.query.get(int(user_id))
    
    # Import and register blueprints
    from routes import main_bp
    from auth import auth_bp
    from health import health_bp
    from github_routes import github_bp
    from utils.coinbase_v2_routes import coinbase_v2_bp
    from utils.agent_kit_routes import agent_kit_bp
    from utils.enhanced_openai_routes import enhanced_openai_bp
    from utils.openai_auth_routes import openai_auth_bp
    from utils.schwabdev_routes import schwabdev_bp
    from utils.ai_trading_bot_routes import ai_trading_bot_bp
    from utils.portfolio_routes import portfolio_bp
    from utils.claude_routes import claude_bp

    # Register health checks first (no authentication/CSRF required)
    app.register_blueprint(health_bp)
    csrf.exempt(health_bp)  # Health checks don't need CSRF protection

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(github_bp)
    app.register_blueprint(coinbase_v2_bp)
    app.register_blueprint(agent_kit_bp)
    app.register_blueprint(enhanced_openai_bp)
    app.register_blueprint(openai_auth_bp)
    app.register_blueprint(schwabdev_bp)
    app.register_blueprint(ai_trading_bot_bp)
    app.register_blueprint(portfolio_bp)
    app.register_blueprint(claude_bp)

    # Register simple OpenAI integration routes
    from utils.simple_openai_routes import simple_openai_bp
    app.register_blueprint(simple_openai_bp)
    
    # Validate encryption configuration on startup
    try:
        from utils.encryption import validate_encryption_config
        is_valid, message = validate_encryption_config()
        if is_valid:
            logging.info(f"✓ Encryption: {message}")
        else:
            logging.critical(f"✗ Encryption validation failed: {message}")
            logging.critical("Application cannot start without proper encryption configuration!")
            raise ValueError(f"Encryption configuration error: {message}")
    except Exception as e:
        logging.critical(f"✗ Fatal: Encryption configuration error: {str(e)}")
        logging.critical("Set ENCRYPTION_KEY or ENCRYPTION_SECRET+ENCRYPTION_SALT environment variables")
        raise

    # Create tables and default admin user
    with app.app_context():
        # Import models to ensure they're registered
        import models

        db.create_all()

        # Create default superadmin user (only if configured via environment)
        admin_email = os.environ.get("SUPERADMIN_EMAIL")
        admin_password = os.environ.get("SUPERADMIN_PASSWORD")

        if admin_email and admin_password:
            from models import User
            from werkzeug.security import generate_password_hash

            existing_admin = User.query.filter_by(email=admin_email).first()
            if not existing_admin:
                admin_user = User(
                    username="superadmin",
                    email=admin_email,
                    password_hash=generate_password_hash(admin_password),
                    role="superadmin"
                )
                db.session.add(admin_user)
                db.session.commit()
                logging.info(f"Created default superadmin user: {admin_email}")
        else:
            logging.info("No SUPERADMIN_EMAIL/SUPERADMIN_PASSWORD set - skipping superadmin creation")

    return app

app = create_app()

# Start the background scheduler
try:
    from utils.scheduler import start_scheduler
    start_scheduler()
except Exception as e:
    logging.error(f"Failed to start scheduler: {str(e)}")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)