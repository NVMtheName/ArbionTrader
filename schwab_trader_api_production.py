#!/usr/bin/env python3
"""
Schwab Trader API Production Integration
Production-ready Python script for Schwab Trader API with OAuth2 3-legged authentication

Features:
- 3-legged OAuth2 authorization code flow
- Secure token storage and refresh logic
- Account and balance fetching
- Production error handling
- Flask endpoints for OAuth callback
- Heroku/Replit deployment ready

Author: Arbion AI Trading Platform
Environment: Production
"""

import os
import json
import time
import logging
import hashlib
import secrets
import urllib.parse
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List

import requests
from flask import Flask, request, jsonify, redirect, url_for, session, render_template_string
from werkzeug.middleware.proxy_fix import ProxyFix

# =============================================================================
# CONFIGURATION SECTION
# =============================================================================

# Environment Variables (Replace with your actual values)
SCHWAB_CLIENT_ID = os.environ.get('SCHWAB_CLIENT_ID', 'YOUR_CLIENT_ID_HERE')
SCHWAB_CLIENT_SECRET = os.environ.get('SCHWAB_CLIENT_SECRET', 'YOUR_CLIENT_SECRET_HERE')
SCHWAB_REDIRECT_URI = os.environ.get('SCHWAB_REDIRECT_URI', 'https://www.arbion.ai/oauth_callback/broker')
FLASK_SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', secrets.token_urlsafe(32))

# Schwab API Configuration
SCHWAB_BASE_URL = 'https://api.schwabapi.com'
SCHWAB_AUTH_URL = 'https://api.schwabapi.com/v1/oauth/authorize'
SCHWAB_TOKEN_URL = 'https://api.schwabapi.com/v1/oauth/token'

# Application Configuration
DEBUG_MODE = os.environ.get('DEBUG', 'False').lower() == 'true'
PORT = int(os.environ.get('PORT', 5000))

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

logging.basicConfig(
    level=logging.INFO if not DEBUG_MODE else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class SchwabTokens:
    """Data class for Schwab OAuth2 tokens"""
    access_token: str
    refresh_token: str
    token_type: str = 'Bearer'
    expires_in: int = 1800  # 30 minutes default
    scope: str = 'api'
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.expires_at is None:
            self.expires_at = self.created_at + timedelta(seconds=self.expires_in)
    
    def is_expired(self, buffer_seconds: int = 300) -> bool:
        """Check if token is expired with buffer time"""
        if self.expires_at is None:
            return True
        return datetime.utcnow() + timedelta(seconds=buffer_seconds) >= self.expires_at
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        if self.expires_at:
            data['expires_at'] = self.expires_at.isoformat()
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SchwabTokens':
        """Create instance from dictionary"""
        if 'expires_at' in data and data['expires_at']:
            data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        if 'created_at' in data and data['created_at']:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)

# =============================================================================
# TOKEN STORAGE (In-Memory with Basic Persistence)
# =============================================================================

class TokenStorage:
    """Simple token storage with in-memory and basic file persistence"""
    
    def __init__(self, storage_file: str = 'schwab_tokens.json'):
        self.storage_file = storage_file
        self.tokens: Dict[str, SchwabTokens] = {}
        self.load_tokens()
    
    def load_tokens(self):
        """Load tokens from file if exists"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    for user_id, token_data in data.items():
                        self.tokens[user_id] = SchwabTokens.from_dict(token_data)
                logger.info(f"Loaded {len(self.tokens)} token(s) from storage")
        except Exception as e:
            logger.error(f"Error loading tokens: {e}")
    
    def save_tokens(self):
        """Save tokens to file"""
        try:
            data = {user_id: tokens.to_dict() for user_id, tokens in self.tokens.items()}
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.debug("Tokens saved to storage")
        except Exception as e:
            logger.error(f"Error saving tokens: {e}")
    
    def store_tokens(self, user_id: str, tokens: SchwabTokens):
        """Store tokens for user"""
        self.tokens[user_id] = tokens
        self.save_tokens()
        logger.info(f"Stored tokens for user: {user_id}")
    
    def get_tokens(self, user_id: str) -> Optional[SchwabTokens]:
        """Get tokens for user"""
        return self.tokens.get(user_id)
    
    def remove_tokens(self, user_id: str):
        """Remove tokens for user"""
        if user_id in self.tokens:
            del self.tokens[user_id]
            self.save_tokens()
            logger.info(f"Removed tokens for user: {user_id}")

# =============================================================================
# SCHWAB API CLIENT
# =============================================================================

class SchwabAPIClient:
    """Production-ready Schwab API client with OAuth2 and error handling"""
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, token_storage: TokenStorage):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_storage = token_storage
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Arbion-Trading-Platform/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded'
        })
    
    def generate_state(self) -> str:
        """Generate cryptographically secure state parameter"""
        return secrets.token_urlsafe(32)
    
    def get_authorization_url(self, state: str) -> str:
        """Generate OAuth2 authorization URL"""
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': 'api',
            'state': state
        }
        
        url = f"{SCHWAB_AUTH_URL}?{urllib.parse.urlencode(params)}"
        logger.info(f"Generated authorization URL with state: {state[:8]}...")
        return url
    
    def exchange_code_for_tokens(self, authorization_code: str) -> Optional[SchwabTokens]:
        """Exchange authorization code for access and refresh tokens"""
        try:
            data = {
                'grant_type': 'authorization_code',
                'code': authorization_code,
                'redirect_uri': self.redirect_uri,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            logger.info("Exchanging authorization code for tokens")
            response = self.session.post(SCHWAB_TOKEN_URL, data=data, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                tokens = SchwabTokens(
                    access_token=token_data['access_token'],
                    refresh_token=token_data['refresh_token'],
                    token_type=token_data.get('token_type', 'Bearer'),
                    expires_in=token_data.get('expires_in', 1800),
                    scope=token_data.get('scope', 'api')
                )
                logger.info("Successfully obtained tokens")
                return tokens
            else:
                logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {e}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[SchwabTokens]:
        """Refresh access token using refresh token"""
        try:
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }
            
            logger.info("Refreshing access token")
            response = self.session.post(SCHWAB_TOKEN_URL, data=data, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                tokens = SchwabTokens(
                    access_token=token_data['access_token'],
                    refresh_token=token_data.get('refresh_token', refresh_token),  # May not be renewed
                    token_type=token_data.get('token_type', 'Bearer'),
                    expires_in=token_data.get('expires_in', 1800),
                    scope=token_data.get('scope', 'api')
                )
                logger.info("Successfully refreshed tokens")
                return tokens
            else:
                logger.error(f"Token refresh failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return None
    
    def get_valid_token(self, user_id: str) -> Optional[str]:
        """Get valid access token, refreshing if necessary"""
        tokens = self.token_storage.get_tokens(user_id)
        
        if not tokens:
            logger.warning(f"No tokens found for user: {user_id}")
            return None
        
        if not tokens.is_expired():
            return tokens.access_token
        
        # Token is expired, try to refresh
        logger.info(f"Token expired for user {user_id}, attempting refresh")
        new_tokens = self.refresh_access_token(tokens.refresh_token)
        
        if new_tokens:
            self.token_storage.store_tokens(user_id, new_tokens)
            return new_tokens.access_token
        else:
            logger.error(f"Failed to refresh token for user: {user_id}")
            self.token_storage.remove_tokens(user_id)
            return None
    
    def make_authenticated_request(self, user_id: str, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        """Make authenticated API request with automatic token refresh"""
        access_token = self.get_valid_token(user_id)
        
        if not access_token:
            logger.error(f"No valid access token for user: {user_id}")
            return None
        
        headers = kwargs.get('headers', {})
        headers.update({
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        })
        kwargs['headers'] = headers
        
        url = f"{SCHWAB_BASE_URL}{endpoint}"
        
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            
            # Handle 401 Unauthorized - token might be invalid
            if response.status_code == 401:
                logger.warning(f"Received 401 for user {user_id}, attempting token refresh")
                
                # Try to refresh token and retry request
                tokens = self.token_storage.get_tokens(user_id)
                if tokens:
                    new_tokens = self.refresh_access_token(tokens.refresh_token)
                    if new_tokens:
                        self.token_storage.store_tokens(user_id, new_tokens)
                        headers['Authorization'] = f'Bearer {new_tokens.access_token}'
                        response = self.session.request(method, url, timeout=30, **kwargs)
            
            return response
            
        except Exception as e:
            logger.error(f"Error making authenticated request: {e}")
            return None
    
    def get_accounts(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch user accounts from Schwab API"""
        response = self.make_authenticated_request(user_id, 'GET', '/trader/v1/accounts')
        
        if response and response.status_code == 200:
            return response.json()
        elif response:
            logger.error(f"Failed to fetch accounts: {response.status_code} - {response.text}")
            return None
        else:
            return None
    
    def get_account_balances(self, user_id: str, account_hash: str = None) -> Optional[Dict[str, Any]]:
        """Fetch account balances from Schwab API"""
        if account_hash:
            endpoint = f'/trader/v1/accounts/{account_hash}/positions'
        else:
            endpoint = '/trader/v1/accounts'
            
        response = self.make_authenticated_request(user_id, 'GET', endpoint)
        
        if response and response.status_code == 200:
            return response.json()
        elif response:
            logger.error(f"Failed to fetch balances: {response.status_code} - {response.text}")
            return None
        else:
            return None

# =============================================================================
# FLASK APPLICATION
# =============================================================================

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Initialize components
token_storage = TokenStorage()
schwab_client = SchwabAPIClient(SCHWAB_CLIENT_ID, SCHWAB_CLIENT_SECRET, SCHWAB_REDIRECT_URI, token_storage)

# =============================================================================
# FLASK ROUTES
# =============================================================================

@app.route('/')
def index():
    """Main page with Schwab API integration status"""
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Schwab Trader API Integration</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .header { text-align: center; margin-bottom: 30px; }
            .btn { display: inline-block; padding: 12px 24px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 10px; }
            .btn:hover { background: #0056b3; }
            .status { padding: 15px; margin: 10px 0; border-radius: 5px; }
            .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
            .warning { background: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }
            .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
            .code { background: #f8f9fa; padding: 10px; border-radius: 5px; font-family: monospace; margin: 10px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏦 Schwab Trader API Integration</h1>
                <p>Production-ready OAuth2 authentication and account access</p>
            </div>
            
            <div class="status warning">
                <strong>Configuration Status:</strong><br>
                Client ID: {{ 'Configured' if client_id_set else 'Not Set' }}<br>
                Client Secret: {{ 'Configured' if client_secret_set else 'Not Set' }}<br>
                Redirect URI: {{ redirect_uri }}
            </div>
            
            {% if not client_id_set or not client_secret_set %}
            <div class="status error">
                <strong>Setup Required:</strong> Please set your Schwab API credentials in environment variables:
                <div class="code">
                    SCHWAB_CLIENT_ID=your_client_id<br>
                    SCHWAB_CLIENT_SECRET=your_client_secret
                </div>
            </div>
            {% endif %}
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="/auth/schwab" class="btn">🔐 Connect Schwab Account</a>
                <a href="/accounts" class="btn">📊 View Accounts</a>
                <a href="/balances" class="btn">💰 Check Balances</a>
            </div>
            
            <div class="status success">
                <strong>Available Endpoints:</strong><br>
                • GET /auth/schwab - Start OAuth2 flow<br>
                • GET /oauth_callback/broker - OAuth2 callback handler<br>
                • GET /accounts - Fetch account information<br>
                • GET /balances - Fetch account balances<br>
                • GET /api/accounts - JSON API for accounts<br>
                • GET /api/balances - JSON API for balances
            </div>
        </div>
    </body>
    </html>
    """
    
    return render_template_string(template,
        client_id_set=bool(SCHWAB_CLIENT_ID and SCHWAB_CLIENT_ID != 'YOUR_CLIENT_ID_HERE'),
        client_secret_set=bool(SCHWAB_CLIENT_SECRET and SCHWAB_CLIENT_SECRET != 'YOUR_CLIENT_SECRET_HERE'),
        redirect_uri=SCHWAB_REDIRECT_URI
    )

@app.route('/auth/schwab')
def initiate_schwab_auth():
    """Initiate Schwab OAuth2 authentication flow"""
    if not SCHWAB_CLIENT_ID or SCHWAB_CLIENT_ID == 'YOUR_CLIENT_ID_HERE':
        return jsonify({'error': 'Schwab client credentials not configured'}), 400
    
    # Generate secure state parameter
    state = schwab_client.generate_state()
    session['oauth_state'] = state
    session['user_id'] = session.get('user_id', 'default_user')  # Simple user identification
    
    # Generate authorization URL
    auth_url = schwab_client.get_authorization_url(state)
    
    logger.info(f"Redirecting to Schwab authorization: {auth_url}")
    return redirect(auth_url)

@app.route('/oauth_callback/broker')
def schwab_oauth_callback():
    """Handle Schwab OAuth2 callback"""
    try:
        # Validate state parameter
        received_state = request.args.get('state')
        stored_state = session.get('oauth_state')
        
        if not received_state or received_state != stored_state:
            logger.error("Invalid state parameter in OAuth callback")
            return jsonify({'error': 'Invalid state parameter'}), 400
        
        # Get authorization code
        authorization_code = request.args.get('code')
        error = request.args.get('error')
        
        if error:
            logger.error(f"OAuth error: {error}")
            return jsonify({'error': f'OAuth error: {error}'}), 400
        
        if not authorization_code:
            logger.error("No authorization code received")
            return jsonify({'error': 'No authorization code received'}), 400
        
        # Exchange code for tokens
        tokens = schwab_client.exchange_code_for_tokens(authorization_code)
        
        if not tokens:
            return jsonify({'error': 'Failed to exchange code for tokens'}), 500
        
        # Store tokens
        user_id = session.get('user_id', 'default_user')
        schwab_client.token_storage.store_tokens(user_id, tokens)
        
        # Clean up session
        session.pop('oauth_state', None)
        
        logger.info(f"Successfully authenticated user: {user_id}")
        return jsonify({
            'success': True,
            'message': 'Successfully authenticated with Schwab',
            'expires_at': tokens.expires_at.isoformat(),
            'redirect': '/accounts'
        })
        
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        return jsonify({'error': 'Internal server error during authentication'}), 500

@app.route('/accounts')
def view_accounts():
    """Display account information"""
    user_id = session.get('user_id', 'default_user')
    accounts_data = schwab_client.get_accounts(user_id)
    
    if not accounts_data:
        return jsonify({'error': 'Failed to fetch accounts. Please re-authenticate.'}), 401
    
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Schwab Accounts</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .account { border: 1px solid #ddd; margin: 15px 0; padding: 20px; border-radius: 8px; background: #f9f9f9; }
            .account-header { font-size: 18px; font-weight: bold; color: #333; margin-bottom: 10px; }
            .account-details { font-size: 14px; color: #666; }
            .btn { display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 10px 5px; }
            pre { background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 Schwab Accounts</h1>
            <div style="margin-bottom: 20px;">
                <a href="/" class="btn">← Back to Home</a>
                <a href="/balances" class="btn">💰 View Balances</a>
            </div>
            
            {% if accounts %}
                {% for account in accounts %}
                <div class="account">
                    <div class="account-header">
                        Account: {{ account.get('accountNumber', 'N/A') }}
                    </div>
                    <div class="account-details">
                        Type: {{ account.get('type', 'N/A') }}<br>
                        Status: {{ account.get('roundTrips', 'N/A') }}<br>
                        Hash ID: {{ account.get('hashValue', 'N/A') }}
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <p>No accounts found or unable to fetch account data.</p>
            {% endif %}
            
            <details>
                <summary>Raw API Response</summary>
                <pre>{{ raw_data }}</pre>
            </details>
        </div>
    </body>
    </html>
    """
    
    accounts = accounts_data if isinstance(accounts_data, list) else accounts_data.get('accounts', [])
    
    return render_template_string(template,
        accounts=accounts,
        raw_data=json.dumps(accounts_data, indent=2)
    )

@app.route('/balances')
def view_balances():
    """Display account balances"""
    user_id = session.get('user_id', 'default_user')
    balances_data = schwab_client.get_account_balances(user_id)
    
    if not balances_data:
        return jsonify({'error': 'Failed to fetch balances. Please re-authenticate.'}), 401
    
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Account Balances</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
            .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .balance-card { border: 1px solid #ddd; margin: 15px 0; padding: 20px; border-radius: 8px; background: #f9f9f9; }
            .balance-header { font-size: 18px; font-weight: bold; color: #333; margin-bottom: 10px; }
            .balance-amount { font-size: 24px; color: #28a745; font-weight: bold; }
            .btn { display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; margin: 10px 5px; }
            pre { background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>💰 Account Balances</h1>
            <div style="margin-bottom: 20px;">
                <a href="/" class="btn">← Back to Home</a>
                <a href="/accounts" class="btn">📊 View Accounts</a>
            </div>
            
            <div class="balance-card">
                <div class="balance-header">Portfolio Summary</div>
                <p>Balance data retrieved successfully from Schwab API</p>
            </div>
            
            <details>
                <summary>Raw Balance Data</summary>
                <pre>{{ raw_data }}</pre>
            </details>
        </div>
    </body>
    </html>
    """
    
    return render_template_string(template,
        raw_data=json.dumps(balances_data, indent=2)
    )

# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.route('/api/accounts')
def api_get_accounts():
    """JSON API endpoint for accounts"""
    user_id = request.args.get('user_id', 'default_user')
    accounts_data = schwab_client.get_accounts(user_id)
    
    if accounts_data:
        return jsonify({
            'success': True,
            'data': accounts_data,
            'timestamp': datetime.utcnow().isoformat()
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to fetch accounts. Authentication may be required.',
            'timestamp': datetime.utcnow().isoformat()
        }), 401

@app.route('/api/balances')
def api_get_balances():
    """JSON API endpoint for balances"""
    user_id = request.args.get('user_id', 'default_user')
    account_hash = request.args.get('account_hash')
    
    balances_data = schwab_client.get_account_balances(user_id, account_hash)
    
    if balances_data:
        return jsonify({
            'success': True,
            'data': balances_data,
            'timestamp': datetime.utcnow().isoformat()
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to fetch balances. Authentication may be required.',
            'timestamp': datetime.utcnow().isoformat()
        }), 401

@app.route('/api/auth/status')
def api_auth_status():
    """Check authentication status"""
    user_id = request.args.get('user_id', 'default_user')
    tokens = token_storage.get_tokens(user_id)
    
    if tokens:
        return jsonify({
            'authenticated': True,
            'expires_at': tokens.expires_at.isoformat() if tokens.expires_at else None,
            'is_expired': tokens.is_expired(),
            'user_id': user_id
        })
    else:
        return jsonify({
            'authenticated': False,
            'user_id': user_id
        })

# =============================================================================
# ERROR HANDLERS
# =============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# =============================================================================
# MAIN APPLICATION ENTRY POINT
# =============================================================================

if __name__ == '__main__':
    logger.info("Starting Schwab Trader API Integration Server")
    logger.info(f"Client ID configured: {bool(SCHWAB_CLIENT_ID and SCHWAB_CLIENT_ID != 'YOUR_CLIENT_ID_HERE')}")
    logger.info(f"Redirect URI: {SCHWAB_REDIRECT_URI}")
    logger.info(f"Debug mode: {DEBUG_MODE}")
    
    # For Heroku deployment
    app.run(host='0.0.0.0', port=PORT, debug=DEBUG_MODE)