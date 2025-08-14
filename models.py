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
    provider = db.Column(db.String(50), nullable=False)  # coinbase, schwab, openai, etrade
    encrypted_credentials = db.Column(LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    last_tested = db.Column(db.DateTime)
    test_status = db.Column(db.String(20))  # success, failed, pending
    
    # Additional fields for OAuth tokens (Schwab, Coinbase)
    access_token = db.Column(Text)
    refresh_token = db.Column(Text)
    token_expiry = db.Column(db.String(50))  # ISO format string
    
    def __repr__(self):
        return f'<APICredential {self.provider} for user {self.user_id}>'

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    provider = db.Column(db.String(50), nullable=False)  # coinbase, schwab, etrade
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
    
    # Enhanced analytics fields
    fees = db.Column(db.Float, default=0.0)
    commission = db.Column(db.Float, default=0.0)
    realized_pnl = db.Column(db.Float)  # Profit/Loss when position is closed
    unrealized_pnl = db.Column(db.Float)  # Current P&L for open positions
    market_value = db.Column(db.Float)  # Current market value
    cost_basis = db.Column(db.Float)  # Cost basis for position tracking
    portfolio_percentage = db.Column(db.Float)  # Percentage of portfolio
    risk_score = db.Column(db.Float)  # Risk assessment score
    confidence_score = db.Column(db.Float)  # AI confidence (if AI trade)
    exit_price = db.Column(db.Float)  # Exit price when position is closed
    exit_date = db.Column(db.DateTime)  # Exit timestamp
    holding_period_days = db.Column(db.Integer)  # Days held
    trade_notes = db.Column(Text)  # User or system notes
    
    def get_execution_details(self):
        """Parse execution details JSON"""
        if self.execution_details:
            try:
                return json.loads(self.execution_details)
            except:
                return {}
        return {}
    
    def set_execution_details(self, details):
        """Set execution details as JSON"""
        self.execution_details = json.dumps(details)
    
    def calculate_pnl(self, current_price=None):
        """Calculate P&L for the trade"""
        if not self.price or not self.quantity:
            return 0.0
        
        if self.status == 'executed' and self.exit_price:
            # Realized P&L for closed position
            if self.side == 'buy':
                return (self.exit_price - self.price) * self.quantity - (self.fees or 0) - (self.commission or 0)
            else:  # sell
                return (self.price - self.exit_price) * self.quantity - (self.fees or 0) - (self.commission or 0)
        elif current_price and self.status == 'executed':
            # Unrealized P&L for open position
            if self.side == 'buy':
                return (current_price - self.price) * self.quantity - (self.fees or 0) - (self.commission or 0)
            else:  # sell (short position)
                return (self.price - current_price) * self.quantity - (self.fees or 0) - (self.commission or 0)
        
        return 0.0
    
    def get_return_percentage(self, current_price=None):
        """Calculate return percentage"""
        if not self.price or not self.quantity:
            return 0.0
        
        investment = self.price * self.quantity
        pnl = self.calculate_pnl(current_price)
        
        if investment > 0:
            return (pnl / investment) * 100
        return 0.0
    
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
    provider = db.Column(db.String(50), nullable=False)  # schwab, coinbase, etrade
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

class Portfolio(db.Model):
    """Portfolio tracking and analytics"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    provider = db.Column(db.String(50), nullable=False)
    account_id = db.Column(db.String(100))  # External account ID
    total_value = db.Column(db.Float, default=0.0)
    cash_balance = db.Column(db.Float, default=0.0)
    invested_amount = db.Column(db.Float, default=0.0)
    total_pnl = db.Column(db.Float, default=0.0)
    day_pnl = db.Column(db.Float, default=0.0)
    total_return_pct = db.Column(db.Float, default=0.0)
    day_return_pct = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Portfolio {self.provider} for user {self.user_id}>'

class TradeAnalytics(db.Model):
    """Daily/periodic trade analytics aggregation"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    
    # Daily metrics
    trades_count = db.Column(db.Integer, default=0)
    winning_trades = db.Column(db.Integer, default=0)
    losing_trades = db.Column(db.Integer, default=0)
    total_volume = db.Column(db.Float, default=0.0)
    total_pnl = db.Column(db.Float, default=0.0)
    realized_pnl = db.Column(db.Float, default=0.0)
    unrealized_pnl = db.Column(db.Float, default=0.0)
    
    # Performance metrics
    win_rate = db.Column(db.Float, default=0.0)
    avg_win = db.Column(db.Float, default=0.0)
    avg_loss = db.Column(db.Float, default=0.0)
    profit_factor = db.Column(db.Float, default=0.0)
    sharpe_ratio = db.Column(db.Float, default=0.0)
    max_drawdown = db.Column(db.Float, default=0.0)
    
    # Strategy breakdown
    manual_trades = db.Column(db.Integer, default=0)
    ai_trades = db.Column(db.Integer, default=0)
    wheel_trades = db.Column(db.Integer, default=0)
    collar_trades = db.Column(db.Integer, default=0)
    
    # Risk metrics
    portfolio_beta = db.Column(db.Float, default=0.0)
    volatility = db.Column(db.Float, default=0.0)
    value_at_risk = db.Column(db.Float, default=0.0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<TradeAnalytics {self.date} for user {self.user_id}>'

class PerformanceBenchmark(db.Model):
    """Track performance against benchmarks"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    benchmark_symbol = db.Column(db.String(20), nullable=False)  # SPY, QQQ, etc.
    period = db.Column(db.String(20), nullable=False)  # 1D, 1W, 1M, 3M, 6M, 1Y
    user_return = db.Column(db.Float, default=0.0)
    benchmark_return = db.Column(db.Float, default=0.0)
    alpha = db.Column(db.Float, default=0.0)  # Excess return vs benchmark
    beta = db.Column(db.Float, default=0.0)   # Correlation with benchmark
    tracking_error = db.Column(db.Float, default=0.0)
    information_ratio = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<PerformanceBenchmark {self.benchmark_symbol} {self.period} for user {self.user_id}>'
