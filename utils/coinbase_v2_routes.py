"""
Enhanced Coinbase Wallet API v2 Routes
Comprehensive Flask routes integrating all v2 features including Smart Accounts,
Gas Sponsorship, Transaction Batching, Multi-Network Support, and Trading.
"""

from flask import Blueprint, request, jsonify, session
from flask_login import login_required, current_user
import logging
from utils.coinbase_v2_client import CoinbaseV2Client

logger = logging.getLogger(__name__)

# Create blueprint for v2 routes
coinbase_v2_bp = Blueprint('coinbase_v2', __name__)

@coinbase_v2_bp.route('/api/coinbase-v2/test-connection', methods=['GET'])
@login_required
def test_v2_connection():
    """Test Coinbase v2 API connection"""
    try:
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.test_connection()
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error testing Coinbase v2 connection: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@coinbase_v2_bp.route('/api/coinbase-v2/save-credentials', methods=['POST'])
@login_required
def save_v2_credentials():
    """Save Coinbase v2 API credentials"""
    try:
        data = request.get_json()
        
        api_key_id = data.get('api_key_id')
        api_key_secret = data.get('api_key_secret')
        wallet_secret = data.get('wallet_secret')
        access_token = data.get('access_token')
        
        if not all([api_key_id, api_key_secret, wallet_secret]):
            return jsonify({
                'success': False,
                'error': 'Missing required credentials'
            }), 400
        
        client = CoinbaseV2Client(user_id=str(current_user.id))
        client.save_credentials(api_key_id, api_key_secret, wallet_secret, access_token)
        
        return jsonify({
            'success': True,
            'message': 'Coinbase v2 credentials saved successfully'
        })
    
    except Exception as e:
        logger.error(f"Error saving Coinbase v2 credentials: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ACCOUNT MANAGEMENT ENDPOINTS
@coinbase_v2_bp.route('/api/coinbase-v2/accounts', methods=['GET'])
@login_required
def list_accounts():
    """List all user accounts across EVM and Solana networks"""
    try:
        client = CoinbaseV2Client(user_id=str(current_user.id))
        accounts = client.list_accounts()
        
        return jsonify({
            'success': True,
            'accounts': accounts,
            'count': len(accounts)
        })
    
    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@coinbase_v2_bp.route('/api/coinbase-v2/accounts/create-evm', methods=['POST'])
@login_required
def create_evm_account():
    """Create a new EVM account"""
    try:
        data = request.get_json()
        network = data.get('network', 'base-sepolia')
        
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.create_evm_account(network)
        
        return jsonify({
            'success': True,
            'account': result
        })
    
    except Exception as e:
        logger.error(f"Error creating EVM account: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@coinbase_v2_bp.route('/api/coinbase-v2/accounts/create-smart', methods=['POST'])
@login_required
def create_smart_account():
    """Create a new Smart Account with advanced features"""
    try:
        data = request.get_json()
        owner_address = data.get('owner_address')
        network = data.get('network', 'base-sepolia')
        
        if not owner_address:
            return jsonify({
                'success': False,
                'error': 'Owner address is required'
            }), 400
        
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.create_smart_account(owner_address, network)
        
        return jsonify({
            'success': True,
            'smart_account': result
        })
    
    except Exception as e:
        logger.error(f"Error creating Smart Account: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@coinbase_v2_bp.route('/api/coinbase-v2/accounts/create-solana', methods=['POST'])
@login_required
def create_solana_account():
    """Create a new Solana account"""
    try:
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.create_solana_account()
        
        return jsonify({
            'success': True,
            'account': result
        })
    
    except Exception as e:
        logger.error(f"Error creating Solana account: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@coinbase_v2_bp.route('/api/coinbase-v2/accounts/<address>/balance', methods=['GET'])
@login_required
def get_account_balance(address):
    """Get account balance for specific address"""
    try:
        network = request.args.get('network', 'base-sepolia')
        
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.get_account_balance(address, network)
        
        return jsonify({
            'success': True,
            'balance': result
        })
    
    except Exception as e:
        logger.error(f"Error getting account balance: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# TRANSACTION ENDPOINTS
@coinbase_v2_bp.route('/api/coinbase-v2/transactions/send', methods=['POST'])
@login_required
def send_transaction():
    """Send a standard EVM transaction"""
    try:
        data = request.get_json()
        
        from_address = data.get('from_address')
        to_address = data.get('to_address')
        value = data.get('value')
        network = data.get('network', 'base-sepolia')
        data_field = data.get('data', '0x')
        
        if not all([from_address, to_address, value]):
            return jsonify({
                'success': False,
                'error': 'Missing required transaction fields'
            }), 400
        
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.send_transaction(from_address, to_address, value, network, data_field)
        
        return jsonify({
            'success': True,
            'transaction': result
        })
    
    except Exception as e:
        logger.error(f"Error sending transaction: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@coinbase_v2_bp.route('/api/coinbase-v2/user-operations/send', methods=['POST'])
@login_required
def send_user_operation():
    """Send a user operation via Smart Account"""
    try:
        data = request.get_json()
        
        smart_account_address = data.get('smart_account_address')
        calls = data.get('calls', [])
        network = data.get('network', 'base-sepolia')
        paymaster_url = data.get('paymaster_url')
        
        if not smart_account_address or not calls:
            return jsonify({
                'success': False,
                'error': 'Smart account address and calls are required'
            }), 400
        
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.send_user_operation(smart_account_address, calls, network, paymaster_url)
        
        return jsonify({
            'success': True,
            'user_operation': result
        })
    
    except Exception as e:
        logger.error(f"Error sending user operation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@coinbase_v2_bp.route('/api/coinbase-v2/transactions/batch', methods=['POST'])
@login_required
def batch_transactions():
    """Batch multiple transactions in a single user operation"""
    try:
        data = request.get_json()
        
        smart_account_address = data.get('smart_account_address')
        transactions = data.get('transactions', [])
        network = data.get('network', 'base-sepolia')
        
        if not smart_account_address or not transactions:
            return jsonify({
                'success': False,
                'error': 'Smart account address and transactions are required'
            }), 400
        
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.batch_transactions(smart_account_address, transactions, network)
        
        return jsonify({
            'success': True,
            'batch_result': result
        })
    
    except Exception as e:
        logger.error(f"Error batching transactions: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@coinbase_v2_bp.route('/api/coinbase-v2/transactions/<transaction_hash>/wait', methods=['GET'])
@login_required
def wait_for_transaction(transaction_hash):
    """Wait for transaction confirmation"""
    try:
        network = request.args.get('network', 'base-sepolia')
        timeout = int(request.args.get('timeout', 300))
        
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.wait_for_transaction(transaction_hash, network, timeout)
        
        return jsonify({
            'success': True,
            'transaction': result
        })
    
    except Exception as e:
        logger.error(f"Error waiting for transaction: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# SWAP AND TRADING ENDPOINTS
@coinbase_v2_bp.route('/api/coinbase-v2/swaps/quote', methods=['GET'])
@login_required
def get_swap_quote():
    """Get a quote for token swap"""
    try:
        from_asset = request.args.get('from_asset')
        to_asset = request.args.get('to_asset')
        amount = request.args.get('amount')
        network = request.args.get('network', 'base-sepolia')
        
        if not all([from_asset, to_asset, amount]):
            return jsonify({
                'success': False,
                'error': 'Missing required swap parameters'
            }), 400
        
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.get_swap_quote(from_asset, to_asset, amount, network)
        
        return jsonify({
            'success': True,
            'quote': result
        })
    
    except Exception as e:
        logger.error(f"Error getting swap quote: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@coinbase_v2_bp.route('/api/coinbase-v2/swaps/execute', methods=['POST'])
@login_required
def execute_swap():
    """Execute a token swap using a quote"""
    try:
        data = request.get_json()
        
        from_address = data.get('from_address')
        quote_id = data.get('quote_id')
        network = data.get('network', 'base-sepolia')
        
        if not all([from_address, quote_id]):
            return jsonify({
                'success': False,
                'error': 'Missing required swap execution parameters'
            }), 400
        
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.execute_swap(from_address, quote_id, network)
        
        return jsonify({
            'success': True,
            'swap_result': result
        })
    
    except Exception as e:
        logger.error(f"Error executing swap: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# GAS SPONSORSHIP ENDPOINTS
@coinbase_v2_bp.route('/api/coinbase-v2/transactions/sponsor', methods=['POST'])
@login_required
def sponsor_transaction():
    """Sponsor gas fees for a user operation"""
    try:
        data = request.get_json()
        
        smart_account_address = data.get('smart_account_address')
        calls = data.get('calls', [])
        network = data.get('network', 'base-sepolia')
        
        if not smart_account_address or not calls:
            return jsonify({
                'success': False,
                'error': 'Smart account address and calls are required'
            }), 400
        
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.sponsor_transaction(smart_account_address, calls, network)
        
        return jsonify({
            'success': True,
            'sponsored_transaction': result
        })
    
    except Exception as e:
        logger.error(f"Error sponsoring transaction: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# FAUCET ENDPOINTS (TESTNET ONLY)
@coinbase_v2_bp.route('/api/coinbase-v2/faucet/request', methods=['POST'])
@login_required
def request_faucet():
    """Request testnet tokens from faucet"""
    try:
        data = request.get_json()
        
        address = data.get('address')
        network = data.get('network', 'base-sepolia')
        asset = data.get('asset', 'eth')
        
        if not address:
            return jsonify({
                'success': False,
                'error': 'Address is required'
            }), 400
        
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.request_faucet(address, network, asset)
        
        return jsonify({
            'success': True,
            'faucet_result': result
        })
    
    except Exception as e:
        logger.error(f"Error requesting faucet: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# MESSAGE SIGNING ENDPOINTS
@coinbase_v2_bp.route('/api/coinbase-v2/sign-message', methods=['POST'])
@login_required
def sign_message():
    """Sign a message with an account"""
    try:
        data = request.get_json()
        
        address = data.get('address')
        message = data.get('message')
        network = data.get('network', 'base-sepolia')
        
        if not all([address, message]):
            return jsonify({
                'success': False,
                'error': 'Address and message are required'
            }), 400
        
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.sign_message(address, message, network)
        
        return jsonify({
            'success': True,
            'signature': result
        })
    
    except Exception as e:
        logger.error(f"Error signing message: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# NETWORK AND UTILITY ENDPOINTS
@coinbase_v2_bp.route('/api/coinbase-v2/networks', methods=['GET'])
@login_required
def get_supported_networks():
    """Get list of supported networks"""
    try:
        client = CoinbaseV2Client(user_id=str(current_user.id))
        networks = client.get_supported_networks()
        
        return jsonify({
            'success': True,
            'networks': networks,
            'count': len(networks)
        })
    
    except Exception as e:
        logger.error(f"Error getting supported networks: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@coinbase_v2_bp.route('/api/coinbase-v2/networks/<network>/fees', methods=['GET'])
@login_required
def get_network_fees(network):
    """Get current network fees"""
    try:
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.get_network_fees(network)
        
        return jsonify({
            'success': True,
            'fees': result
        })
    
    except Exception as e:
        logger.error(f"Error getting network fees: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@coinbase_v2_bp.route('/api/coinbase-v2/estimate-gas', methods=['POST'])
@login_required
def estimate_gas():
    """Estimate gas for a transaction"""
    try:
        data = request.get_json()
        
        from_address = data.get('from_address')
        to_address = data.get('to_address')
        value = data.get('value')
        data_field = data.get('data', '0x')
        network = data.get('network', 'base-sepolia')
        
        if not all([from_address, to_address, value]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields for gas estimation'
            }), 400
        
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.estimate_gas(from_address, to_address, value, data_field, network)
        
        return jsonify({
            'success': True,
            'gas_estimate': result
        })
    
    except Exception as e:
        logger.error(f"Error estimating gas: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# SECURITY ENDPOINTS
@coinbase_v2_bp.route('/api/coinbase-v2/wallet-secret/rotate', methods=['POST'])
@login_required
def rotate_wallet_secret():
    """Rotate wallet secret for enhanced security"""
    try:
        data = request.get_json()
        new_wallet_secret = data.get('new_wallet_secret')
        
        if not new_wallet_secret:
            return jsonify({
                'success': False,
                'error': 'New wallet secret is required'
            }), 400
        
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.rotate_wallet_secret(new_wallet_secret)
        
        return jsonify({
            'success': True,
            'rotation_result': result
        })
    
    except Exception as e:
        logger.error(f"Error rotating wallet secret: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# DIAGNOSTIC ENDPOINTS
@coinbase_v2_bp.route('/api/coinbase-v2/status', methods=['GET'])
@login_required
def get_api_status():
    """Get API status and health"""
    try:
        client = CoinbaseV2Client(user_id=str(current_user.id))
        result = client.get_api_status()
        
        return jsonify({
            'success': True,
            'status': result
        })
    
    except Exception as e:
        logger.error(f"Error getting API status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500