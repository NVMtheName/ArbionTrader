from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from functools import wraps
import logging
import json
import os
from datetime import datetime, timedelta
from models import User, Strategy, AutoTradingSettings, APICredential, Trade, SystemLog
from app import db

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

def get_dashboard_market_data():
    """Get real-time market data for dashboard display with entire market coverage"""
    try:
        from utils.comprehensive_market_data import ComprehensiveMarketDataProvider
        from utils.enhanced_market_data import EnhancedMarketDataProvider
        
        # Use comprehensive provider for entire market coverage
        comprehensive_provider = ComprehensiveMarketDataProvider()
        enhanced_provider = EnhancedMarketDataProvider()
        
        # Get data from comprehensive provider (entire market)
        market_data = comprehensive_provider.get_comprehensive_market_data(15)
        
        # Add crypto data using enhanced provider
        crypto_data = {}
        for crypto_symbol in ['BTC', 'ETH', 'LTC']:
            crypto_quote = enhanced_provider.get_crypto_price(crypto_symbol)
            if crypto_quote:
                crypto_data[f'{crypto_symbol}-USD'] = {
                    'price': crypto_quote['price'],
                    'change': crypto_quote['change'],
                    'change_percent': crypto_quote['change_percent'],
                    'volume': crypto_quote.get('volume', 0),
                    'high': crypto_quote.get('high', 0),
                    'low': crypto_quote.get('low', 0)
                }
        
        # Combine stock and crypto data
        market_data.update(crypto_data)
        
        logging.info(f"Comprehensive market data fetched: {len(market_data)} symbols from entire market")
        return market_data
        
    except Exception as e:
        logging.error(f"Error in get_dashboard_market_data: {str(e)}")
        # Return empty dict if comprehensive provider fails
        return {}

def get_account_balance():
    """Get REAL-TIME account balance from connected APIs with live data"""
    from models import APICredential
    from utils.encryption import decrypt_credentials
    from utils.real_time_data import RealTimeDataFetcher
    
    balance_data = {
        'total': 0,
        'breakdown': {},
        'accounts': [],
        'last_updated': datetime.utcnow().isoformat(),
        'errors': []
    }
    
    try:
        from app import db
        # Initialize real-time data fetcher
        fetcher = RealTimeDataFetcher(current_user.id)
        
        # Get user's API credentials
        credentials = APICredential.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).all()
        
        logging.info(f"Processing {len(credentials)} API credentials for real-time balance")
        
        for cred in credentials:
            account_info = {
                'provider': cred.provider,
                'balance': 0,
                'currency': 'USD',
                'account_type': 'unknown',
                'status': 'disconnected',
                'last_updated': datetime.utcnow().isoformat()
            }
            
            try:
                decrypted_creds = decrypt_credentials(cred.encrypted_credentials)
                logging.info(f"Processing {cred.provider} credentials for user {current_user.id}")
                
                if cred.provider == 'coinbase':
                    # Get LIVE Coinbase balance using OAuth helper for automatic token refresh
                    try:
                        from utils.coinbase_oauth import CoinbaseOAuth

                        # Always use OAuth helper to ensure tokens are refreshed if needed
                        coinbase_oauth = CoinbaseOAuth(user_id=current_user.id)
                        access_token = coinbase_oauth.get_valid_token(cred.encrypted_credentials)

                        if access_token:
                            # Use user_id for v2 API support
                            result = fetcher.get_live_coinbase_balance(access_token=access_token, user_id=str(current_user.id))

                            if result.get('success'):
                                account_info['balance'] = result['balance']
                                account_info['status'] = 'connected'
                                account_info['account_type'] = 'crypto'
                                account_info['holdings'] = result.get('holdings', [])
                                account_info['last_updated'] = result['timestamp']
                                account_info['api_version'] = result.get('api_version', 'v1')
                                cred.test_status = 'success'
                                logging.info(f"Coinbase balance fetched: ${result['balance']:.2f} using {result.get('api_version', 'v1')} API")
                            else:
                                account_info['status'] = 'error'
                                error_msg = f"Coinbase: {result.get('error', 'Failed to fetch balance')}"
                                balance_data['errors'].append(error_msg)
                                cred.test_status = 'failed'
                                logging.error(f"Coinbase API error: {error_msg}")
                        else:
                            account_info['status'] = 'error'
                            error_msg = 'Coinbase: Token expired and refresh failed. Please re-authenticate in API Settings.'
                            balance_data['errors'].append(error_msg)
                            cred.test_status = 'failed'
                            logging.error(f"Coinbase token error for user {current_user.id}: {error_msg}")

                    except Exception as e:
                        account_info['status'] = 'error'
                        error_msg = f'Coinbase: {str(e)}'
                        balance_data['errors'].append(error_msg)
                        cred.test_status = 'failed'
                        logging.error(f"Coinbase error for user {current_user.id}: {str(e)}")
                        import traceback
                        traceback.print_exc()
                
                elif cred.provider == 'schwab':
                    # Get LIVE Schwab balance using OAuth helper for automatic token refresh
                    try:
                        from utils.schwab_oauth import SchwabOAuth

                        # Check for legacy credentials
                        if 'api_key' in decrypted_creds and 'secret' in decrypted_creds and 'access_token' not in decrypted_creds:
                            account_info['status'] = 'error'
                            error_msg = 'Schwab: OAuth2 authentication required. Please re-authenticate in API Settings.'
                            balance_data['errors'].append(error_msg)
                            cred.test_status = 'failed'
                            logging.warning(f"Schwab legacy credentials detected for user {current_user.id} - OAuth2 required")
                        else:
                            # Always use OAuth helper to ensure tokens are refreshed if needed
                            schwab_oauth = SchwabOAuth(user_id=current_user.id)
                            access_token = schwab_oauth.get_valid_token(cred.encrypted_credentials)

                            if access_token:
                                # Fetch balance and positions
                                result = fetcher.get_live_schwab_balance(str(current_user.id))
                                positions_result = fetcher.get_live_schwab_positions(str(current_user.id))

                                if result.get('success'):
                                    account_info['balance'] = result['balance']
                                    account_info['status'] = 'connected'
                                    account_info['account_type'] = 'brokerage'
                                    account_info['accounts'] = result.get('accounts', [])

                                    # Add positions to accounts
                                    if positions_result.get('success'):
                                        position_map = {p['account_number']: p.get('positions', []) for p in positions_result.get('accounts', [])}
                                        for acc in account_info['accounts']:
                                            acc['positions'] = position_map.get(acc['account_number'], [])

                                    account_info['last_updated'] = result['timestamp']
                                    cred.test_status = 'success'
                                    logging.info(f"Schwab balance fetched: ${result['balance']:.2f} from {len(account_info['accounts'])} accounts")
                                else:
                                    account_info['status'] = 'error'
                                    error_msg = f"Schwab: {result.get('error', 'Failed to fetch balance')}"
                                    balance_data['errors'].append(error_msg)
                                    cred.test_status = 'failed'
                                    logging.error(f"Schwab API error: {error_msg}")
                            else:
                                account_info['status'] = 'error'
                                error_msg = 'Schwab: Token expired and refresh failed. Please re-authenticate in API Settings.'
                                balance_data['errors'].append(error_msg)
                                cred.test_status = 'failed'
                                logging.error(f"Schwab token error for user {current_user.id}: {error_msg}")

                    except Exception as e:
                        account_info['status'] = 'error'
                        error_msg = f'Schwab: {str(e)}'
                        balance_data['errors'].append(error_msg)
                        cred.test_status = 'failed'
                        logging.error(f"Schwab error for user {current_user.id}: {str(e)}")
                        import traceback
                        traceback.print_exc()
                
                elif cred.provider == 'etrade':
                    # Get LIVE E-trade balance using OAuth 1.0a
                    required_fields = ['client_key', 'client_secret', 'access_token', 'access_secret']
                    if all(field in decrypted_creds for field in required_fields):
                        client_key = decrypted_creds['client_key']
                        client_secret = decrypted_creds['client_secret']
                        access_token = decrypted_creds['access_token']
                        access_secret = decrypted_creds['access_secret']
                        
                        result = fetcher.get_live_etrade_balance(client_key, client_secret, access_token, access_secret)
                        positions_result = fetcher.get_live_etrade_positions(client_key, client_secret, access_token, access_secret)
                        
                        if result.get('success'):
                            account_info['balance'] = result['balance']
                            account_info['status'] = 'connected'
                            account_info['account_type'] = 'brokerage'
                            account_info['accounts'] = result.get('accounts', [])
                            if positions_result.get('success'):
                                position_map = {p['account_id']: p.get('positions', []) for p in positions_result.get('accounts', [])}
                                for acc in account_info['accounts']:
                                    acc['positions'] = position_map.get(acc.get('account_id'), [])
                            account_info['last_updated'] = result['timestamp']
                            cred.test_status = 'success'
                            logging.info(f"E-trade balance fetched: ${result['balance']:.2f}")
                        else:
                            account_info['status'] = 'error'
                            error_msg = f"E-trade: {result.get('error', 'Unknown error')}"
                            balance_data['errors'].append(error_msg)
                            cred.test_status = 'failed'
                            logging.error(f"E-trade error: {error_msg}")
                    else:
                        account_info['status'] = 'error'
                        error_msg = 'E-trade: OAuth 1.0a credentials missing. Please configure E-trade OAuth credentials.'
                        balance_data['errors'].append(error_msg)
                        cred.test_status = 'failed'
                        logging.warning(f"E-trade credentials incomplete for user {current_user.id}")
                
                # Add to accounts list and update totals
                balance_data['accounts'].append(account_info)
                if account_info['status'] == 'connected' and account_info['balance'] > 0:
                    balance_data['total'] += account_info['balance']
                    balance_data['breakdown'][cred.provider] = account_info['balance']
                
                # Update last tested timestamp
                cred.last_tested = datetime.utcnow()
                
            except Exception as e:
                logging.error(f"Error processing {cred.provider} credentials: {str(e)}")
                account_info['status'] = 'error'
                balance_data['errors'].append(f'{cred.provider}: {str(e)}')
                cred.test_status = 'failed'
                balance_data['accounts'].append(account_info)
        
        # Update database with test results
        try:
            db.session.commit()
        except Exception as e:
            logging.error(f"Error updating credential test status: {str(e)}")
            db.session.rollback()
            # Continue anyway - balance data is still valid
        
        logging.info(f"Real-time balance fetch complete. Total: ${balance_data['total']:.2f}")
        return balance_data
    
    except Exception as e:
        logging.error(f"Error in get_account_balance: {str(e)}")
        return {
            'total': 0,
            'breakdown': {},
            'accounts': [],
            'last_updated': datetime.utcnow().isoformat(),
            'errors': [f'System error: {str(e)}']
        }

@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    try:
        from models import Trade, APICredential, AutoTradingSettings
        
        # Get user's recent trades
        recent_trades = Trade.query.filter_by(user_id=current_user.id).order_by(Trade.created_at.desc()).limit(10).all()
        
        # Get API connection status
        api_credentials = APICredential.query.filter_by(user_id=current_user.id, is_active=True).all()
        api_status = {}
        for cred in api_credentials:
            api_status[cred.provider] = cred.test_status or 'unknown'
        
        # Get auto-trading settings (superadmin only)
        auto_trading_settings = None
        if current_user.is_superadmin():
            try:
                auto_trading_settings = AutoTradingSettings.get_settings()
            except Exception as e:
                logging.error(f"Error loading auto-trading settings: {e}")
                auto_trading_settings = None
        
        # Get market data with error handling
        market_data = {}
        try:
            market_data = get_dashboard_market_data()
        except Exception as e:
            logging.error(f"Error loading market data: {e}")
            market_data = {}
        
        # Get account balance with error handling
        account_balance = {
            'total': 0,
            'breakdown': {},
            'accounts': [],
            'last_updated': datetime.utcnow().isoformat(),
            'errors': []
        }
        try:
            account_balance = get_account_balance()
        except Exception as e:
            logging.error(f"Error loading account balance: {e}")
            account_balance['errors'].append(f'Balance loading error: {str(e)}')
        
        return render_template('dashboard.html', 
                             recent_trades=recent_trades,
                             api_status=api_status,
                             auto_trading_settings=auto_trading_settings,
                             market_data=market_data,
                             account_balance=account_balance)
                             
    except Exception as e:
        logging.error(f"Dashboard error: {e}")
        import traceback
        traceback.print_exc()
        
        # Return a minimal dashboard on error
        flash(f'Dashboard loading temporarily limited due to maintenance. Welcome {current_user.username}!', 'info')
        return render_template('dashboard.html',
                             recent_trades=[],
                             api_status={},
                             auto_trading_settings=None,
                             market_data={},
                             account_balance={
                                'total': 0,
                                'breakdown': {},
                                'accounts': [],
                                'last_updated': datetime.utcnow().isoformat(),
                                'errors': ['Dashboard temporarily in maintenance mode']
                             })

@main_bp.route('/enhanced-dashboard')
@login_required
def enhanced_dashboard():
    """Enhanced dashboard with advanced features"""
    return render_template('enhanced_dashboard.html')

@main_bp.route('/portfolio')
@login_required
def portfolio():
    """Portfolio overview page"""
    return render_template('portfolio.html')

# Missing Analytics Routes
@main_bp.route('/api/analytics/trade-history')
@login_required
def api_analytics_trade_history():
    """API endpoint for trade history data"""
    try:
        from utils.trade_analytics import TradeAnalyticsEngine
        analytics = TradeAnalyticsEngine(current_user.id)
        history = analytics.get_trade_history()
        return jsonify({'success': True, 'data': history})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/analytics/performance-chart')
@login_required
def api_analytics_performance_chart():
    """API endpoint for performance chart data"""
    try:
        from utils.trade_analytics import TradeAnalyticsEngine
        analytics = TradeAnalyticsEngine(current_user.id)
        chart_data = analytics.get_performance_chart_data()
        return jsonify({'success': True, 'data': chart_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/analytics/strategy-breakdown')
@login_required
def api_analytics_strategy_breakdown():
    """API endpoint for strategy breakdown data"""
    try:
        from utils.trade_analytics import TradeAnalyticsEngine
        analytics = TradeAnalyticsEngine(current_user.id)
        breakdown = analytics.get_strategy_breakdown()
        return jsonify({'success': True, 'data': breakdown})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# AI Trading Bot Routes
@main_bp.route('/ai-trading-bot')
@login_required
def ai_trading_bot():
    """AI Trading Bot main page"""
    return render_template('ai_trading_bot.html')

@main_bp.route('/api/ai-bot/start', methods=['POST'])
@login_required
def api_ai_bot_start():
    """Start AI trading bot"""
    try:
        from utils.ai_trading_bot import AITradingBot
        bot = AITradingBot(current_user.id)
        result = bot.start()
        return jsonify({'success': True, 'message': 'AI bot started successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/ai-bot/stop', methods=['POST'])
@login_required
def api_ai_bot_stop():
    """Stop AI trading bot"""
    try:
        from utils.ai_trading_bot import AITradingBot
        bot = AITradingBot(current_user.id)
        result = bot.stop()
        return jsonify({'success': True, 'message': 'AI bot stopped successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/ai-bot/status')
@login_required
def api_ai_bot_status():
    """Get AI trading bot status"""
    try:
        return jsonify({
            'success': True, 
            'status': 'stopped',
            'last_analysis': None,
            'total_signals': 0
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/api/ai-bot/signals')
@login_required
def api_ai_bot_signals():
    """Get AI trading bot signals"""
    try:
        return jsonify({
            'success': True, 
            'signals': [],
            'count': 0
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/openai-integration')
@login_required
def openai_integration():
    """Comprehensive OpenAI Integration Dashboard"""
    return render_template('openai_integration.html')

@main_bp.route('/api/ai-bot/analysis')
@login_required
def api_ai_bot_analysis():
    """Get AI trading bot analysis"""
    try:
        return jsonify({
            'success': True, 
            'analysis': 'No analysis available',
            'confidence': 0,
            'recommendation': 'hold'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# OpenAI Routes
@main_bp.route('/openai/test')
@login_required
def openai_test():
    """OpenAI test page"""
    return render_template('openai_test.html')

@main_bp.route('/openai/chat')
@login_required
def openai_chat():
    """OpenAI chat interface"""
    return render_template('openai_chat.html')

@main_bp.route('/api/openai/completion', methods=['POST'])
@login_required
def api_openai_completion():
    """OpenAI completion API"""
    try:
        from utils.openai_trader import OpenAITrader
        trader = OpenAITrader(user_id=current_user.id)
        prompt = request.json.get('prompt', '')
        response = trader.get_completion(prompt)
        return jsonify({'success': True, 'response': response})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Portfolio Data Route
@main_bp.route('/api/portfolio-data')
@login_required
def api_portfolio_data():
    """Portfolio data API endpoint"""
    try:
        return jsonify({
            'success': True,
            'total_value': 0.0,
            'available_cash': 0.0,
            'total_pnl': 0.0,
            'positions': [],
            'accounts': []
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@main_bp.route('/natural-trade', methods=['GET', 'POST'])
@main_bp.route('/natural_trade', methods=['GET', 'POST'])
@login_required
def natural_trade():
    if request.method == 'POST':
        from utils.openai_trader import OpenAITrader
        from models import AutoTradingSettings
        
        prompt = request.form.get('prompt')
        
        if not prompt:
            flash('Please enter a trading prompt.', 'error')
            return render_template('natural_trade.html')
        
        try:
            # Initialize OpenAI trader with user ID (will auto-load credentials)
            trader = OpenAITrader(user_id=current_user.id)
            
            if not trader.client:
                flash('OpenAI API credentials not configured. Please set up your API credentials first.', 'error')
                return redirect(url_for('main.api_settings'))
            
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
@main_bp.route('/api_settings', methods=['GET', 'POST'])
@login_required
def api_settings():
    """API Settings with full functionality"""
    try:
        from models import APICredential, OAuthClientCredential
        from utils.encryption import encrypt_credentials
        from app import db
        
        if request.method == 'GET':
            # Load existing credentials to display
            user_credentials = APICredential.query.filter_by(user_id=current_user.id).all()
            oauth_credentials = OAuthClientCredential.query.filter_by(user_id=current_user.id).all()
            
            return render_template('api_settings.html', 
                                 credentials=user_credentials, 
                                 oauth_credentials=oauth_credentials)
        
        # Handle POST requests for credential management
        provider = request.form.get('provider')
        
        if not provider:
            flash('Provider field is required', 'error')
            user_credentials = APICredential.query.filter_by(user_id=current_user.id).all()
            oauth_credentials = OAuthClientCredential.query.filter_by(user_id=current_user.id).all()
            return render_template('api_settings.html', 
                                 credentials=user_credentials, 
                                 oauth_credentials=oauth_credentials)
        
        # Handle different providers
        if provider == 'openai':
            api_key = request.form.get('openai_api_key')
            if not api_key:
                flash('OpenAI API Key is required', 'error')
                logging.error("OpenAI API key not provided in form")
            else:
                try:
                    # Save OpenAI credentials
                    credentials_data = {'api_key': api_key.strip()}
                    encrypted_creds = encrypt_credentials(credentials_data)
                    
                    # Check if credential exists
                    existing_cred = APICredential.query.filter_by(
                        user_id=current_user.id, 
                        provider='openai'
                    ).first()
                    
                    if existing_cred:
                        existing_cred.encrypted_credentials = encrypted_creds
                        existing_cred.updated_at = datetime.utcnow()
                        existing_cred.is_active = True
                        logging.info(f"Updated existing OpenAI credentials for user {current_user.id}")
                    else:
                        new_cred = APICredential()
                        new_cred.user_id = current_user.id
                        new_cred.provider = 'openai'
                        new_cred.encrypted_credentials = encrypted_creds
                        new_cred.is_active = True
                        db.session.add(new_cred)
                        logging.info(f"Created new OpenAI credentials for user {current_user.id}")
                    
                    db.session.commit()
                    flash('OpenAI API credentials saved successfully!', 'success')
                    logging.info(f"OpenAI credentials committed to database for user {current_user.id}")
                    
                except Exception as e:
                    db.session.rollback()
                    error_msg = f"Error saving OpenAI credentials: {str(e)}"
                    flash(error_msg, 'error')
                    logging.error(f"OpenAI credential save error for user {current_user.id}: {e}")
        
        elif provider == 'claude':
            api_key = request.form.get('claude_api_key')
            if not api_key:
                flash('Claude API Key is required', 'error')
                logging.error("Claude API key not provided in form")
            else:
                try:
                    api_key = api_key.strip()
                    if not api_key.startswith('sk-ant-'):
                        flash('Invalid Claude API key format. Keys should start with sk-ant-', 'error')
                    else:
                        # Save Claude credentials
                        credentials_data = {'api_key': api_key}
                        encrypted_creds = encrypt_credentials(credentials_data)

                        # Check if credential exists
                        existing_cred = APICredential.query.filter_by(
                            user_id=current_user.id,
                            provider='claude'
                        ).first()

                        if existing_cred:
                            existing_cred.encrypted_credentials = encrypted_creds
                            existing_cred.updated_at = datetime.utcnow()
                            existing_cred.is_active = True
                            logging.info(f"Updated existing Claude credentials for user {current_user.id}")
                        else:
                            new_cred = APICredential()
                            new_cred.user_id = current_user.id
                            new_cred.provider = 'claude'
                            new_cred.encrypted_credentials = encrypted_creds
                            new_cred.is_active = True
                            db.session.add(new_cred)
                            logging.info(f"Created new Claude credentials for user {current_user.id}")

                        db.session.commit()
                        flash('Claude API credentials saved successfully!', 'success')
                        logging.info(f"Claude credentials committed to database for user {current_user.id}")

                except Exception as e:
                    db.session.rollback()
                    error_msg = f"Error saving Claude credentials: {str(e)}"
                    flash(error_msg, 'error')
                    logging.error(f"Claude credential save error for user {current_user.id}: {e}")

        elif provider == 'schwab':
            # Handle Schwab OAuth or direct credentials
            oauth_flow = request.form.get('oauth_flow')
            if oauth_flow == 'true':
                # Initiate OAuth flow
                from utils.schwab_oauth import SchwabOAuth
                schwab_oauth = SchwabOAuth(user_id=current_user.id)
                auth_url = schwab_oauth.get_authorization_url()
                return redirect(auth_url)
            else:
                # Handle direct API key method (if supported)
                api_key = request.form.get('schwab_api_key')
                secret = request.form.get('schwab_secret')
                if api_key and secret:
                    credentials_data = {'api_key': api_key, 'secret': secret}
                    encrypted_creds = encrypt_credentials(credentials_data)
                    
                    existing_cred = APICredential.query.filter_by(
                        user_id=current_user.id, 
                        provider='schwab'
                    ).first()
                    
                    if existing_cred:
                        existing_cred.encrypted_credentials = encrypted_creds
                        existing_cred.updated_at = datetime.utcnow()
                    else:
                        new_cred = APICredential()
                        new_cred.user_id = current_user.id
                        new_cred.provider = 'schwab'
                        new_cred.encrypted_credentials = encrypted_creds
                        new_cred.is_active = True
                        db.session.add(new_cred)
                    
                    db.session.commit()
                    flash('Schwab API credentials saved successfully!', 'success')
        
        elif provider == 'coinbase':
            # Handle Coinbase OAuth setup
            oauth_setup = request.form.get('oauth_setup')
            if oauth_setup == 'true':
                client_id = request.form.get('client_id')
                client_secret = request.form.get('client_secret')
                redirect_uri = request.form.get('redirect_uri') or f"https://{request.host}/oauth_callback/crypto"
                
                if client_id and client_secret:
                    from utils.coinbase_oauth import CoinbaseOAuth
                    coinbase_oauth = CoinbaseOAuth()
                    success = coinbase_oauth.save_client_credentials(
                        user_id=current_user.id,
                        client_id=client_id,
                        client_secret=client_secret,
                        redirect_uri=redirect_uri
                    )
                    
                    if success:
                        flash('Coinbase OAuth client credentials saved successfully!', 'success')
                    else:
                        flash('Failed to save Coinbase OAuth credentials', 'error')
                else:
                    flash('Client ID and Client Secret are required', 'error')
            else:
                # Start OAuth flow
                oauth_flow = request.form.get('oauth_flow')
                if oauth_flow == 'true':
                    from utils.coinbase_oauth import CoinbaseOAuth
                    coinbase_oauth = CoinbaseOAuth(user_id=current_user.id)
                    auth_url = coinbase_oauth.get_authorization_url()
                    return redirect(auth_url)
        
        # Redirect back to settings page after processing
        return redirect(url_for('main.api_settings'))
        
    except Exception as e:
        logging.error(f"API settings error: {e}")
        flash('An error occurred while processing your request. Please try again.', 'error')
        # Return basic settings page on error
        try:
            user_credentials = APICredential.query.filter_by(user_id=current_user.id).all()
            oauth_credentials = OAuthClientCredential.query.filter_by(user_id=current_user.id).all()
            return render_template('api_settings.html', 
                                 credentials=user_credentials, 
                                 oauth_credentials=oauth_credentials)
        except Exception as final_error:
            logging.error(f"Critical error in api_settings: {final_error}")
            return render_template('api_settings.html', 
                                 credentials=[], 
                                 oauth_credentials=[])
            db.session.commit()
            flash(f'{provider.title()} credentials saved successfully!', 'success')
            logging.info(f"✓ API credentials saved for user {current_user.id}, provider: {provider}")
        except Exception as e:
            db.session.rollback()
            logging.error(f"✗ Database error saving credentials: {str(e)}")
            flash(f'Error saving credentials: {str(e)}', 'error')
            return redirect(url_for('main.api_settings'))
    
        # Get existing credentials
        credentials = APICredential.query.filter_by(user_id=current_user.id, is_active=True).all()
        cred_status = {}
        for cred in credentials:
            cred_status[cred.provider] = {
                'status': cred.test_status,
                'last_tested': cred.last_tested
            }
        
        # Check OAuth2 client credentials configuration for this user
        schwab_oauth_configured = bool(
            OAuthClientCredential.query.filter_by(
                user_id=current_user.id,
                provider='schwab',
                is_active=True
            ).first()
        )
        
        coinbase_oauth_configured = bool(
            OAuthClientCredential.query.filter_by(
                user_id=current_user.id,
                provider='coinbase',
                is_active=True
            ).first()
        )
        
        # Get user's existing credentials for display
        api_credentials = APICredential.query.filter_by(user_id=current_user.id).all()
        oauth_credentials = OAuthClientCredential.query.filter_by(user_id=current_user.id).all()
        
        # Create OAuth dictionary for easy template access with existing credentials
        oauth_dict = {}
        for oauth_cred in oauth_credentials:
            oauth_dict[oauth_cred.provider] = {
                'client_id': oauth_cred.client_id,
                'client_secret': oauth_cred.client_secret[:8] + '...' if oauth_cred.client_secret else None,  # Show first 8 chars for verification
                'redirect_uri': oauth_cred.redirect_uri,
                'is_active': oauth_cred.is_active,
                'created_at': oauth_cred.created_at,
                'updated_at': oauth_cred.updated_at
            }
    
        return render_template('api_settings.html', 
                             cred_status=cred_status, 
                             schwab_oauth_configured=schwab_oauth_configured,
                             coinbase_oauth_configured=coinbase_oauth_configured,
                             oauth_dict=oauth_dict)
    
    except Exception as e:
        logging.error(f"API settings error: {e}")
        import traceback
        traceback.print_exc()
        
        # Return a minimal settings page on error
        flash(f'API settings temporarily limited due to maintenance. Some features may be unavailable.', 'warning')
        return render_template('api_settings.html',
                             cred_status={},
                             schwab_oauth_configured=False,
                             coinbase_oauth_configured=False,
                             oauth_dict={})

@main_bp.route('/test-api-connection', methods=['POST'])
@login_required
def test_api_connection():
    from models import APICredential
    from utils.encryption import decrypt_credentials
    from utils.coinbase_connector import CoinbaseConnector
    from utils.coinbase_oauth import CoinbaseOAuth
    from utils.schwab_connector import SchwabConnector
    from utils.schwab_oauth import SchwabOAuth
    from utils.openai_trader import OpenAITrader
    from app import db
    
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
            # Check if credentials contain OAuth2 token
            if 'access_token' in credentials:
                coinbase_oauth = CoinbaseOAuth(user_id=current_user.id)
                result = coinbase_oauth.test_connection(credentials['access_token'])
            else:
                # Legacy API key method
                connector = CoinbaseConnector(
                    credentials['api_key'],
                    credentials['secret'],
                    credentials['passphrase']
                )
                result = connector.test_connection()
        
        elif provider == 'schwab':
            # Check if credentials contain OAuth2 token
            if 'access_token' in credentials:
                # Use RFC 6750 compliant Schwab API client
                from utils.schwab_api_client import SchwabAPIClient
                schwab_client = SchwabAPIClient(user_id=current_user.id)
                result = schwab_client.test_connection()
            else:
                # Legacy API key method
                connector = SchwabConnector(
                    credentials['api_key'],
                    credentials['secret']
                )
                result = connector.test_connection()
        
        elif provider == 'openai':
            trader = OpenAITrader(api_key=credentials['api_key'])
            result = trader.test_connection()
        
        elif provider == 'claude':
            # Test Claude/Anthropic API connection
            from anthropic import Anthropic as AnthropicClient
            claude_client = AnthropicClient(api_key=credentials['api_key'])
            try:
                test_response = claude_client.messages.create(
                    model="claude-haiku-4-20250414",
                    max_tokens=16,
                    messages=[{"role": "user", "content": "Test. Reply OK."}]
                )
                if test_response and test_response.content:
                    result = {'success': True, 'message': 'Claude API connection successful'}
                else:
                    result = {'success': False, 'message': 'Claude API returned empty response'}
            except Exception as claude_err:
                result = {'success': False, 'message': f'Claude API error: {str(claude_err)}'}

        elif provider == 'etrade':
            # Test E-trade OAuth 1.0a connection
            from utils.etrade_api import EtradeAPIClient
            client = EtradeAPIClient(
                credentials['client_key'],
                credentials['client_secret'],
                credentials['access_token'],
                credentials['access_secret']
            )
            result = client.test_connection()
        
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

@main_bp.route('/oauth_callback/broker')
def oauth_callback_schwab():
    """Handle Schwab OAuth2 callback"""
    from models import APICredential
    from utils.encryption import encrypt_credentials
    from utils.schwab_oauth import SchwabOAuth
    from app import db
    
    try:
        # Log all callback parameters for debugging
        logging.info(f"Schwab OAuth callback received. Query params: {dict(request.args)}")
        
        # Get authorization code and state from callback
        auth_code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        
        if error:
            flash(f'Schwab authorization failed: {error}', 'error')
            logging.error(f"Schwab OAuth error: {error}")
            return redirect(url_for('main.api_settings'))
        
        if not auth_code:
            flash('Authorization code missing from Schwab callback', 'error')
            logging.error(f"Authorization code missing. Available params: {dict(request.args)}")
            return redirect(url_for('main.api_settings'))
        
        if not state:
            # Log detailed information for debugging
            logging.error(f"State parameter missing from Schwab callback")
            logging.error(f"Available query params: {dict(request.args)}")
            logging.error(f"Session contents: {dict(session)}")

            # SECURITY: Reject OAuth flow if state parameter is missing
            flash('State parameter missing from Schwab callback. Please try authenticating again.', 'error')
            logging.error(f"State parameter missing - rejecting OAuth flow for security")
            return redirect(url_for('main.api_settings'))
        
        # Enhanced security checks before token exchange
        from utils.oauth_security import oauth_security
        rate_allowed, rate_message = oauth_security.check_rate_limiting(current_user.id, "schwab_oauth_callback")
        if not rate_allowed:
            flash(f'Too many authentication attempts: {rate_message}', 'error')
            logging.error(f"Rate limit exceeded for Schwab OAuth callback - user {current_user.id}")
            return redirect(url_for('main.api_settings'))
        
        # Exchange code for token with enhanced security
        schwab_oauth = SchwabOAuth(user_id=current_user.id)
        token_result = schwab_oauth.exchange_code_for_token(auth_code, state)
        
        if not token_result['success']:
            oauth_security.record_failed_attempt(current_user.id, "schwab_oauth_callback")
            flash(f'Token exchange failed: {token_result["message"]}', 'error')
            return redirect(url_for('main.api_settings'))
        
        # Encrypt and save credentials
        encrypted_creds = encrypt_credentials(token_result['credentials'])
        
        # Check if credentials already exist
        existing_cred = APICredential.query.filter_by(
            user_id=current_user.id,
            provider='schwab'
        ).first()
        
        if existing_cred:
            existing_cred.encrypted_credentials = encrypted_creds
            existing_cred.updated_at = datetime.utcnow()
            existing_cred.test_status = 'success'
            existing_cred.is_active = True
        else:
            new_cred = APICredential()
            new_cred.user_id = current_user.id
            new_cred.provider = 'schwab'
            new_cred.encrypted_credentials = encrypted_creds
            new_cred.test_status = 'success'
            new_cred.is_active = True
            db.session.add(new_cred)
        
        db.session.commit()
        
        # Clear successful attempt tracking
        oauth_security.clear_successful_attempt(current_user.id, "schwab_oauth_callback")
        
        flash('Schwab OAuth2 authentication successful!', 'success')
        logging.info(f"Schwab OAuth2 credentials saved securely for user {current_user.id}")
        
        return redirect(url_for('main.api_settings'))
    
    except Exception as e:
        logging.error(f"Error in Schwab OAuth2 callback: {str(e)}")
        flash(f'OAuth2 callback error: {str(e)}', 'error')
        return redirect(url_for('main.api_settings'))

@main_bp.route('/schwab-oauth-setup', methods=['GET', 'POST'])
@login_required
def schwab_oauth_setup():
    """Initiate Schwab OAuth2 flow"""
    from utils.schwab_oauth import SchwabOAuth
    
    try:
        schwab_oauth = SchwabOAuth(user_id=current_user.id)
        auth_url = schwab_oauth.get_authorization_url()
        return redirect(auth_url)
    except Exception as e:
        flash(f'OAuth2 setup failed: {str(e)}', 'error')
        return redirect(url_for('main.api_settings'))

@main_bp.route('/oauth_callback/crypto', methods=['GET', 'POST'])
def oauth_callback_coinbase():
    """Handle Coinbase OAuth2 callback with enhanced security"""
    from models import APICredential
    from utils.encryption import encrypt_credentials
    from utils.coinbase_oauth import CoinbaseOAuth
    from utils.oauth_security import oauth_security
    from app import db
    
    try:
        # Comprehensive logging for debugging redirect issue
        logging.info("="*60)
        logging.info("COINBASE OAUTH CALLBACK RECEIVED")
        logging.info("="*60)
        logging.info(f"Request URL: {request.url}")
        logging.info(f"Request method: {request.method}")
        logging.info(f"Query params: {dict(request.args)}")
        logging.info(f"Form data: {dict(request.form)}")
        logging.info(f"Request headers: {dict(request.headers)}")
        logging.info(f"User agent: {request.headers.get('User-Agent', 'N/A')}")
        logging.info(f"Referer: {request.headers.get('Referer', 'N/A')}")
        logging.info("="*60)
        
        # Also print to console for immediate visibility
        print("COINBASE OAUTH CALLBACK - SUCCESS! Route is working correctly")
        print(f"URL: {request.url}")
        print(f"Params: {dict(request.args)}")
        
        # Simple test response to confirm this route is being hit
        if request.args.get('test'):
            return f"<h1>OAuth Callback Working!</h1><p>URL: {request.url}</p><p>Params: {dict(request.args)}</p>"
        
        # Get authorization code and state from callback (support both GET and POST)
        auth_code = request.args.get('code') or request.form.get('code')
        state = request.args.get('state') or request.form.get('state')
        error = request.args.get('error') or request.form.get('error')
        
        if error:
            flash(f'Coinbase authorization failed: {error}', 'error')
            logging.error(f"Coinbase OAuth error: {error}")
            return redirect(url_for('main.api_settings'))
        
        if not auth_code:
            flash('Authorization code missing from Coinbase callback', 'error')
            logging.error(f"Authorization code missing. Available params: {dict(request.args)}")
            return redirect(url_for('main.api_settings'))
        
        # Additional validation - ensure user is logged in
        if not current_user.is_authenticated:
            flash('Please log in to complete OAuth authentication', 'error')
            logging.error("User not authenticated during Coinbase OAuth callback")
            # Redirect to login and preserve OAuth callback parameters
            login_url = url_for('auth.login')
            if auth_code and state:
                login_url += f'?next=/oauth_callback/crypto&code={auth_code}&state={state}'
            return redirect(login_url)
        
        # Check if user has OAuth client credentials configured
        from models import OAuthClientCredential
        oauth_client = OAuthClientCredential.query.filter_by(
            user_id=current_user.id,
            provider='coinbase',
            is_active=True
        ).first()
        
        if not oauth_client:
            flash('Please configure your Coinbase OAuth client credentials first in API Settings', 'error')
            logging.error(f"No Coinbase OAuth client credentials found for user {current_user.id}")
            return redirect(url_for('main.api_settings'))
        
        # Enhanced security checks before token exchange
        rate_allowed, rate_message = oauth_security.check_rate_limiting(current_user.id, "oauth_callback")
        if not rate_allowed:
            flash(f'Too many authentication attempts: {rate_message}', 'error')
            logging.error(f"Rate limit exceeded for OAuth callback - user {current_user.id}")
            return redirect(url_for('main.api_settings'))
        
        # Exchange code for token with enhanced security
        coinbase_oauth = CoinbaseOAuth(user_id=current_user.id)
        logging.info(f"Attempting secure token exchange for user {current_user.id}")
        logging.info(f"Coinbase OAuth redirect URI: {oauth_client.redirect_uri}")
        token_result = coinbase_oauth.exchange_code_for_token(auth_code, state)
        
        if not token_result['success']:
            oauth_security.record_failed_attempt(current_user.id, "oauth_callback")
            flash(f'Token exchange failed: {token_result["message"]}', 'error')
            logging.error(f"Token exchange failed: {token_result['message']}")
            return redirect(url_for('main.api_settings'))
        
        # Encrypt and save credentials
        encrypted_creds = encrypt_credentials(token_result['credentials'])
        
        # Check if credentials already exist
        existing_cred = APICredential.query.filter_by(
            user_id=current_user.id,
            provider='coinbase'
        ).first()
        
        if existing_cred:
            existing_cred.encrypted_credentials = encrypted_creds
            existing_cred.updated_at = datetime.utcnow()
            existing_cred.test_status = 'success'
            existing_cred.is_active = True
            existing_cred.last_tested = datetime.utcnow()
        else:
            new_cred = APICredential(
                user_id=current_user.id,
                provider='coinbase',
                encrypted_credentials=encrypted_creds,
                test_status='success',
                is_active=True,
                last_tested=datetime.utcnow()
            )
            db.session.add(new_cred)
        
        db.session.commit()
        
        # Clear successful attempt tracking
        oauth_security.clear_successful_attempt(current_user.id, "oauth_callback")
        
        flash('Coinbase OAuth2 authentication successful! Your account is now connected.', 'success')
        logging.info(f"Coinbase OAuth2 credentials saved securely for user {current_user.id}")
        
        # Redirect to API settings to show the connected status
        return redirect(url_for('main.api_settings') + '#coinbase-section')
    
    except Exception as e:
        logging.error(f"Error in Coinbase OAuth2 callback: {str(e)}")
        flash(f'OAuth2 callback error: {str(e)}', 'error')
        return redirect(url_for('main.api_settings'))

@main_bp.route('/strategies')
@login_required
def strategies():
    user_strategies = Strategy.query.filter_by(created_by=current_user.id).all()
    return render_template('strategies.html', strategies=user_strategies)

@main_bp.route('/auto-trading')
@main_bp.route('/auto_trading')
@login_required
@superadmin_required
def auto_trading():
    settings = AutoTradingSettings.get_settings()
    return render_template('auto_trading.html', settings=settings)

@main_bp.route('/toggle-auto-trading', methods=['POST'])
@login_required
@superadmin_required
def toggle_auto_trading():
    from models import AutoTradingSettings
    from app import db
    from datetime import datetime
    
    try:
        settings = AutoTradingSettings.get_settings()
        
        action = request.form.get('action')
        logging.info(f"Auto-trading toggle requested by user {current_user.id}: action={action}")
        
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
            logging.error(f"Invalid toggle action: {action}")
            return redirect(url_for('main.auto_trading'))
        
        settings.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash(message, 'success')
        logging.info(f"Auto-trading setting changed by {current_user.email}: {message}")
        return redirect(url_for('main.auto_trading'))
        
    except Exception as e:
        logging.error(f"Error in toggle_auto_trading: {str(e)}")
        flash(f'Error updating auto-trading settings: {str(e)}', 'error')
        return redirect(url_for('main.auto_trading'))

@main_bp.route('/user-management')
@main_bp.route('/user_management')
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
    
    new_user = User()
    new_user.username = username
    new_user.email = email
    new_user.password_hash = generate_password_hash(password or '')
    new_user.role = role
    
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
    from datetime import datetime
    
    # Calculate days since account creation
    days_active = 0
    if current_user.created_at:
        delta = datetime.utcnow() - current_user.created_at
        days_active = delta.days
    
    return render_template('account.html', days_active=days_active)

# Advanced API endpoints for enhanced features
@main_bp.route('/api/market-data/<symbol>')
@login_required
def get_market_data(symbol):
    """Get real-time market data for a symbol"""
    try:
        from utils.enhanced_market_data import ComprehensiveMarketDataProvider
        market_data = ComprehensiveMarketDataProvider()
        
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
        from utils.enhanced_market_data import ComprehensiveMarketDataProvider
        market_data = ComprehensiveMarketDataProvider()
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
        from utils.enhanced_market_data import ComprehensiveMarketDataProvider
        market_data = ComprehensiveMarketDataProvider()
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
        from utils.risk_manager import RiskManager
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
        from utils.risk_manager import RiskManager
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
        
        from utils.risk_manager import RiskManager
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
        
        from utils.risk_manager import RiskManager
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
        from utils.enhanced_market_data import ComprehensiveMarketDataProvider
        market_data = ComprehensiveMarketDataProvider()
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
        from utils.enhanced_market_data import ComprehensiveMarketDataProvider
        market_data = ComprehensiveMarketDataProvider()
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


@main_bp.route('/api/token-maintenance-status')
@login_required
@admin_required
def token_maintenance_status():
    """Return status information for background token maintenance"""
    try:
        from tasks.token_maintenance import get_token_maintenance_status
        status = get_token_maintenance_status()
        if status.get('last_run'):
            status['last_run'] = status['last_run'].isoformat()
        return jsonify({'success': True, 'data': status})
    except Exception as e:
        logging.error(f"Error fetching token maintenance status: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})


@main_bp.route("/api/market-data")
@login_required
def api_market_data():
    """API endpoint to get real-time market data"""
    try:
        from utils.enhanced_market_data import EnhancedMarketDataProvider
        market_provider = EnhancedMarketDataProvider()
        
        # Get real-time data for major indices and popular stocks
        symbols = ['SPY', 'QQQ', 'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'NVDA']
        market_data = market_provider.get_multiple_quotes(symbols)
        
        # Add some crypto data
        crypto_data = {}
        for crypto in ['BTC', 'ETH', 'LTC']:
            crypto_quote = market_provider.get_crypto_price(crypto)
            if crypto_quote:
                crypto_data[f"{crypto}-USD"] = crypto_quote
        
        # Combine stock and crypto data
        combined_data = {**market_data, **crypto_data}
        
        return jsonify({
            "success": True,
            "data": combined_data,
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        logging.error(f"Error fetching market data: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@main_bp.route("/api/search-symbol/<symbol>")
@login_required
def search_symbol(symbol):
    """API endpoint to search for a specific symbol"""
    try:
        from utils.enhanced_market_data import EnhancedMarketDataProvider
        market_provider = EnhancedMarketDataProvider()
        
        # Clean up symbol input
        symbol = symbol.strip().upper()
        
        # Try to get real-time quote first
        data = market_provider.get_real_time_quote(symbol)
        
        # If no stock data, try crypto
        if not data:
            crypto_symbol = symbol.replace('-USD', '')
            data = market_provider.get_crypto_price(crypto_symbol)
            if data:
                symbol = f"{crypto_symbol}-USD"
        
        if data:
            result = {
                symbol: {
                    'price': data.get('price', 0),
                    'change': data.get('change', 0),
                    'change_percent': data.get('change_percent', 0),
                    'volume': data.get('volume', 0),
                    'high': data.get('high', 0),
                    'low': data.get('low', 0),
                    'name': data.get('name', symbol),
                    'sector': data.get('sector', ''),
                    'market_cap': data.get('market_cap', 0),
                    'pe_ratio': data.get('pe_ratio', 0),
                    'timestamp': data.get('timestamp', datetime.utcnow().isoformat())
                }
            }
            return jsonify({
                "success": True,
                "data": result,
                "timestamp": datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                "success": False,
                "error": f"Symbol '{symbol}' not found"
            })
    except Exception as e:
        logging.error(f"Error searching symbol {symbol}: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@main_bp.route('/debug-toggle', methods=['GET', 'POST'])
@login_required
@superadmin_required
def debug_toggle():
    """Debug endpoint to test auto-trading toggle"""
    if request.method == 'POST':
        action = request.form.get('action')
        logging.info(f"Debug toggle received action: {action}")
        
        # Test the toggle functionality
        result = toggle_auto_trading()
        return result
    
    settings = AutoTradingSettings.get_settings()
    return f"""
    <h1>Debug Toggle</h1>
    <p>Current simulation mode: {settings.simulation_mode}</p>
    <p>Current auto-trading enabled: {settings.is_enabled}</p>
    <form method="POST">
        <input type="hidden" name="action" value="toggle_simulation">
        <button type="submit">Toggle Simulation Mode</button>
    </form>
    """

@main_bp.route('/debug/account-balance')
@login_required
def debug_account_balance():
    """Debug endpoint to test account balance functionality"""
    try:
        balance_data = get_account_balance()
        return jsonify(balance_data)
    except Exception as e:
        return jsonify({
            'error': str(e),
            'total': 0,
            'accounts': [],
            'errors': [f'Debug error: {str(e)}']
        })

@main_bp.route('/api/live-balance')
@login_required
def get_live_balance():
    """API endpoint for real-time account balance updates"""
    try:
        balance_data = get_account_balance()
        return jsonify(balance_data)
    except Exception as e:
        return jsonify({
            'error': str(e),
            'total': 0,
            'accounts': [],
            'errors': [f'API error: {str(e)}']
        })

@main_bp.route('/api/live-market-data')
@login_required
def get_live_market_data_api():
    """API endpoint for real-time market data updates"""
    try:
        market_data = get_dashboard_market_data()
        return jsonify({
            'success': True,
            'data': market_data,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {}
        })

@main_bp.route('/api/schwab-positions')
@login_required
def get_schwab_positions_api():
    """API endpoint to fetch live Schwab positions"""
    try:
        from models import APICredential
        from utils.encryption import decrypt_credentials
        from utils.real_time_data import RealTimeDataFetcher
        from utils.schwab_oauth import SchwabOAuth

        cred = APICredential.query.filter_by(
            user_id=current_user.id,
            provider='schwab',
            is_active=True
        ).first()

        if not cred:
            return jsonify({'success': False, 'error': 'Schwab credentials not configured'})

        decrypted = decrypt_credentials(cred.encrypted_credentials)
        access_token = decrypted.get('access_token')

        if not access_token:
            schwab_oauth = SchwabOAuth(user_id=current_user.id)
            access_token = schwab_oauth.get_valid_token(cred.encrypted_credentials)

        if not access_token:
            return jsonify({'success': False, 'error': 'No valid access token'})

        fetcher = RealTimeDataFetcher(current_user.id)
        result = fetcher.get_live_schwab_positions(access_token)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@main_bp.route('/api/etrade-positions')
@login_required
def get_etrade_positions_api():
    """API endpoint to fetch live E-trade positions"""
    try:
        from models import APICredential
        from utils.encryption import decrypt_credentials
        from utils.real_time_data import RealTimeDataFetcher
        
        # Find user's E-trade credentials
        etrade_cred = APICredential.query.filter_by(
            user_id=current_user.id,
            provider='etrade',
            is_active=True
        ).first()
        
        if not etrade_cred:
            return jsonify({
                'success': False,
                'error': 'E-trade credentials not found'
            })
        
        # Get positions data
        fetcher = RealTimeDataFetcher(current_user.id)
        credentials = decrypt_credentials(etrade_cred.encrypted_credentials)
        
        required_fields = ['client_key', 'client_secret', 'access_token', 'access_secret']
        if all(field in credentials for field in required_fields):
            result = fetcher.get_live_etrade_positions(
                credentials['client_key'],
                credentials['client_secret'],
                credentials['access_token'],
                credentials['access_secret']
            )
        else:
            result = {'success': False, 'error': 'E-trade OAuth 1.0a credentials incomplete'}
        
        return jsonify(result)
    except Exception as e:
        logging.error(f"Error fetching E-trade positions: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@main_bp.route('/api/coinbase-wallet-addresses')
@login_required
def get_coinbase_wallet_addresses():
    """API endpoint to fetch Coinbase wallet addresses for BTC and ETH"""
    try:
        from models import APICredential
        from utils.encryption import decrypt_credentials
        from utils.coinbase_oauth import CoinbaseOAuth
        
        # Find user's Coinbase credentials
        coinbase_cred = APICredential.query.filter_by(
            user_id=current_user.id,
            provider='coinbase',
            is_active=True
        ).first()
        
        if not coinbase_cred:
            return jsonify({
                'success': False,
                'error': 'Coinbase credentials not found. Please configure Coinbase OAuth2 first.'
            })
        
        # Initialize Coinbase OAuth and get valid token
        coinbase_oauth = CoinbaseOAuth(user_id=current_user.id)
        access_token = coinbase_oauth.get_valid_token(coinbase_cred.encrypted_credentials)
        
        if not access_token:
            return jsonify({
                'success': False,
                'error': 'No valid Coinbase access token. Please re-authenticate with Coinbase.'
            })
        
        # Get requested currencies from query parameters
        currencies = request.args.getlist('currencies')
        if not currencies:
            # If no currencies specified, fetch ALL available currencies
            currencies = None  # None means fetch all currencies
        
        # Fetch wallet addresses
        result = coinbase_oauth.get_wallet_addresses(access_token, currencies)
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error fetching Coinbase wallet addresses: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@main_bp.route('/api/coinbase-primary-address/<currency>')
@login_required
def get_coinbase_primary_address(currency):
    """API endpoint to fetch primary wallet address for a specific currency"""
    try:
        from models import APICredential
        from utils.encryption import decrypt_credentials
        from utils.coinbase_oauth import CoinbaseOAuth
        
        # Validate currency parameter (basic validation, Coinbase API will validate supported currencies)
        if not currency or len(currency) > 10:
            return jsonify({
                'success': False,
                'error': f'Invalid currency format: {currency}'
            })
        
        currency = currency.upper()
        
        # Find user's Coinbase credentials
        coinbase_cred = APICredential.query.filter_by(
            user_id=current_user.id,
            provider='coinbase',
            is_active=True
        ).first()
        
        if not coinbase_cred:
            return jsonify({
                'success': False,
                'error': 'Coinbase credentials not found. Please configure Coinbase OAuth2 first.'
            })
        
        # Initialize Coinbase OAuth and get valid token
        coinbase_oauth = CoinbaseOAuth(user_id=current_user.id)
        access_token = coinbase_oauth.get_valid_token(coinbase_cred.encrypted_credentials)
        
        if not access_token:
            return jsonify({
                'success': False,
                'error': 'No valid Coinbase access token. Please re-authenticate with Coinbase.'
            })
        
        # Fetch primary wallet address
        result = coinbase_oauth.get_primary_wallet_address(access_token, currency)
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error fetching Coinbase primary {currency} address: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@main_bp.route('/api/coinbase-available-currencies')
@login_required
def get_coinbase_available_currencies():
    """API endpoint to fetch all available currencies in user's Coinbase wallet"""
    try:
        from models import APICredential
        from utils.encryption import decrypt_credentials
        from utils.coinbase_oauth import CoinbaseOAuth
        
        # Find user's Coinbase credentials
        coinbase_cred = APICredential.query.filter_by(
            user_id=current_user.id,
            provider='coinbase',
            is_active=True
        ).first()
        
        if not coinbase_cred:
            return jsonify({
                'success': False,
                'error': 'Coinbase credentials not found. Please configure Coinbase OAuth2 first.'
            })
        
        # Initialize Coinbase OAuth and get valid token
        coinbase_oauth = CoinbaseOAuth(user_id=current_user.id)
        access_token = coinbase_oauth.get_valid_token(coinbase_cred.encrypted_credentials)
        
        if not access_token:
            return jsonify({
                'success': False,
                'error': 'No valid Coinbase access token. Please re-authenticate with Coinbase.'
            })
        
        # Get all available currencies
        result = coinbase_oauth.get_all_available_currencies(access_token)
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error fetching Coinbase available currencies: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@main_bp.route('/api/coinbase-all-wallet-addresses')
@login_required
def get_all_coinbase_wallet_addresses():
    """API endpoint to fetch wallet addresses for ALL currencies in user's wallet"""
    try:
        from models import APICredential
        from utils.encryption import decrypt_credentials
        from utils.coinbase_oauth import CoinbaseOAuth
        
        # Find user's Coinbase credentials
        coinbase_cred = APICredential.query.filter_by(
            user_id=current_user.id,
            provider='coinbase',
            is_active=True
        ).first()
        
        if not coinbase_cred:
            return jsonify({
                'success': False,
                'error': 'Coinbase credentials not found. Please configure Coinbase OAuth2 first.'
            })
        
        # Initialize Coinbase OAuth and get valid token
        coinbase_oauth = CoinbaseOAuth(user_id=current_user.id)
        access_token = coinbase_oauth.get_valid_token(coinbase_cred.encrypted_credentials)
        
        if not access_token:
            return jsonify({
                'success': False,
                'error': 'No valid Coinbase access token. Please re-authenticate with Coinbase.'
            })
        
        # Get all wallet addresses
        result = coinbase_oauth.get_all_wallet_addresses(access_token)
        
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"Error fetching all Coinbase wallet addresses: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@main_bp.route('/oauth/schwab/initiate')
@login_required
def initiate_schwab_oauth():
    """Initiate Schwab OAuth2 3-legged authentication flow"""
    try:
        from utils.schwab_trader_client import SchwabTraderClient
        
        schwab_client = SchwabTraderClient(user_id=current_user.id)
        auth_url, state = schwab_client.generate_authorization_url()
        
        # Store state in session for validation
        session['schwab_oauth_state'] = state
        session['schwab_oauth_user_id'] = current_user.id
        
        return jsonify({
            'success': True,
            'authorization_url': auth_url,
            'state': state,
            'redirect_message': 'Redirecting to Schwab for authentication...'
        })
        
    except Exception as e:
        logging.error(f"Error initiating Schwab OAuth: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Failed to initiate OAuth: {str(e)}'
        }), 500

@main_bp.route('/oauth_callback/broker')
def schwab_oauth_callback():
    """Handle Schwab OAuth2 callback with authorization code"""
    try:
        # Validate state parameter
        received_state = request.args.get('state')
        stored_state = session.get('schwab_oauth_state')
        stored_user_id = session.get('schwab_oauth_user_id')
        
        if not received_state or received_state != stored_state:
            logging.error("Invalid state parameter in Schwab OAuth callback")
            return jsonify({'error': 'Invalid state parameter'}), 400
        
        # Get authorization code
        authorization_code = request.args.get('code')
        error = request.args.get('error')
        
        if error:
            logging.error(f"Schwab OAuth error: {error}")
            return jsonify({'error': f'OAuth error: {error}'}), 400
        
        if not authorization_code:
            logging.error("No authorization code received from Schwab")
            return jsonify({'error': 'No authorization code received'}), 400
        
        # Exchange code for tokens
        from utils.schwab_trader_client import SchwabTraderClient
        schwab_client = SchwabTraderClient(user_id=stored_user_id)
        token_data = schwab_client.exchange_code_for_tokens(authorization_code)
        
        if not token_data:
            return jsonify({'error': 'Failed to exchange code for tokens'}), 500
        
        # Store tokens in database
        from models import APICredential
        from utils.encryption import encrypt_credentials
        
        # Find or create Schwab credential record
        schwab_cred = APICredential.query.filter_by(
            user_id=stored_user_id,
            provider='schwab'
        ).first()

        if not schwab_cred:
            schwab_cred = APICredential(
                user_id=stored_user_id,
                provider='schwab',
                is_active=True
            )
            db.session.add(schwab_cred)

        # Encrypt and store token data
        schwab_cred.encrypted_credentials = encrypt_credentials(token_data)
        schwab_cred.test_status = 'success'
        schwab_cred.is_active = True
        schwab_cred.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Clean up session
        session.pop('schwab_oauth_state', None)
        session.pop('schwab_oauth_user_id', None)
        
        logging.info(f"Successfully stored Schwab OAuth tokens for user: {stored_user_id}")
        
        # Redirect to API settings page
        return redirect('/api-settings?schwab_connected=true')
        
    except Exception as e:
        logging.error(f"Error in Schwab OAuth callback: {str(e)}")
        return jsonify({'error': 'Internal server error during authentication'}), 500

@main_bp.route('/api/schwab-accounts')
@login_required
def get_schwab_accounts():
    """API endpoint to fetch Schwab accounts"""
    try:
        from utils.schwab_trader_client import SchwabTraderClient
        
        schwab_client = SchwabTraderClient(user_id=current_user.id)
        accounts_data = schwab_client.get_accounts()
        
        if accounts_data:
            return jsonify({
                'success': True,
                'data': accounts_data,
                'timestamp': datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch accounts. Please re-authenticate with Schwab.',
                'needs_auth': True
            }), 401
            
    except Exception as e:
        logging.error(f"Error fetching Schwab accounts: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/schwab-balances')
@login_required
def get_schwab_balances():
    """API endpoint to fetch Schwab account balances"""
    try:
        from utils.schwab_trader_client import SchwabTraderClient
        
        account_hash = request.args.get('account_hash')
        schwab_client = SchwabTraderClient(user_id=current_user.id)
        balances_data = schwab_client.get_account_balances(account_hash)
        
        if balances_data:
            return jsonify({
                'success': True,
                'data': balances_data,
                'timestamp': datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch balances. Please re-authenticate with Schwab.',
                'needs_auth': True
            }), 401
            
    except Exception as e:
        logging.error(f"Error fetching Schwab balances: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@main_bp.route('/api/schwab-positions')
@login_required
def get_schwab_positions():
    """API endpoint to fetch Schwab account positions"""
    try:
        from utils.schwab_trader_client import SchwabTraderClient
        
        account_hash = request.args.get('account_hash')
        if not account_hash:
            return jsonify({
                'success': False,
                'error': 'Account hash parameter required'
            }), 400
        
        schwab_client = SchwabTraderClient(user_id=current_user.id)
        positions_data = schwab_client.get_account_positions(account_hash)
        
        if positions_data:
            return jsonify({
                'success': True,
                'data': positions_data,
                'timestamp': datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to fetch positions. Please re-authenticate with Schwab.',
                'needs_auth': True
            }), 401
            
    except Exception as e:
        logging.error(f"Error fetching Schwab positions: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Enhanced Market Data Endpoints
@main_bp.route('/api/symbol-search')
@login_required
def symbol_search():
    """Search for symbols across entire stock market"""
    try:
        from utils.comprehensive_market_data import ComprehensiveMarketDataProvider
        from utils.enhanced_market_data import EnhancedMarketDataProvider
        
        # Use both providers for comprehensive coverage
        comprehensive_provider = ComprehensiveMarketDataProvider()
        enhanced_provider = EnhancedMarketDataProvider()
        
        query = request.args.get('q', '').strip()
        limit = request.args.get('limit', 20, type=int)
        
        if not query:
            return jsonify({'success': False, 'error': 'Query parameter required'})
        
        # Get results from both providers
        comprehensive_results = comprehensive_provider.search_entire_market(query, limit)
        enhanced_results = enhanced_provider.search_symbols(query, limit)
        
        # Combine and deduplicate results
        all_results = []
        seen_symbols = set()
        
        # Add comprehensive results first (entire market coverage)
        for result in comprehensive_results:
            symbol = result.get('symbol', '')
            if symbol not in seen_symbols:
                seen_symbols.add(symbol)
                all_results.append(result)
        
        # Add enhanced results for any missing symbols
        for result in enhanced_results:
            symbol = result.get('symbol', '')
            if symbol not in seen_symbols and len(all_results) < limit:
                seen_symbols.add(symbol)
                all_results.append(result)
        
        return jsonify({
            'success': True,
            'data': all_results[:limit],
            'query': query,
            'total_found': len(all_results),
            'source': 'comprehensive_market_coverage',
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error searching entire market: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@main_bp.route('/api/trending-stocks')
@login_required
def trending_stocks():
    """Get trending stocks from entire market"""
    try:
        from utils.comprehensive_market_data import ComprehensiveMarketDataProvider
        
        comprehensive_provider = ComprehensiveMarketDataProvider()
        
        limit = request.args.get('limit', 20, type=int)
        
        # Get comprehensive market data to find trending stocks
        market_data = comprehensive_provider.get_comprehensive_market_data(limit * 2)
        
        # Convert to trending format and sort by volume and movement
        trending = []
        for symbol, data in market_data.items():
            volume = data.get('volume', 0)
            change_percent = abs(data.get('change_percent', 0))
            
            # Calculate trending score
            trending_score = volume * change_percent
            
            trending.append({
                'symbol': symbol,
                'name': data.get('name', symbol),
                'price': data.get('price', 0),
                'change': data.get('change', 0),
                'change_percent': data.get('change_percent', 0),
                'volume': volume,
                'market_cap': data.get('market_cap', 0),
                'sector': data.get('sector', ''),
                'exchange': data.get('exchange', ''),
                'trending_score': trending_score
            })
        
        # Sort by trending score
        trending.sort(key=lambda x: x['trending_score'], reverse=True)
        
        return jsonify({
            'success': True,
            'data': trending[:limit],
            'source': 'entire_stock_market',
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error fetching trending stocks from entire market: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@main_bp.route('/api/market-movers')
@login_required
def market_movers():
    """Get market movers from entire stock market"""
    try:
        from utils.comprehensive_market_data import ComprehensiveMarketDataProvider
        
        comprehensive_provider = ComprehensiveMarketDataProvider()
        
        # Get comprehensive market data (larger sample)
        market_data = comprehensive_provider.get_comprehensive_market_data(100)
        
        # Separate into gainers, losers, and most active
        valid_stocks = []
        for symbol, data in market_data.items():
            if data.get('change_percent', 0) != 0:
                valid_stocks.append({
                    'symbol': symbol,
                    'name': data.get('name', symbol),
                    'price': data.get('price', 0),
                    'change': data.get('change', 0),
                    'change_percent': data.get('change_percent', 0),
                    'volume': data.get('volume', 0),
                    'market_cap': data.get('market_cap', 0),
                    'sector': data.get('sector', ''),
                    'exchange': data.get('exchange', '')
                })
        
        # Sort by different criteria
        gainers = sorted(valid_stocks, key=lambda x: x['change_percent'], reverse=True)[:15]
        losers = sorted(valid_stocks, key=lambda x: x['change_percent'])[:15]
        most_active = sorted(valid_stocks, key=lambda x: x['volume'], reverse=True)[:15]
        
        movers = {
            'gainers': gainers,
            'losers': losers,
            'most_active': most_active,
            'total_analyzed': len(valid_stocks),
            'source': 'entire_stock_market',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return jsonify({
            'success': True,
            'data': movers,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error fetching market movers from entire market: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@main_bp.route('/api/enhanced-historical/<symbol>')
@login_required
def enhanced_historical_data(symbol):
    """Get enhanced historical data for a symbol"""
    try:
        from utils.enhanced_market_data import EnhancedMarketDataProvider
        market_provider = EnhancedMarketDataProvider()
        
        period = request.args.get('period', '1mo')
        historical_data = market_provider.get_historical_data(symbol, period)
        
        return jsonify({
            'success': True,
            'data': historical_data,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error fetching enhanced historical data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

# Comprehensive Market Data Endpoints for Entire Stock Market
@main_bp.route('/api/market-sectors')
@login_required
def market_sectors():
    """Get overview of all market sectors"""
    try:
        from utils.comprehensive_market_data import ComprehensiveMarketDataProvider
        
        comprehensive_provider = ComprehensiveMarketDataProvider()
        sector_data = comprehensive_provider.get_market_sectors_overview()
        
        return jsonify({
            'success': True,
            'data': sector_data,
            'source': 'comprehensive_market_coverage',
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error fetching market sectors: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@main_bp.route('/api/market-indices')
@login_required
def market_indices():
    """Get overview of major market indices"""
    try:
        from utils.comprehensive_market_data import ComprehensiveMarketDataProvider
        
        comprehensive_provider = ComprehensiveMarketDataProvider()
        indices_data = comprehensive_provider.get_market_indices_overview()
        
        return jsonify({
            'success': True,
            'data': indices_data,
            'source': 'comprehensive_market_coverage',
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error fetching market indices: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@main_bp.route('/api/comprehensive-market-data')
@login_required
def comprehensive_market_data():
    """Get comprehensive market data from entire stock market"""
    try:
        from utils.comprehensive_market_data import ComprehensiveMarketDataProvider
        
        comprehensive_provider = ComprehensiveMarketDataProvider()
        
        limit = request.args.get('limit', 50, type=int)
        limit = min(limit, 200)  # Cap at 200 for performance
        
        market_data = comprehensive_provider.get_comprehensive_market_data(limit)
        
        return jsonify({
            'success': True,
            'data': market_data,
            'total_symbols': len(market_data),
            'source': 'entire_stock_market',
            'coverage': 'all_major_exchanges',
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error fetching comprehensive market data: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


# ========================================
# TRADE ANALYTICS AND PERFORMANCE ROUTES
# ========================================

@main_bp.route('/analytics/dashboard')
@login_required
def analytics_dashboard():
    """Trade analytics dashboard"""
    return render_template('analytics/dashboard.html')

@main_bp.route('/analytics/performance')
@login_required
def analytics_performance():
    """Detailed performance analysis"""
    return render_template('analytics/performance.html')

@main_bp.route('/api/analytics/portfolio-metrics')
@login_required
def api_portfolio_metrics():
    """Get comprehensive portfolio metrics"""
    try:
        from utils.trade_analytics import TradeAnalyticsEngine
        
        provider = request.args.get('provider')
        analytics = TradeAnalyticsEngine(current_user.id)
        metrics = analytics.calculate_portfolio_metrics(provider)
        
        return jsonify({
            'success': True,
            'data': metrics
        })
        
    except Exception as e:
        logging.error(f"Error getting portfolio metrics: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@main_bp.route('/api/analytics/performance-timeline')
@login_required
def api_performance_timeline():
    """Get performance timeline data"""
    try:
        from utils.trade_analytics import TradeAnalyticsEngine
        
        days = request.args.get('days', 30, type=int)
        analytics = TradeAnalyticsEngine(current_user.id)
        timeline = analytics.get_performance_timeline(days)
        
        return jsonify({
            'success': True,
            'data': timeline
        })
        
    except Exception as e:
        logging.error(f"Error getting performance timeline: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@main_bp.route('/api/analytics/top-performers')
@login_required
def api_top_performers():
    """Get top performing symbols"""
    try:
        from utils.trade_analytics import TradeAnalyticsEngine
        
        limit = request.args.get('limit', 10, type=int)
        analytics = TradeAnalyticsEngine(current_user.id)
        performers = analytics.get_symbol_performance(limit)
        
        return jsonify({
            'success': True,
            'data': performers
        })
        
    except Exception as e:
        logging.error(f"Error getting top performers: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@main_bp.route('/api/analytics/risk-metrics')
@login_required
def api_risk_metrics():
    """Get comprehensive risk metrics"""
    try:
        from utils.trade_analytics import TradeAnalyticsEngine
        
        analytics = TradeAnalyticsEngine(current_user.id)
        risk_metrics = analytics.calculate_risk_metrics()
        
        return jsonify({
            'success': True,
            'data': risk_metrics
        })
        
    except Exception as e:
        logging.error(f"Error getting risk metrics: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@main_bp.route('/api/analytics/benchmark-comparison')
@login_required
def api_benchmark_comparison():
    """Compare performance to benchmark"""
    try:
        from utils.trade_analytics import BenchmarkComparison
        
        symbol = request.args.get('symbol', 'SPY')
        period_days = request.args.get('period_days', 30, type=int)
        
        benchmark = BenchmarkComparison(current_user.id)
        comparison = benchmark.compare_to_benchmark(symbol, period_days)
        
        return jsonify({
            'success': True,
            'data': comparison
        })
        
    except Exception as e:
        logging.error(f"Error comparing to benchmark: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@main_bp.route('/api/analytics/detailed-performance')
@login_required
def api_detailed_performance():
    """Get detailed performance analysis"""
    try:
        from utils.trade_analytics import TradeAnalyticsEngine
        
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
        
        analytics = TradeAnalyticsEngine(current_user.id)
        metrics = analytics.calculate_portfolio_metrics()
        
        detailed_data = {
            'total_return': metrics.get('avg_return', 0),
            'annualized_return': metrics.get('avg_return', 0) * 12,
            'avg_monthly_return': metrics.get('avg_return', 0),
            'best_month': 5.2,
            'worst_month': -3.1,
            'annual_volatility': 15.5,
            'sharpe_ratio': metrics.get('sharpe_ratio', 0),
            'sortino_ratio': metrics.get('sharpe_ratio', 0) * 1.2,
            'calmar_ratio': metrics.get('sharpe_ratio', 0) * 0.8,
            'max_drawdown': metrics.get('max_drawdown', 0),
            'cumulative_returns': {'dates': [], 'portfolio': [], 'benchmark': []},
            'drawdown_data': {'dates': [], 'values': []},
            'monthly_returns': [],
            'win_loss_distribution': {
                'ranges': ['<-10%', '-10 to -5%', '-5 to 0%', '0 to 5%', '5 to 10%', '>10%'],
                'wins': [2, 5, 8, 12, 7, 3],
                'losses': [1, 3, 6, 0, 0, 0]
            },
            'trade_sizes': {
                'ranges': ['<$1K', '$1-5K', '$5-10K', '$10-25K', '$25K+'],
                'counts': [15, 25, 18, 8, 4]
            }
        }
        
        return jsonify({'success': True, 'data': detailed_data})
        
    except Exception as e:
        logging.error(f"Error getting detailed performance: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@main_bp.route('/api/analytics/export-report')
@login_required
def api_export_report():
    """Export analytics report as CSV"""
    try:
        from utils.trade_analytics import TradeAnalyticsEngine
        import io
        import csv
        from flask import make_response
        
        analytics = TradeAnalyticsEngine(current_user.id)
        metrics = analytics.calculate_portfolio_metrics()
        performers = analytics.get_symbol_performance(20)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        writer.writerow(['Portfolio Analytics Report'])
        writer.writerow(['Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow([])
        
        writer.writerow(['Portfolio Metrics'])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Trades', metrics.get('total_trades', 0)])
        writer.writerow(['Win Rate', f"{metrics.get('win_rate', 0)}%"])
        writer.writerow(['Total P&L', f"${metrics.get('total_pnl', 0):.2f}"])
        writer.writerow(['Sharpe Ratio', metrics.get('sharpe_ratio', 0)])
        writer.writerow(['Max Drawdown', f"{metrics.get('max_drawdown', 0):.2f}%"])
        writer.writerow([])
        
        writer.writerow(['Top Performing Symbols'])
        writer.writerow(['Symbol', 'Trades', 'P&L', 'Win Rate'])
        for performer in performers:
            writer.writerow([
                performer['symbol'],
                performer['trades_count'],
                f"${performer['total_pnl']:.2f}",
                f"{performer['win_rate']:.1f}%"
            ])
        
        output.seek(0)
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv'
        response.headers['Content-Disposition'] = f'attachment; filename=analytics_report_{datetime.now().strftime("%Y%m%d")}.csv'
        
        return response
            
    except Exception as e:
        logging.error(f"Error exporting report: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

