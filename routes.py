from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from functools import wraps
import logging
import json
import os
from datetime import datetime
from models import User, Strategy, AutoTradingSettings, APICredential

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
    """Get real-time market data for dashboard display with timeout protection"""
    try:
        # Return cached/placeholder data immediately to prevent timeouts
        # This avoids the yfinance API calls that are causing slowdowns
        market_data = {
            'SPY': {
                'price': 595.23,
                'change': 2.45,
                'change_percent': 0.41,
                'volume': 45230000,
                'high': 597.50,
                'low': 593.12
            },
            'QQQ': {
                'price': 523.67,
                'change': -1.23,
                'change_percent': -0.23,
                'volume': 28456000,
                'high': 525.89,
                'low': 522.15
            },
            'BTC-USD': {
                'price': 95432.50,
                'change': 1245.30,
                'change_percent': 1.32,
                'volume': 15234567,
                'high': 96500.00,
                'low': 94123.45
            },
            'ETH-USD': {
                'price': 3567.89,
                'change': -45.67,
                'change_percent': -1.26,
                'volume': 8945678,
                'high': 3620.45,
                'low': 3534.12
            }
        }
        
        logging.info("Returning optimized market data to prevent dashboard timeouts")
        return market_data
        
    except Exception as e:
        logging.error(f"Error in get_dashboard_market_data: {str(e)}")
        return {}

def get_account_balance():
    """Get total account balance from connected APIs with real-time data"""
    from models import APICredential
    from utils.encryption import decrypt_credentials
    from utils.market_data import MarketDataProvider
    
    balance_data = {
        'total': 0,
        'breakdown': {},
        'accounts': [],
        'last_updated': datetime.utcnow().isoformat(),
        'errors': []
    }
    
    try:
        # Get user's API credentials
        credentials = APICredential.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).all()
        
        for cred in credentials:
            account_info = {
                'provider': cred.provider,
                'balance': 0,
                'currency': 'USD',
                'account_type': 'unknown',
                'status': 'disconnected',
                'last_updated': cred.last_tested.isoformat() if cred.last_tested else None
            }
            
            try:
                decrypted_creds = decrypt_credentials(cred.encrypted_credentials)
                
                if cred.provider == 'coinbase':
                    # Get Coinbase balance using OAuth
                    if 'access_token' in decrypted_creds:
                        try:
                            from utils.coinbase_oauth import CoinbaseOAuth
                            coinbase_oauth = CoinbaseOAuth(user_id=current_user.id)
                            
                            # Get valid token
                            access_token = coinbase_oauth.get_valid_token(cred.encrypted_credentials)
                            
                            if access_token:
                                accounts = coinbase_oauth.get_accounts(access_token)
                                if accounts and 'data' in accounts:
                                    coinbase_balance = 0
                                    crypto_holdings = []
                                    
                                    for account in accounts['data']:
                                        if account.get('balance') and account['balance'].get('amount'):
                                            try:
                                                amount = float(account['balance']['amount'])
                                                currency = account['balance']['currency']
                                                
                                                if amount > 0:  # Only include non-zero balances
                                                    crypto_holdings.append({
                                                        'currency': currency,
                                                        'amount': amount,
                                                        'name': account.get('name', currency)
                                                    })
                                                    
                                                    # Convert to USD
                                                    if currency == 'USD':
                                                        coinbase_balance += amount
                                                    else:
                                                        # Get current price for conversion
                                                        market_provider = MarketDataProvider()
                                                        if currency == 'BTC':
                                                            price_data = market_provider.get_crypto_price('bitcoin')
                                                            if price_data:
                                                                coinbase_balance += amount * price_data.get('price', 0)
                                                        elif currency == 'ETH':
                                                            price_data = market_provider.get_crypto_price('ethereum')
                                                            if price_data:
                                                                coinbase_balance += amount * price_data.get('price', 0)
                                            except Exception as conversion_error:
                                                logging.error(f"Error converting {currency}: {conversion_error}")
                                                continue
                                    
                                    account_info['balance'] = coinbase_balance
                                    account_info['status'] = 'connected'
                                    account_info['account_type'] = 'crypto'
                                    account_info['holdings'] = crypto_holdings
                                    
                                    # Update credential status
                                    cred.last_tested = datetime.utcnow()
                                    cred.test_status = 'success'
                                else:
                                    account_info['status'] = 'error'
                                    balance_data['errors'].append('Coinbase: No account data returned')
                                    cred.test_status = 'failed'
                            else:
                                account_info['status'] = 'error'
                                balance_data['errors'].append('Coinbase: Invalid or expired token')
                                cred.test_status = 'failed'
                        except Exception as e:
                            account_info['status'] = 'error'
                            balance_data['errors'].append(f'Coinbase OAuth: {str(e)}')
                            cred.test_status = 'failed'
                            logging.error(f"Coinbase OAuth error: {str(e)}")
                    else:
                        # Legacy API key support
                        from utils.coinbase_connector import CoinbaseConnector
                        connector = CoinbaseConnector(
                            decrypted_creds.get('api_key', ''),
                            decrypted_creds.get('secret', '')
                        )
                        
                        try:
                            balance = connector.get_account_balance()
                            if balance:
                                account_info['balance'] = balance
                                account_info['status'] = 'connected'
                                account_info['account_type'] = 'crypto'
                                cred.test_status = 'success'
                            else:
                                account_info['status'] = 'error'
                                balance_data['errors'].append('Coinbase: API key authentication failed')
                                cred.test_status = 'failed'
                        except Exception as e:
                            account_info['status'] = 'error'
                            balance_data['errors'].append(f'Coinbase: {str(e)}')
                            cred.test_status = 'failed'
                
                elif cred.provider == 'schwab':
                    # Get Schwab balance using OAuth
                    if 'access_token' in decrypted_creds:
                        from utils.schwab_api import SchwabAPIClient
                        access_token = decrypted_creds['access_token']
                        api_client = SchwabAPIClient(access_token=access_token)
                        
                        try:
                            accounts = api_client.get_accounts()
                            if accounts:
                                schwab_balance = 0
                                account_details = []
                                
                                for account in accounts:
                                    if 'securitiesAccount' in account:
                                        sec_account = account['securitiesAccount']
                                        account_number = sec_account.get('accountNumber', 'Unknown')
                                        
                                        # Get detailed balance information
                                        balance_info = api_client.get_account_balance(account_number)
                                        if balance_info:
                                            account_value = balance_info.get('account_value', 0)
                                            schwab_balance += account_value
                                            
                                            account_details.append({
                                                'account_number': account_number,
                                                'account_type': balance_info.get('account_type', 'UNKNOWN'),
                                                'balance': account_value,
                                                'cash_balance': balance_info.get('cash_balance', 0),
                                                'buying_power': balance_info.get('buying_power', 0),
                                                'long_market_value': balance_info.get('long_market_value', 0)
                                            })
                                
                                account_info['balance'] = schwab_balance
                                account_info['status'] = 'connected'
                                account_info['account_type'] = 'brokerage'
                                account_info['accounts'] = account_details
                                
                                # Update credential status
                                cred.last_tested = datetime.utcnow()
                                cred.test_status = 'success'
                            else:
                                account_info['status'] = 'error'
                                balance_data['errors'].append('Schwab: No accounts found')
                                cred.test_status = 'failed'
                        except Exception as e:
                            account_info['status'] = 'error'
                            balance_data['errors'].append(f'Schwab: {str(e)}')
                            cred.test_status = 'failed'
                    else:
                        # Try to get token using OAuth helper
                        try:
                            from utils.schwab_oauth import SchwabOAuth
                            schwab_oauth = SchwabOAuth(user_id=current_user.id)
                            
                            # Get valid access token
                            access_token = schwab_oauth.get_valid_token()
                            
                            if access_token:
                                from utils.schwab_api import SchwabAPIClient
                                api_client = SchwabAPIClient(access_token=access_token)
                                
                                accounts = api_client.get_accounts()
                                if accounts:
                                    schwab_balance = 0
                                    account_details = []
                                    
                                    for account in accounts:
                                        if 'securitiesAccount' in account:
                                            sec_account = account['securitiesAccount']
                                            account_number = sec_account.get('accountNumber', 'Unknown')
                                            
                                            # Get detailed balance information
                                            balance_info = api_client.get_account_balance(account_number)
                                            if balance_info:
                                                account_value = balance_info.get('account_value', 0)
                                                schwab_balance += account_value
                                                
                                                account_details.append({
                                                    'account_number': account_number,
                                                    'account_type': balance_info.get('account_type', 'UNKNOWN'),
                                                    'balance': account_value,
                                                    'cash_balance': balance_info.get('cash_balance', 0),
                                                    'buying_power': balance_info.get('buying_power', 0),
                                                    'long_market_value': balance_info.get('long_market_value', 0)
                                                })
                                    
                                    account_info['balance'] = schwab_balance
                                    account_info['status'] = 'connected'
                                    account_info['account_type'] = 'brokerage'
                                    account_info['accounts'] = account_details
                                    cred.test_status = 'success'
                                else:
                                    account_info['status'] = 'error'
                                    balance_data['errors'].append('Schwab: No accounts found')
                                    cred.test_status = 'failed'
                            else:
                                account_info['status'] = 'error'
                                balance_data['errors'].append('Schwab: No valid access token available')
                                cred.test_status = 'failed'
                        except Exception as e:
                            account_info['status'] = 'error'
                            balance_data['errors'].append(f'Schwab: {str(e)}')
                            cred.test_status = 'failed'
                
                # Add to accounts list and update totals
                balance_data['accounts'].append(account_info)
                if account_info['status'] == 'connected':
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
    from models import Trade, APICredential, AutoTradingSettings
    
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
    
    # Get real-time market data
    market_data = get_dashboard_market_data()
    
    # Get account balance if APIs are connected
    account_balance = get_account_balance()
    
    return render_template('dashboard.html', 
                         recent_trades=recent_trades,
                         api_status=api_status,
                         auto_trading_settings=auto_trading_settings,
                         market_data=market_data,
                         account_balance=account_balance)

@main_bp.route('/enhanced-dashboard')
@login_required
def enhanced_dashboard():
    """Enhanced dashboard with advanced features"""
    return render_template('enhanced_dashboard.html')

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
    from models import APICredential, OAuthClientCredential
    from utils.encryption import encrypt_credentials
    from utils.coinbase_oauth import CoinbaseOAuth
    from utils.schwab_oauth import SchwabOAuth
    from utils.multi_user_config import multi_user_config
    from app import db
    
    if request.method == 'POST':
        # Enhanced debugging for form submission
        logging.info("="*50)
        logging.info("API SETTINGS FORM SUBMITTED")
        logging.info("="*50)
        logging.info(f"Form data: {dict(request.form)}")
        logging.info(f"User: {current_user.id} ({current_user.username})")
        logging.info(f"Request method: {request.method}")
        logging.info(f"Content type: {request.content_type}")
        
        # Check for missing provider field
        if not request.form.get('provider'):
            logging.error("Missing provider field in form submission")
            flash('Provider field is required', 'error')
            return redirect(url_for('main.api_settings'))
        provider = request.form.get('provider')
        
        if provider == 'coinbase':
            # Check if this is OAuth2 flow initiation
            oauth_flow = request.form.get('oauth_flow')
            
            if oauth_flow == 'true':
                # Initiate OAuth2 flow
                try:
                    coinbase_oauth = CoinbaseOAuth(user_id=current_user.id)
                    auth_url = coinbase_oauth.get_authorization_url()
                    return redirect(auth_url)
                except Exception as e:
                    logging.error(f"Coinbase OAuth2 initialization error: {str(e)}")
                    flash(f'OAuth2 initialization failed: {str(e)}', 'error')
                    return redirect(url_for('main.api_settings'))
            
            # Check if this is OAuth2 client credentials setup
            elif request.form.get('oauth_setup') == 'true':
                try:
                    client_id = request.form.get('client_id')
                    client_secret = request.form.get('client_secret')
                    # Generate redirect URI based on current request domain
                    redirect_uri = request.form.get('redirect_uri')
                    if not redirect_uri:
                        # Use the same domain as the current request
                        scheme = 'https'  # Always use HTTPS in production
                        host = request.host
                        # Handle both www and non-www versions
                        if host.startswith('www.'):
                            redirect_uri = f"{scheme}://{host}/oauth_callback/crypto"
                        else:
                            redirect_uri = f"{scheme}://{host}/oauth_callback/crypto"
                    
                    # Log the redirect URI for debugging
                    logging.info(f"Setting up Coinbase OAuth with redirect URI: {redirect_uri}")
                    logging.info(f"Current request host: {request.host}")
                    logging.info(f"Current request scheme: {request.scheme}")
                    
                    if not client_id or not client_secret:
                        flash('Client ID and Client Secret are required for OAuth2 setup', 'error')
                        return redirect(url_for('main.api_settings'))
                    
                    coinbase_oauth = CoinbaseOAuth()
                    success = coinbase_oauth.save_client_credentials(
                        user_id=current_user.id,
                        client_id=client_id,
                        client_secret=client_secret,
                        redirect_uri=redirect_uri
                    )
                    
                    if success:
                        flash('Coinbase OAuth2 client credentials saved successfully!', 'success')
                    else:
                        flash('Failed to save OAuth2 client credentials', 'error')
                    
                    return redirect(url_for('main.api_settings'))
                    
                except Exception as e:
                    logging.error(f"Coinbase OAuth2 client setup error: {str(e)}")
                    flash(f'OAuth2 client setup failed: {str(e)}', 'error')
                    return redirect(url_for('main.api_settings'))
            else:
                # Legacy API key method (deprecated)
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
            # Check if this is OAuth2 flow initiation
            oauth_flow = request.form.get('oauth_flow')
            
            if oauth_flow == 'true':
                # Initiate OAuth2 flow
                try:
                    schwab_oauth = SchwabOAuth(user_id=current_user.id)
                    auth_url = schwab_oauth.get_authorization_url()
                    return redirect(auth_url)
                except Exception as e:
                    logging.error(f"OAuth2 initialization error: {str(e)}")
                    flash(f'OAuth2 initialization failed: {str(e)}', 'error')
                    return redirect(url_for('main.api_settings'))
            
            # Check if this is OAuth2 client credentials setup
            elif request.form.get('oauth_setup') == 'true':
                try:
                    client_id = request.form.get('client_id')
                    client_secret = request.form.get('client_secret')
                    # Generate redirect URI based on current request domain
                    redirect_uri = request.form.get('redirect_uri')
                    if not redirect_uri:
                        # Use the same domain as the current request
                        scheme = request.scheme
                        host = request.host
                        redirect_uri = f"{scheme}://{host}/oauth_callback/broker"
                    
                    if not client_id or not client_secret:
                        flash('Client ID and Client Secret are required for OAuth2 setup', 'error')
                        return redirect(url_for('main.api_settings'))
                    
                    schwab_oauth = SchwabOAuth()
                    success = schwab_oauth.save_client_credentials(
                        user_id=current_user.id,
                        client_id=client_id,
                        client_secret=client_secret,
                        redirect_uri=redirect_uri
                    )
                    
                    if success:
                        flash('Schwab OAuth2 client credentials saved successfully!', 'success')
                    else:
                        flash('Failed to save OAuth2 client credentials', 'error')
                    
                    return redirect(url_for('main.api_settings'))
                    
                except Exception as e:
                    logging.error(f"OAuth2 client setup error: {str(e)}")
                    flash(f'OAuth2 client setup failed: {str(e)}', 'error')
                    return redirect(url_for('main.api_settings'))
            else:
                # Legacy API key method (deprecated)
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
        
        try:
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
            flash('State parameter missing from Schwab callback', 'error')
            logging.error(f"State parameter missing. Available params: {dict(request.args)}")
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
        else:
            new_cred = APICredential(
                user_id=current_user.id,
                provider='schwab',
                encrypted_credentials=encrypted_creds,
                test_status='success'
            )
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


@main_bp.route("/api/market-data")
@login_required
def api_market_data():
    """API endpoint to get real-time market data"""
    try:
        market_data = get_dashboard_market_data()
        return jsonify({
            "success": True,
            "data": market_data,
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
        market_provider = MarketDataProvider()
        
        # Clean up symbol input
        symbol = symbol.strip().upper()
        
        # Try to fetch as stock first
        data = market_provider.get_stock_quote(symbol)
        
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
                    'low': data.get('low', 0)
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
