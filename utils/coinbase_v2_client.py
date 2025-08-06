"""
Coinbase Wallet API v2 Enhanced Client
Integrates comprehensive v2 features including Smart Accounts, Gas Sponsorship, 
Transaction Batching, Multi-Network Support, and advanced trading capabilities.
"""

import os
import json
import requests
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from utils.encryption import encrypt_credentials, decrypt_credentials

logger = logging.getLogger(__name__)

class CoinbaseV2Client:
    """Enhanced Coinbase Wallet API v2 Client with comprehensive feature support"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.api_base_url = 'https://api.cdp.coinbase.com/platform/v1'
        self.wallet_api_url = 'https://api.cdp.coinbase.com/wallet/v2'
        self.api_key_id = None
        self.api_key_secret = None
        self.wallet_secret = None
        self.access_token = None
        
        # Load credentials from database
        self._load_credentials()
    
    def _load_credentials(self):
        """Load API credentials from database"""
        try:
            from models import APICredential
            
            # Load CDP API credentials
            api_cred = APICredential.query.filter_by(
                user_id=self.user_id,
                provider='coinbase_v2',
                is_active=True
            ).first()
            
            if api_cred:
                decrypted = decrypt_credentials(api_cred.encrypted_credentials)
                self.api_key_id = decrypted.get('api_key_id')
                self.api_key_secret = decrypted.get('api_key_secret')
                self.wallet_secret = decrypted.get('wallet_secret')
                self.access_token = decrypted.get('access_token')
                logger.info(f"Loaded Coinbase v2 credentials for user {self.user_id}")
            else:
                logger.warning(f"No Coinbase v2 credentials found for user {self.user_id}")
                
        except Exception as e:
            logger.error(f"Error loading Coinbase v2 credentials: {e}")
    
    def save_credentials(self, api_key_id: str, api_key_secret: str, wallet_secret: str, access_token: str = None):
        """Save API credentials to database"""
        try:
            from models import APICredential
            from app import db
            
            credentials = {
                'api_key_id': api_key_id,
                'api_key_secret': api_key_secret,
                'wallet_secret': wallet_secret,
                'access_token': access_token
            }
            
            encrypted_creds = encrypt_credentials(credentials)
            
            # Check if credentials exist
            existing_cred = APICredential.query.filter_by(
                user_id=self.user_id,
                provider='coinbase_v2'
            ).first()
            
            if existing_cred:
                existing_cred.encrypted_credentials = encrypted_creds
                existing_cred.is_active = True
                existing_cred.updated_at = datetime.utcnow()
            else:
                new_cred = APICredential(
                    user_id=self.user_id,
                    provider='coinbase_v2',
                    encrypted_credentials=encrypted_creds,
                    is_active=True
                )
                db.session.add(new_cred)
            
            db.session.commit()
            
            # Update instance variables
            self.api_key_id = api_key_id
            self.api_key_secret = api_key_secret
            self.wallet_secret = wallet_secret
            self.access_token = access_token
            
            logger.info(f"Saved Coinbase v2 credentials for user {self.user_id}")
            
        except Exception as e:
            logger.error(f"Error saving Coinbase v2 credentials: {e}")
            raise
    
    def _make_authenticated_request(self, method: str, endpoint: str, data: Dict = None, use_wallet_api: bool = False) -> Dict:
        """Make authenticated request to Coinbase v2 API"""
        base_url = self.wallet_api_url if use_wallet_api else self.api_base_url
        url = f"{base_url}{endpoint}"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}' if self.access_token else f'Bearer {self.api_key_secret}',
            'Content-Type': 'application/json',
            'User-Agent': 'Arbion-Trading-Platform/2.0',
            'X-CDP-API-KEY': self.api_key_id
        }
        
        if self.wallet_secret:
            headers['X-CDP-WALLET-SECRET'] = self.wallet_secret
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Coinbase v2 API request failed: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            raise
    
    # ACCOUNT MANAGEMENT
    def create_evm_account(self, network: str = "base-sepolia") -> Dict:
        """Create a new EVM account (Externally Owned Account)"""
        try:
            data = {
                "network": network
            }
            
            result = self._make_authenticated_request('POST', '/accounts/evm', data, use_wallet_api=True)
            logger.info(f"Created EVM account: {result.get('address', 'Unknown')}")
            return result
            
        except Exception as e:
            logger.error(f"Error creating EVM account: {e}")
            raise
    
    def create_smart_account(self, owner_address: str, network: str = "base-sepolia") -> Dict:
        """Create a Smart Account with advanced features (EIP-4337)"""
        try:
            data = {
                "owner": owner_address,
                "network": network
            }
            
            result = self._make_authenticated_request('POST', '/accounts/smart', data, use_wallet_api=True)
            logger.info(f"Created Smart Account: {result.get('address', 'Unknown')}")
            return result
            
        except Exception as e:
            logger.error(f"Error creating Smart Account: {e}")
            raise
    
    def create_solana_account(self) -> Dict:
        """Create a new Solana account"""
        try:
            result = self._make_authenticated_request('POST', '/accounts/solana', use_wallet_api=True)
            logger.info(f"Created Solana account: {result.get('address', 'Unknown')}")
            return result
            
        except Exception as e:
            logger.error(f"Error creating Solana account: {e}")
            raise
    
    def list_accounts(self) -> List[Dict]:
        """List all accounts across EVM and Solana networks"""
        try:
            result = self._make_authenticated_request('GET', '/accounts', use_wallet_api=True)
            accounts = result.get('accounts', [])
            logger.info(f"Retrieved {len(accounts)} accounts")
            return accounts
            
        except Exception as e:
            logger.error(f"Error listing accounts: {e}")
            raise
    
    def get_account_balance(self, address: str, network: str = "base-sepolia") -> Dict:
        """Get account balance for specific address and network"""
        try:
            endpoint = f'/accounts/{address}/balance?network={network}'
            result = self._make_authenticated_request('GET', endpoint, use_wallet_api=True)
            logger.info(f"Retrieved balance for {address}: {result.get('balance', 'Unknown')}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            raise
    
    # TRANSACTION CAPABILITIES
    def send_transaction(self, from_address: str, to_address: str, value: str, network: str = "base-sepolia", data: str = "0x") -> Dict:
        """Send a standard EVM transaction"""
        try:
            transaction_data = {
                "from": from_address,
                "to": to_address,
                "value": value,
                "data": data,
                "network": network
            }
            
            result = self._make_authenticated_request('POST', '/transactions', transaction_data, use_wallet_api=True)
            logger.info(f"Sent transaction: {result.get('hash', 'Unknown')}")
            return result
            
        except Exception as e:
            logger.error(f"Error sending transaction: {e}")
            raise
    
    def send_user_operation(self, smart_account_address: str, calls: List[Dict], network: str = "base-sepolia", paymaster_url: str = None) -> Dict:
        """Send a user operation (batch transaction) via Smart Account"""
        try:
            operation_data = {
                "smart_account": smart_account_address,
                "network": network,
                "calls": calls
            }
            
            if paymaster_url:
                operation_data["paymaster_url"] = paymaster_url
            
            result = self._make_authenticated_request('POST', '/user-operations', operation_data, use_wallet_api=True)
            logger.info(f"Sent user operation: {result.get('user_op_hash', 'Unknown')}")
            return result
            
        except Exception as e:
            logger.error(f"Error sending user operation: {e}")
            raise
    
    def batch_transactions(self, smart_account_address: str, transactions: List[Dict], network: str = "base-sepolia") -> Dict:
        """Batch multiple transactions in a single user operation"""
        try:
            calls = []
            for tx in transactions:
                calls.append({
                    "to": tx["to"],
                    "value": tx.get("value", "0"),
                    "data": tx.get("data", "0x")
                })
            
            return self.send_user_operation(smart_account_address, calls, network)
            
        except Exception as e:
            logger.error(f"Error batching transactions: {e}")
            raise
    
    def wait_for_transaction(self, transaction_hash: str, network: str = "base-sepolia", timeout: int = 300) -> Dict:
        """Wait for transaction confirmation"""
        try:
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                endpoint = f'/transactions/{transaction_hash}?network={network}'
                result = self._make_authenticated_request('GET', endpoint, use_wallet_api=True)
                
                status = result.get('status')
                if status in ['complete', 'failed']:
                    logger.info(f"Transaction {transaction_hash} completed with status: {status}")
                    return result
                
                time.sleep(5)  # Poll every 5 seconds
            
            raise TimeoutError(f"Transaction {transaction_hash} did not complete within {timeout} seconds")
            
        except Exception as e:
            logger.error(f"Error waiting for transaction: {e}")
            raise
    
    # SWAPS AND TRADING
    def get_swap_quote(self, from_asset: str, to_asset: str, amount: str, network: str = "base-sepolia") -> Dict:
        """Get a quote for token swap"""
        try:
            params = {
                'from_asset': from_asset,
                'to_asset': to_asset,
                'amount': amount,
                'network': network
            }
            
            result = self._make_authenticated_request('GET', f'/swaps/quote?{requests.compat.urlencode(params)}', use_wallet_api=True)
            logger.info(f"Retrieved swap quote: {from_asset} -> {to_asset}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting swap quote: {e}")
            raise
    
    def execute_swap(self, from_address: str, quote_id: str, network: str = "base-sepolia") -> Dict:
        """Execute a token swap using a quote"""
        try:
            swap_data = {
                "from_address": from_address,
                "quote_id": quote_id,
                "network": network
            }
            
            result = self._make_authenticated_request('POST', '/swaps/execute', swap_data, use_wallet_api=True)
            logger.info(f"Executed swap: {result.get('transaction_hash', 'Unknown')}")
            return result
            
        except Exception as e:
            logger.error(f"Error executing swap: {e}")
            raise
    
    # GAS SPONSORSHIP
    def sponsor_transaction(self, smart_account_address: str, calls: List[Dict], network: str = "base-sepolia") -> Dict:
        """Sponsor gas fees for a user operation (Base Sepolia is free)"""
        try:
            # On Base Sepolia, gas is sponsored by default
            # For mainnet, you would specify a paymaster URL
            paymaster_url = None
            if network == "base-mainnet":
                # Would need to configure paymaster for mainnet
                paymaster_url = "https://paymaster.base.org"  # Example
            
            return self.send_user_operation(smart_account_address, calls, network, paymaster_url)
            
        except Exception as e:
            logger.error(f"Error sponsoring transaction: {e}")
            raise
    
    # FAUCET (TESTNET ONLY)
    def request_faucet(self, address: str, network: str = "base-sepolia", asset: str = "eth") -> Dict:
        """Request testnet tokens from faucet"""
        try:
            faucet_data = {
                "address": address,
                "network": network,
                "asset": asset
            }
            
            result = self._make_authenticated_request('POST', '/faucets', faucet_data, use_wallet_api=True)
            logger.info(f"Requested faucet for {address} on {network}")
            return result
            
        except Exception as e:
            logger.error(f"Error requesting faucet: {e}")
            raise
    
    # MESSAGE SIGNING
    def sign_message(self, address: str, message: str, network: str = "base-sepolia") -> Dict:
        """Sign a message with an account"""
        try:
            sign_data = {
                "address": address,
                "message": message,
                "network": network
            }
            
            result = self._make_authenticated_request('POST', '/sign-message', sign_data, use_wallet_api=True)
            logger.info(f"Signed message with {address}")
            return result
            
        except Exception as e:
            logger.error(f"Error signing message: {e}")
            raise
    
    # ADVANCED FEATURES
    def get_supported_networks(self) -> List[str]:
        """Get list of supported networks"""
        try:
            result = self._make_authenticated_request('GET', '/networks', use_wallet_api=True)
            networks = result.get('networks', [])
            logger.info(f"Retrieved {len(networks)} supported networks")
            return networks
            
        except Exception as e:
            logger.error(f"Error getting supported networks: {e}")
            raise
    
    def get_network_fees(self, network: str = "base-sepolia") -> Dict:
        """Get current network fees"""
        try:
            endpoint = f'/networks/{network}/fees'
            result = self._make_authenticated_request('GET', endpoint, use_wallet_api=True)
            logger.info(f"Retrieved network fees for {network}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting network fees: {e}")
            raise
    
    def estimate_gas(self, from_address: str, to_address: str, value: str, data: str = "0x", network: str = "base-sepolia") -> Dict:
        """Estimate gas for a transaction"""
        try:
            estimate_data = {
                "from": from_address,
                "to": to_address,
                "value": value,
                "data": data,
                "network": network
            }
            
            result = self._make_authenticated_request('POST', '/estimate-gas', estimate_data, use_wallet_api=True)
            logger.info(f"Estimated gas: {result.get('gas_estimate', 'Unknown')}")
            return result
            
        except Exception as e:
            logger.error(f"Error estimating gas: {e}")
            raise
    
    # WALLET SECRET ROTATION
    def rotate_wallet_secret(self, new_wallet_secret: str) -> Dict:
        """Rotate wallet secret for enhanced security"""
        try:
            rotation_data = {
                "new_wallet_secret": new_wallet_secret
            }
            
            result = self._make_authenticated_request('POST', '/wallet-secret/rotate', rotation_data, use_wallet_api=True)
            
            # Update stored credentials
            if result.get('success'):
                self.wallet_secret = new_wallet_secret
                self.save_credentials(self.api_key_id, self.api_key_secret, new_wallet_secret, self.access_token)
            
            logger.info("Wallet secret rotated successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error rotating wallet secret: {e}")
            raise
    
    # TESTING AND DIAGNOSTICS
    def test_connection(self) -> Dict:
        """Test API connection and credentials"""
        try:
            result = self.list_accounts()
            return {
                'success': True,
                'message': 'Connection successful',
                'account_count': len(result)
            }
            
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_api_status(self) -> Dict:
        """Get API status and health"""
        try:
            result = self._make_authenticated_request('GET', '/health', use_wallet_api=True)
            logger.info("Retrieved API status")
            return result
            
        except Exception as e:
            logger.error(f"Error getting API status: {e}")
            raise