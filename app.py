import os
import logging
from flask import Flask
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

# Set up logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
    
    # Configure proper URL generation for OAuth redirects
    # Allow flexible domain handling for OAuth callbacks (both arbion.ai and www.arbion.ai)
    app.config['SERVER_NAME'] = None  # Enable flexible domain handling
    app.config['PREFERRED_URL_SCHEME'] = 'https'
    
    # Fix DATABASE_URL for newer SQLAlchemy versions
    database_url = os.environ.get("DATABASE_URL", "postgresql://localhost/arbion_db")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
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
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(github_bp)
    
    # Create tables and default admin user
    with app.app_context():
        # Import models to ensure they're registered
        import models
        
        db.create_all()
        
        # Create default superadmin user
        from models import User
        from werkzeug.security import generate_password_hash
        
        admin_email = "nvm427@gmail.com"
        admin_password = "$@MP$0n9174201989"
        
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
