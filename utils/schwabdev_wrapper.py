"""
Schwabdev Wrapper for Arbion Platform
Integrates schwabdev library v3.0.0 with Arbion's existing OAuth token storage
"""

import os
import json
import logging
import tempfile
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class SchwabdevWrapper:
    """
    Wrapper for schwabdev.Client that integrates with Arbion's database token storage
    """

    def __init__(self, user_id: int = None):
        """Initialize wrapper with user ID"""
        self.user_id = user_id
        self.client = None
        self.app_key = None
        self.app_secret = None
        self.temp_tokens_file = None

        # Load credentials from environment or database
        self._load_credentials()

        # Initialize schwabdev client if credentials are available
        if self.app_key and self.app_secret:
            self._initialize_client()

    def _load_credentials(self):
        """Load Schwab app credentials from environment or database"""
        try:
            # Try environment variables first
            self.app_key = os.environ.get('SCHWAB_APP_KEY') or os.environ.get('SCHWAB_CLIENT_ID')
            self.app_secret = os.environ.get('SCHWAB_APP_SECRET') or os.environ.get('SCHWAB_CLIENT_SECRET')

            # If not in environment, try user-specific credentials from database
            if (not self.app_key or not self.app_secret) and self.user_id:
                from models import OAuthClientCredential
                client_cred = OAuthClientCredential.query.filter_by(
                    user_id=self.user_id,
                    provider='schwab',
                    is_active=True
                ).first()

                if client_cred:
                    self.app_key = client_cred.client_id
                    self.app_secret = client_cred.client_secret
                    logger.info(f"Loaded Schwab credentials from database for user {self.user_id}")

            if self.app_key and self.app_secret:
                logger.info("Schwab app credentials loaded successfully")
            else:
                logger.warning("Schwab app credentials not found")

        except Exception as e:
            logger.error(f"Error loading Schwab credentials: {e}")
            self.app_key = None
            self.app_secret = None

    def _load_tokens_from_database(self) -> Optional[Dict]:
        """Load OAuth tokens from Arbion database"""
        if not self.user_id:
            return None

        try:
            from models import APICredential
            from utils.encryption import decrypt_credentials

            cred = APICredential.query.filter_by(
                user_id=self.user_id,
                provider='schwab',
                is_active=True
            ).first()

            if not cred or not cred.encrypted_credentials:
                logger.info("No Schwab tokens found in database")
                return None

            # Decrypt credentials
            token_data = decrypt_credentials(cred.encrypted_credentials)

            if isinstance(token_data, str):
                token_data = json.loads(token_data)

            logger.info("Loaded Schwab tokens from database")
            return token_data

        except Exception as e:
            logger.error(f"Error loading tokens from database: {e}")
            return None

    def _create_temp_tokens_file(self, token_data: Dict) -> str:
        """Create a temporary tokens database file for schwabdev"""
        try:
            import sqlite3

            # Create temp file
            temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
            temp_file.close()

            # Create tokens database
            conn = sqlite3.connect(temp_file.name)
            cursor = conn.cursor()

            # Create tokens table (schwabdev schema)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tokens (
                    access_token TEXT,
                    refresh_token TEXT,
                    id_token TEXT,
                    token_type TEXT,
                    expires_in INTEGER,
                    scope TEXT,
                    refresh_token_expires_in INTEGER,
                    last_updated_at INTEGER
                )
            ''')

            # Insert tokens
            cursor.execute('''
                INSERT INTO tokens (
                    access_token, refresh_token, id_token, token_type,
                    expires_in, scope, refresh_token_expires_in, last_updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                token_data.get('access_token', ''),
                token_data.get('refresh_token', ''),
                token_data.get('id_token', ''),
                token_data.get('token_type', 'Bearer'),
                token_data.get('expires_in', 1800),
                token_data.get('scope', ''),
                token_data.get('refresh_token_expires_in', 604800),
                int(datetime.utcnow().timestamp())
            ))

            conn.commit()
            conn.close()

            logger.info(f"Created temporary tokens file: {temp_file.name}")
            return temp_file.name

        except Exception as e:
            logger.error(f"Error creating temp tokens file: {e}")
            return None

    def _initialize_client(self):
        """Initialize schwabdev client with tokens from database"""
        try:
            import schwabdev

            if not self.app_key or not self.app_secret:
                raise ValueError("App key and secret required")

            # Load tokens from database
            token_data = self._load_tokens_from_database()

            # Create temporary tokens file if tokens exist
            if token_data:
                self.temp_tokens_file = self._create_temp_tokens_file(token_data)
            else:
                # No tokens yet - create empty temp file
                temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db')
                self.temp_tokens_file = temp_file.name
                temp_file.close()

            # Initialize schwabdev client
            self.client = schwabdev.Client(
                app_key=self.app_key,
                app_secret=self.app_secret,
                callback_url=os.environ.get('SCHWAB_REDIRECT_URI', 'https://www.arbion.ai/oauth_callback/broker'),
                tokens_db=self.temp_tokens_file,
                timeout=30
            )

            logger.info("Schwabdev client initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing schwabdev client: {e}")
            self.client = None

    def _sync_tokens_to_database(self):
        """Sync tokens from schwabdev back to Arbion database"""
        if not self.user_id or not self.temp_tokens_file:
            return

        try:
            import sqlite3
            from models import APICredential, db
            from utils.encryption import encrypt_credentials

            # Read tokens from temp file
            conn = sqlite3.connect(self.temp_tokens_file)
            cursor = conn.cursor()
            cursor.execute('SELECT access_token, refresh_token, id_token, token_type, expires_in FROM tokens')
            row = cursor.fetchone()
            conn.close()

            if not row:
                return

            token_data = {
                'access_token': row[0],
                'refresh_token': row[1],
                'id_token': row[2],
                'token_type': row[3],
                'expires_in': row[4]
            }

            # Update database
            cred = APICredential.query.filter_by(
                user_id=self.user_id,
                provider='schwab'
            ).first()

            if cred:
                cred.encrypted_credentials = encrypt_credentials(token_data)
                cred.updated_at = datetime.utcnow()
                cred.is_active = True
                db.session.commit()
                logger.info("Synced tokens back to database")

        except Exception as e:
            logger.error(f"Error syncing tokens to database: {e}")

    def get_linked_accounts(self) -> Dict[str, Any]:
        """Get all linked Schwab accounts"""
        try:
            if not self.client:
                return {'success': False, 'error': 'Client not initialized'}

            # Update tokens if needed
            self.client.update_tokens()

            response = self.client.linked_accounts()

            # Sync tokens back to database
            self._sync_tokens_to_database()

            if response.ok:
                return {
                    'success': True,
                    'accounts': response.json()
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}',
                    'response': response.text
                }

        except Exception as e:
            logger.error(f"Error getting linked accounts: {e}")
            return {'success': False, 'error': str(e)}

    def get_account_details(self, account_hash: str, fields: str = None) -> Dict[str, Any]:
        """Get account details including positions and balances"""
        try:
            if not self.client:
                return {'success': False, 'error': 'Client not initialized'}

            # Update tokens if needed
            self.client.update_tokens()

            response = self.client.account_details(accountHash=account_hash, fields=fields)

            # Sync tokens back to database
            self._sync_tokens_to_database()

            if response.ok:
                return {
                    'success': True,
                    'account': response.json()
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}',
                    'response': response.text
                }

        except Exception as e:
            logger.error(f"Error getting account details: {e}")
            return {'success': False, 'error': str(e)}

    def get_quotes(self, symbols: list) -> Dict[str, Any]:
        """Get real-time quotes for symbols"""
        try:
            if not self.client:
                return {'success': False, 'error': 'Client not initialized'}

            # Update tokens if needed
            self.client.update_tokens()

            response = self.client.quotes(symbols=symbols)

            # Sync tokens back to database
            self._sync_tokens_to_database()

            if response.ok:
                return {
                    'success': True,
                    'quotes': response.json()
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}',
                    'response': response.text
                }

        except Exception as e:
            logger.error(f"Error getting quotes: {e}")
            return {'success': False, 'error': str(e)}

    def place_order(self, account_hash: str, order: dict) -> Dict[str, Any]:
        """Place a trading order"""
        try:
            if not self.client:
                return {'success': False, 'error': 'Client not initialized'}

            # Update tokens if needed
            self.client.update_tokens()

            response = self.client.place_order(accountHash=account_hash, order=order)

            # Sync tokens back to database
            self._sync_tokens_to_database()

            if response.ok:
                return {
                    'success': True,
                    'order_response': response.headers.get('Location', 'Order placed successfully')
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}',
                    'response': response.text
                }

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {'success': False, 'error': str(e)}

    def get_account_orders(self, account_hash: str, from_time: str = None, to_time: str = None) -> Dict[str, Any]:
        """Get account orders"""
        try:
            if not self.client:
                return {'success': False, 'error': 'Client not initialized'}

            # Update tokens if needed
            self.client.update_tokens()

            response = self.client.account_orders(accountHash=account_hash)

            # Sync tokens back to database
            self._sync_tokens_to_database()

            if response.ok:
                return {
                    'success': True,
                    'orders': response.json()
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}',
                    'response': response.text
                }

        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return {'success': False, 'error': str(e)}

    def __del__(self):
        """Cleanup temporary files"""
        try:
            if self.temp_tokens_file and os.path.exists(self.temp_tokens_file):
                os.unlink(self.temp_tokens_file)
        except:
            pass
