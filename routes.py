from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from models import User, APICredential, Trade, Strategy, SystemLog, AutoTradingSettings
from app import db
from utils.encryption import encrypt_credentials, decrypt_credentials
from utils.coinbase_connector import CoinbaseConnector
from utils.schwab_connector import SchwabConnector
from utils.openai_trader import OpenAITrader
from utils.market_data import MarketDataProvider
from utils.risk_management import RiskManager
from functools import wraps
import logging
import json
from datetime import datetime

main_bp = Blueprint('main', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin():
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def superadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_superadmin():
            flash('You do not have permission to access this page.', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@main_bp.route('/')
@login_required
def dashboard():
    # Get user's recent trades
    recent_trades = Trade.query.filter_by(user_id=current_user.id).order_by(Trade.created_at.desc()).limit(10).all()
    
    # Get API connection status
    api_credentials = APICredential.query.filter_by(user_id=current_user.id, is_active=True).all()
    api_status = {}
    for cred in api_credentials:
        api_status[cred.provider] = cred.test_status
    
    # Get auto-trading settings (superadmin only)
    auto_trading_settings = None
    if current_user.is_superadmin():
        auto_trading_settings = AutoTradingSettings.get_settings()
    
    return render_template('dashboard.html', 
                         recent_trades=recent_trades,
                         api_status=api_status,
                         auto_trading_settings=auto_trading_settings)

@main_bp.route('/enhanced-dashboard')
@login_required
def enhanced_dashboard():
    """Enhanced dashboard with advanced features"""
    return render_template('enhanced_dashboard.html')

@main_bp.route('/natural-trade', methods=['GET', 'POST'])
@login_required
def natural_trade():
    if request.method == 'POST':
        prompt = request.form.get('prompt')
        
        if not prompt:
            flash('Please enter a trading prompt.', 'error')
            return render_template('natural_trade.html')
        
        # Get user's OpenAI credentials
        openai_cred = APICredential.query.filter_by(
            user_id=current_user.id, 
            provider='openai', 
            is_active=True
        ).first()
        
        if not openai_cred:
            flash('OpenAI API credentials not configured. Please set up your API credentials first.', 'error')
            return redirect(url_for('main.api_settings'))
        
        try:
            # Decrypt OpenAI credentials
            credentials = decrypt_credentials(openai_cred.encrypted_credentials)
            
            # Initialize OpenAI trader
            trader = OpenAITrader(credentials['api_key'])
            
            # Parse the natural language prompt
            trade_instruction = trader.parse_trading_prompt(prompt)
            
            # Get auto-trading settings to check simulation mode
            auto_settings = AutoTradingSettings.get_settings()
            is_simulation = auto_settings.simulation_mode
            
            # Execute the trade
            result = trader.execute_trade(
                trade_instruction, 
                current_user.id, 
                is_simulation=is_simulation
            )
            
            if result['success']:
                flash(f'Trade executed successfully: {result["message"]}', 'success')
                logging.info(f"Natural language trade executed for user {current_user.id}: {prompt}")
            else:
                flash(f'Trade failed: {result["message"]}', 'error')
                logging.error(f"Natural language trade failed for user {current_user.id}: {result['message']}")
        
        except Exception as e:
            flash(f'Error processing trade: {str(e)}', 'error')
            logging.error(f"Error in natural language trade: {str(e)}")
    
    return render_template('natural_trade.html')

@main_bp.route('/api-settings', methods=['GET', 'POST'])
@login_required
def api_settings():
    if request.method == 'POST':
        provider = request.form.get('provider')
        
        if provider == 'coinbase':
            api_key = request.form.get('coinbase_api_key')
            secret = request.form.get('coinbase_secret')
            passphrase = request.form.get('coinbase_passphrase')
            
            if not all([api_key, secret, passphrase]):
                flash('All Coinbase API fields are required.', 'error')
                return redirect(url_for('main.api_settings'))
            
            credentials = {
                'api_key': api_key,
                'secret': secret,
                'passphrase': passphrase
            }
        
        elif provider == 'schwab':
            api_key = request.form.get('schwab_api_key')
            secret = request.form.get('schwab_secret')
            
            if not all([api_key, secret]):
                flash('All Schwab API fields are required.', 'error')
                return redirect(url_for('main.api_settings'))
            
            credentials = {
                'api_key': api_key,
                'secret': secret
            }
        
        elif provider == 'openai':
            api_key = request.form.get('openai_api_key')
            
            if not api_key:
                flash('OpenAI API key is required.', 'error')
                return redirect(url_for('main.api_settings'))
            
            credentials = {
                'api_key': api_key
            }
        
        else:
            flash('Invalid provider selected.', 'error')
            return redirect(url_for('main.api_settings'))
        
        # Encrypt and save credentials
        encrypted_creds = encrypt_credentials(credentials)
        
        # Check if credentials already exist
        existing_cred = APICredential.query.filter_by(
            user_id=current_user.id,
            provider=provider
        ).first()
        
        if existing_cred:
            existing_cred.encrypted_credentials = encrypted_creds
            existing_cred.updated_at = datetime.utcnow()
            existing_cred.test_status = 'pending'
        else:
            new_cred = APICredential(
                user_id=current_user.id,
                provider=provider,
                encrypted_credentials=encrypted_creds
            )
            db.session.add(new_cred)
        
        db.session.commit()
        flash(f'{provider.title()} credentials saved successfully.', 'success')
        logging.info(f"API credentials saved for user {current_user.id}, provider: {provider}")
    
    # Get existing credentials
    credentials = APICredential.query.filter_by(user_id=current_user.id, is_active=True).all()
    cred_status = {}
    for cred in credentials:
        cred_status[cred.provider] = {
            'status': cred.test_status,
            'last_tested': cred.last_tested
        }
    
    return render_template('api_settings.html', cred_status=cred_status)

@main_bp.route('/test-api-connection', methods=['POST'])
@login_required
def test_api_connection():
    provider = request.form.get('provider')
    
    credential = APICredential.query.filter_by(
        user_id=current_user.id,
        provider=provider,
        is_active=True
    ).first()
    
    if not credential:
        return jsonify({'success': False, 'message': 'API credentials not found'})
    
    try:
        credentials = decrypt_credentials(credential.encrypted_credentials)
        
        if provider == 'coinbase':
            connector = CoinbaseConnector(
                credentials['api_key'],
                credentials['secret'],
                credentials['passphrase']
            )
            result = connector.test_connection()
        
        elif provider == 'schwab':
            connector = SchwabConnector(
                credentials['api_key'],
                credentials['secret']
            )
            result = connector.test_connection()
        
        elif provider == 'openai':
            trader = OpenAITrader(credentials['api_key'])
            result = trader.test_connection()
        
        else:
            result = {'success': False, 'message': 'Invalid provider'}
        
        # Update credential status
        credential.test_status = 'success' if result['success'] else 'failed'
        credential.last_tested = datetime.utcnow()
        db.session.commit()
        
        return jsonify(result)
    
    except Exception as e:
        credential.test_status = 'failed'
        credential.last_tested = datetime.utcnow()
        db.session.commit()
        logging.error(f"API test connection failed: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/strategies')
@login_required
def strategies():
    user_strategies = Strategy.query.filter_by(created_by=current_user.id).all()
    return render_template('strategies.html', strategies=user_strategies)

@main_bp.route('/auto-trading')
@login_required
@superadmin_required
def auto_trading():
    settings = AutoTradingSettings.get_settings()
    return render_template('auto_trading.html', settings=settings)

@main_bp.route('/toggle-auto-trading', methods=['POST'])
@login_required
@superadmin_required
def toggle_auto_trading():
    settings = AutoTradingSettings.get_settings()
    
    action = request.form.get('action')
    
    if action == 'toggle_main':
        settings.is_enabled = not settings.is_enabled
        message = 'Auto-trading enabled' if settings.is_enabled else 'Auto-trading disabled'
    
    elif action == 'toggle_simulation':
        settings.simulation_mode = not settings.simulation_mode
        message = 'Simulation mode enabled' if settings.simulation_mode else 'Simulation mode disabled'
    
    elif action == 'toggle_wheel':
        settings.wheel_enabled = not settings.wheel_enabled
        message = 'Wheel strategy enabled' if settings.wheel_enabled else 'Wheel strategy disabled'
    
    elif action == 'toggle_collar':
        settings.collar_enabled = not settings.collar_enabled
        message = 'Collar strategy enabled' if settings.collar_enabled else 'Collar strategy disabled'
    
    elif action == 'toggle_ai':
        settings.ai_enabled = not settings.ai_enabled
        message = 'AI strategy enabled' if settings.ai_enabled else 'AI strategy disabled'
    
    else:
        flash('Invalid action.', 'error')
        return redirect(url_for('main.auto_trading'))
    
    settings.updated_at = datetime.utcnow()
    db.session.commit()
    
    flash(message, 'success')
    logging.info(f"Auto-trading setting changed by {current_user.email}: {message}")
    return redirect(url_for('main.auto_trading'))

@main_bp.route('/user-management')
@login_required
@superadmin_required
def user_management():
    users = User.query.all()
    return render_template('user_management.html', users=users)

@main_bp.route('/create-user', methods=['POST'])
@login_required
@superadmin_required
def create_user():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role')
    
    if not all([username, email, password, role]):
        flash('All fields are required.', 'error')
        return redirect(url_for('main.user_management'))
    
    if role not in ['standard', 'admin', 'superadmin']:
        flash('Invalid role selected.', 'error')
        return redirect(url_for('main.user_management'))
    
    # Check if user already exists
    if User.query.filter_by(email=email).first():
        flash('Email already exists.', 'error')
        return redirect(url_for('main.user_management'))
    
    if User.query.filter_by(username=username).first():
        flash('Username already exists.', 'error')
        return redirect(url_for('main.user_management'))
    
    new_user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        role=role
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    flash(f'User {username} created successfully.', 'success')
    logging.info(f"User {username} created by {current_user.email}")
    return redirect(url_for('main.user_management'))

@main_bp.route('/toggle-user-status', methods=['POST'])
@login_required
@superadmin_required
def toggle_user_status():
    user_id = request.form.get('user_id')
    user = User.query.get(user_id)
    
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('main.user_management'))
    
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'error')
        return redirect(url_for('main.user_management'))
    
    user.is_active = not user.is_active
    db.session.commit()
    
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {user.username} {status} successfully.', 'success')
    logging.info(f"User {user.username} {status} by {current_user.email}")
    return redirect(url_for('main.user_management'))

@main_bp.route('/account')
@login_required
def account():
    return render_template('account.html')

# Advanced API endpoints for enhanced features
@main_bp.route('/api/market-data/<symbol>')
@login_required
def get_market_data(symbol):
    """Get real-time market data for a symbol"""
    try:
        market_data = MarketDataProvider()
        
        # Determine if it's crypto or stock
        if symbol.endswith('-USD') or symbol.upper() in ['BTC', 'ETH', 'LTC', 'BCH']:
            data = market_data.get_crypto_price(symbol.replace('-USD', ''))
        else:
            data = market_data.get_stock_quote(symbol)
        
        if data:
            return jsonify({'success': True, 'data': data})
        else:
            return jsonify({'success': False, 'message': 'Symbol not found'})
    
    except Exception as e:
        logging.error(f"Error fetching market data: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/api/technical-indicators/<symbol>')
@login_required
def get_technical_indicators(symbol):
    """Get technical indicators for a symbol"""
    try:
        market_data = MarketDataProvider()
        indicators = market_data.calculate_technical_indicators(symbol)
        
        if indicators:
            return jsonify({'success': True, 'data': indicators})
        else:
            return jsonify({'success': False, 'message': 'Could not calculate indicators'})
    
    except Exception as e:
        logging.error(f"Error calculating technical indicators: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/api/option-chain/<symbol>')
@login_required
def get_option_chain(symbol):
    """Get option chain for a symbol"""
    try:
        market_data = MarketDataProvider()
        expiration = request.args.get('expiration')
        
        option_chain = market_data.get_option_chain(symbol, expiration)
        
        if option_chain:
            return jsonify({'success': True, 'data': option_chain})
        else:
            return jsonify({'success': False, 'message': 'Option chain not available'})
    
    except Exception as e:
        logging.error(f"Error fetching option chain: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/api/portfolio-risk')
@login_required
def get_portfolio_risk():
    """Get portfolio risk analysis"""
    try:
        risk_manager = RiskManager()
        risk_data = risk_manager.calculate_portfolio_risk(current_user.id)
        
        return jsonify({'success': True, 'data': risk_data})
    
    except Exception as e:
        logging.error(f"Error calculating portfolio risk: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/api/risk-report')
@login_required
def get_risk_report():
    """Get comprehensive risk report"""
    try:
        risk_manager = RiskManager()
        report = risk_manager.generate_risk_report(current_user.id)
        
        return jsonify({'success': True, 'data': report})
    
    except Exception as e:
        logging.error(f"Error generating risk report: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/api/validate-trade', methods=['POST'])
@login_required
def validate_trade():
    """Validate a trade against risk parameters"""
    try:
        data = request.get_json()
        symbol = data.get('symbol')
        amount = float(data.get('amount', 0))
        
        risk_manager = RiskManager()
        is_valid, message = risk_manager.validate_trade_limits(current_user.id, amount, symbol)
        
        return jsonify({'success': is_valid, 'message': message})
    
    except Exception as e:
        logging.error(f"Error validating trade: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/api/position-size', methods=['POST'])
@login_required
def calculate_position_size():
    """Calculate optimal position size"""
    try:
        data = request.get_json()
        account_balance = float(data.get('account_balance', 10000))
        risk_percentage = float(data.get('risk_percentage', 2))
        entry_price = float(data.get('entry_price'))
        stop_loss = float(data.get('stop_loss'))
        
        risk_manager = RiskManager()
        position_size = risk_manager.calculate_position_size(
            account_balance, risk_percentage, entry_price, stop_loss
        )
        
        return jsonify({
            'success': True,
            'position_size': position_size,
            'risk_amount': account_balance * (risk_percentage / 100),
            'risk_per_share': abs(entry_price - stop_loss)
        })
    
    except Exception as e:
        logging.error(f"Error calculating position size: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/api/market-sentiment/<symbol>')
@login_required
def get_market_sentiment(symbol):
    """Get market sentiment analysis"""
    try:
        market_data = MarketDataProvider()
        sentiment = market_data.get_market_sentiment(symbol)
        
        if sentiment:
            return jsonify({'success': True, 'data': sentiment})
        else:
            return jsonify({'success': False, 'message': 'Sentiment data not available'})
    
    except Exception as e:
        logging.error(f"Error fetching market sentiment: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/api/historical-data/<symbol>')
@login_required
def get_historical_data(symbol):
    """Get historical price data"""
    try:
        market_data = MarketDataProvider()
        period = request.args.get('period', '1mo')
        
        historical_data = market_data.get_historical_data(symbol, period)
        
        if historical_data:
            return jsonify({'success': True, 'data': historical_data})
        else:
            return jsonify({'success': False, 'message': 'Historical data not available'})
    
    except Exception as e:
        logging.error(f"Error fetching historical data: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/api/system-logs')
@login_required
@admin_required
def get_system_logs():
    """Get system logs for administrators"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        level = request.args.get('level', 'all')
        
        query = SystemLog.query
        
        if level != 'all':
            query = query.filter_by(level=level)
        
        logs = query.order_by(SystemLog.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'data': {
                'logs': [
                    {
                        'id': log.id,
                        'level': log.level,
                        'message': log.message,
                        'module': log.module,
                        'user_id': log.user_id,
                        'created_at': log.created_at.isoformat()
                    }
                    for log in logs.items
                ],
                'pagination': {
                    'page': logs.page,
                    'pages': logs.pages,
                    'per_page': logs.per_page,
                    'total': logs.total
                }
            }
        })
    
    except Exception as e:
        logging.error(f"Error fetching system logs: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/api/trade-history')
@login_required
def get_trade_history():
    """Get user's trade history with pagination"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', 'all')
        
        query = Trade.query.filter_by(user_id=current_user.id)
        
        if status != 'all':
            query = query.filter_by(status=status)
        
        trades = query.order_by(Trade.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'success': True,
            'data': {
                'trades': [
                    {
                        'id': trade.id,
                        'symbol': trade.symbol,
                        'side': trade.side,
                        'quantity': trade.quantity,
                        'price': trade.price,
                        'amount': trade.amount,
                        'status': trade.status,
                        'trade_type': trade.trade_type,
                        'strategy': trade.strategy,
                        'provider': trade.provider,
                        'is_simulation': trade.is_simulation,
                        'created_at': trade.created_at.isoformat(),
                        'executed_at': trade.executed_at.isoformat() if trade.executed_at else None
                    }
                    for trade in trades.items
                ],
                'pagination': {
                    'page': trades.page,
                    'pages': trades.pages,
                    'per_page': trades.per_page,
                    'total': trades.total
                }
            }
        })
    
    except Exception as e:
        logging.error(f"Error fetching trade history: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})
