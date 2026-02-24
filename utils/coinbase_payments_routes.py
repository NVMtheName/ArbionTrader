"""
Flask routes for Coinbase Payments API.
Deposits, withdrawals, transfers, crypto addresses, and conversions.
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
import logging

logger = logging.getLogger(__name__)

coinbase_payments_bp = Blueprint('coinbase_payments', __name__)


def _client():
    from utils.coinbase_payments import CoinbasePaymentsClient
    return CoinbasePaymentsClient(user_id=str(current_user.id))


# ------------------------------------------------------------------
# Payment Methods
# ------------------------------------------------------------------

@coinbase_payments_bp.route('/api/coinbase-payments/payment-methods', methods=['GET'])
@login_required
def list_payment_methods():
    try:
        result = _client().list_payment_methods()
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error listing payment methods: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_payments_bp.route('/api/coinbase-payments/payment-methods/<pm_id>', methods=['GET'])
@login_required
def get_payment_method(pm_id):
    try:
        result = _client().get_payment_method(pm_id)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error getting payment method: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# Deposits
# ------------------------------------------------------------------

@coinbase_payments_bp.route('/api/coinbase-payments/deposits/payment-method', methods=['POST'])
@login_required
def deposit_from_payment_method():
    try:
        data = request.get_json()
        for field in ['amount', 'currency', 'payment_method_id']:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        result = _client().deposit_from_payment_method(
            data['amount'], data['currency'], data['payment_method_id']
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error depositing from payment method: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_payments_bp.route('/api/coinbase-payments/deposits/coinbase-account', methods=['POST'])
@login_required
def deposit_from_coinbase_account():
    try:
        data = request.get_json()
        for field in ['amount', 'currency', 'coinbase_account_id']:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        result = _client().deposit_from_coinbase_account(
            data['amount'], data['currency'], data['coinbase_account_id']
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error depositing from Coinbase account: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# Withdrawals
# ------------------------------------------------------------------

@coinbase_payments_bp.route('/api/coinbase-payments/withdrawals/payment-method', methods=['POST'])
@login_required
def withdraw_to_payment_method():
    try:
        data = request.get_json()
        for field in ['amount', 'currency', 'payment_method_id']:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        result = _client().withdraw_to_payment_method(
            data['amount'], data['currency'], data['payment_method_id']
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error withdrawing to payment method: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_payments_bp.route('/api/coinbase-payments/withdrawals/coinbase-account', methods=['POST'])
@login_required
def withdraw_to_coinbase_account():
    try:
        data = request.get_json()
        for field in ['amount', 'currency', 'coinbase_account_id']:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        result = _client().withdraw_to_coinbase_account(
            data['amount'], data['currency'], data['coinbase_account_id']
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error withdrawing to Coinbase account: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_payments_bp.route('/api/coinbase-payments/withdrawals/crypto', methods=['POST'])
@login_required
def withdraw_to_crypto_address():
    try:
        data = request.get_json()
        for field in ['amount', 'currency', 'crypto_address']:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        result = _client().withdraw_to_crypto_address(
            amount=data['amount'],
            currency=data['currency'],
            crypto_address=data['crypto_address'],
            network=data.get('network'),
            destination_tag=data.get('destination_tag'),
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error withdrawing to crypto address: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_payments_bp.route('/api/coinbase-payments/withdrawals/fee-estimate', methods=['GET'])
@login_required
def get_withdrawal_fee_estimate():
    try:
        currency = request.args.get('currency')
        crypto_address = request.args.get('crypto_address')
        if not currency or not crypto_address:
            return jsonify({'success': False, 'error': 'currency and crypto_address required'}), 400
        result = _client().get_crypto_withdrawal_fee_estimate(
            currency=currency,
            crypto_address=crypto_address,
            network=request.args.get('network'),
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error getting fee estimate: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# Transfers
# ------------------------------------------------------------------

@coinbase_payments_bp.route('/api/coinbase-payments/transfers', methods=['GET'])
@login_required
def list_transfers():
    try:
        result = _client().list_transfers(
            transfer_type=request.args.get('type'),
            limit=request.args.get('limit', type=int),
            cursor=request.args.get('cursor'),
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error listing transfers: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_payments_bp.route('/api/coinbase-payments/transfers/<transfer_id>', methods=['GET'])
@login_required
def get_transfer(transfer_id):
    try:
        result = _client().get_transfer(transfer_id)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error getting transfer: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# Coinbase Wallets & Crypto Addresses
# ------------------------------------------------------------------

@coinbase_payments_bp.route('/api/coinbase-payments/wallets', methods=['GET'])
@login_required
def list_coinbase_wallets():
    try:
        result = _client().list_coinbase_wallets()
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error listing wallets: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_payments_bp.route('/api/coinbase-payments/wallets/<account_id>/addresses', methods=['POST'])
@login_required
def generate_crypto_address(account_id):
    try:
        result = _client().generate_crypto_address(account_id)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error generating crypto address: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# Conversions
# ------------------------------------------------------------------

@coinbase_payments_bp.route('/api/coinbase-payments/conversions', methods=['POST'])
@login_required
def convert_currency():
    try:
        data = request.get_json()
        for field in ['from_currency', 'to_currency', 'amount']:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        result = _client().convert_currency(
            data['from_currency'], data['to_currency'], data['amount']
        )
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error converting currency: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_payments_bp.route('/api/coinbase-payments/conversions/<conversion_id>', methods=['GET'])
@login_required
def get_conversion(conversion_id):
    try:
        result = _client().get_conversion(conversion_id)
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error getting conversion: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ------------------------------------------------------------------
# Currencies & Fees
# ------------------------------------------------------------------

@coinbase_payments_bp.route('/api/coinbase-payments/currencies', methods=['GET'])
@login_required
def list_currencies():
    try:
        result = _client().list_currencies()
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error listing currencies: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500


@coinbase_payments_bp.route('/api/coinbase-payments/fees', methods=['GET'])
@login_required
def get_fees():
    try:
        result = _client().get_fees()
        return jsonify({'success': True, **result})
    except Exception as e:
        logger.error("Error getting fees: %s", e)
        return jsonify({'success': False, 'error': str(e)}), 500
