from app import db
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import Text, LargeBinary
import json

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='standard')  # superadmin, admin, standard
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    api_credentials = db.relationship('APICredential', backref='user', lazy=True, cascade='all, delete-orphan')
    oauth_client_credentials = db.relationship('OAuthClientCredential', backref='user', lazy=True, cascade='all, delete-orphan')
    trades = db.relationship('Trade', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def is_superadmin(self):
        return self.role == 'superadmin'
    
    def is_admin(self):
        return self.role in ['superadmin', 'admin']
    
    def __repr__(self):
        return f'<User {self.username}>'

class APICredential(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    provider = db.Column(db.String(50), nullable=False)  # coinbase, schwab, openai
    encrypted_credentials = db.Column(LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    last_tested = db.Column(db.DateTime)
    test_status = db.Column(db.String(20))  # success, failed, pending
    
    def __repr__(self):
        return f'<APICredential {self.provider} for user {self.user_id}>'

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    provider = db.Column(db.String(50), nullable=False)  # coinbase, schwab
    symbol = db.Column(db.String(20), nullable=False)
    side = db.Column(db.String(10), nullable=False)  # buy, sell
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float)
    amount = db.Column(db.Float)
    status = db.Column(db.String(20), default='pending')  # pending, executed, failed, cancelled
    trade_type = db.Column(db.String(20), default='market')  # market, limit, stop
    strategy = db.Column(db.String(50))  # manual, wheel, collar, ai
    natural_language_prompt = db.Column(Text)
    execution_details = db.Column(Text)  # JSON string with execution details
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    executed_at = db.Column(db.DateTime)
    is_simulation = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<Trade {self.symbol} {self.side} {self.quantity}>'

class Strategy(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(Text)
    strategy_type = db.Column(db.String(50), nullable=False)  # wheel, collar, ai
    parameters = db.Column(Text)  # JSON string with strategy parameters
    is_active = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_parameters(self):
        return json.loads(self.parameters) if self.parameters else {}
    
    def set_parameters(self, params):
        self.parameters = json.dumps(params)
    
    def __repr__(self):
        return f'<Strategy {self.name}>'

class SystemLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.String(20), nullable=False)  # info, warning, error
    message = db.Column(Text, nullable=False)
    module = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SystemLog {self.level}: {self.message[:50]}>'

class OAuthClientCredential(db.Model):
    """Store OAuth2 client credentials per-user for multi-user deployment"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    provider = db.Column(db.String(50), nullable=False)  # schwab, coinbase
    client_id = db.Column(db.String(256), nullable=False)
    client_secret = db.Column(db.String(256), nullable=False)
    redirect_uri = db.Column(db.String(512), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<OAuthClientCredential {self.provider} for user {self.user_id}>'

class AutoTradingSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    is_enabled = db.Column(db.Boolean, default=False)
    simulation_mode = db.Column(db.Boolean, default=True)
    wheel_enabled = db.Column(db.Boolean, default=False)
    collar_enabled = db.Column(db.Boolean, default=False)
    ai_enabled = db.Column(db.Boolean, default=False)
    last_run = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @classmethod
    def get_settings(cls):
        settings = cls.query.first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings
