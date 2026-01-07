import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
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
    from github_routes import github_bp
    from utils.coinbase_v2_routes import coinbase_v2_bp
    from utils.agent_kit_routes import agent_kit_bp
    from utils.enhanced_openai_routes import enhanced_openai_bp
    from utils.openai_auth_routes import openai_auth_bp
    from utils.schwabdev_routes import schwabdev_bp
    from utils.ai_trading_bot_routes import ai_trading_bot_bp
    from utils.portfolio_routes import portfolio_bp
    
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