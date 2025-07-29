#!/usr/bin/env python3
"""
Coinbase Wallet Address Fetcher

This script demonstrates how to fetch wallet addresses from Coinbase using OAuth2 authentication.
It supports fetching addresses for BTC, ETH, and other supported currencies.

Required OAuth2 Scopes:
- wallet:accounts:read: Required to list user accounts
- wallet:addresses:read: Required to fetch wallet addresses

Usage:
1. Complete OAuth2 flow and obtain a valid access token
2. Use the functions below to fetch wallet addresses
3. Handle errors appropriately based on scope permissions

Author: Arbion AI Trading Platform
Date: July 29, 2025
"""

import requests
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CoinbaseWalletAddressFetcher:
    """
    Fetches wallet addresses from Coinbase using OAuth2 authentication
    """
    
    def __init__(self, access_token):
        """
        Initialize the wallet address fetcher
        
        Args:
            access_token (str): Valid OAuth2 access token with required scopes
        """
        self.access_token = access_token
        self.api_base_url = 'https://api.coinbase.com/v2'
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'User-Agent': 'Arbion Trading Platform/1.0'
        }
    
    def validate_scopes(self):
        """
        Validate that the access token has the required scopes
        
        Returns:
            dict: Validation result with scope information
        """
        try:
            # Test accounts endpoint (requires wallet:accounts:read)
            response = requests.get(
                f'{self.api_base_url}/accounts',
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 403:
                return {
                    'valid': False,
                    'error': 'Missing required scope: wallet:accounts:read',
                    'required_scopes': ['wallet:accounts:read', 'wallet:addresses:read']
                }
            elif response.status_code != 200:
                return {
                    'valid': False,
                    'error': f'API error: HTTP {response.status_code}',
                    'response': response.text
                }
            
            # Test a specific account's addresses (requires wallet:addresses:read)
            accounts_data = response.json()
            if accounts_data.get('data'):
                account_id = accounts_data['data'][0]['id']
                
                addresses_response = requests.get(
                    f'{self.api_base_url}/accounts/{account_id}/addresses',
                    headers=self.headers,
                    timeout=30
                )
                
                if addresses_response.status_code == 403:
                    return {
                        'valid': False,
                        'error': 'Missing required scope: wallet:addresses:read',
                        'required_scopes': ['wallet:accounts:read', 'wallet:addresses:read']
                    }
            
            return {
                'valid': True,
                'message': 'All required scopes are present',
                'scopes_verified': ['wallet:accounts:read', 'wallet:addresses:read']
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f'Scope validation failed: {str(e)}'
            }
    
    def get_all_accounts(self):
        """
        Fetch all user accounts from Coinbase
        
        Returns:
            dict: API response with all accounts
        """
        try:
            logger.info("Fetching all user accounts...")
            
            response = requests.get(
                f'{self.api_base_url}/accounts',
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 200:
                accounts_data = response.json()
                logger.info(f"Successfully fetched {len(accounts_data.get('data', []))} accounts")
                return {
                    'success': True,
                    'accounts': accounts_data.get('data', []),
                    'total_accounts': len(accounts_data.get('data', []))
                }
            elif response.status_code == 403:
                return {
                    'success': False,
                    'error': 'Insufficient permissions. Required scope: wallet:accounts:read'
                }
            else:
                return {
                    'success': False,
                    'error': f'API error: HTTP {response.status_code}',
                    'response': response.text
                }
                
        except Exception as e:
            logger.error(f"Error fetching accounts: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_wallet_addresses(self, currencies=['BTC', 'ETH']):
        """
        Fetch wallet addresses for specified currencies
        
        Args:
            currencies (list): List of currency codes to fetch addresses for
            
        Returns:
            dict: Wallet addresses and account information
        """
        try:
            logger.info(f"Fetching wallet addresses for currencies: {currencies}")
            
            # Step 1: Get all accounts
            accounts_result = self.get_all_accounts()
            if not accounts_result['success']:
                return accounts_result
            
            all_accounts = accounts_result['accounts']
            
            # Step 2: Filter accounts by requested currencies
            target_accounts = []
            for account in all_accounts:
                currency = account.get('currency', {}).get('code', '')
                if currency in currencies:
                    target_accounts.append({
                        'id': account.get('id'),
                        'name': account.get('name'),
                        'currency': currency,
                        'type': account.get('type'),
                        'balance': account.get('balance', {}),
                        'primary': account.get('primary', False)
                    })
            
            if not target_accounts:
                return {
                    'success': True,
                    'wallet_addresses': {},
                    'message': f'No accounts found for currencies: {currencies}',
                    'available_currencies': [acc.get('currency', {}).get('code') for acc in all_accounts]
                }
            
            logger.info(f"Found {len(target_accounts)} accounts for target currencies")
            
            # Step 3: Fetch addresses for each target account
            wallet_addresses = {}
            successful_fetches = 0
            
            for account in target_accounts:
                account_id = account['id']
                currency = account['currency']
                
                try:
                    logger.info(f"Fetching addresses for {currency} account: {account_id}")
                    
                    addresses_response = requests.get(
                        f'{self.api_base_url}/accounts/{account_id}/addresses',
                        headers=self.headers,
                        timeout=30
                    )
                    
                    if addresses_response.status_code == 200:
                        addresses_data = addresses_response.json()
                        addresses_list = addresses_data.get('data', [])
                        
                        if addresses_list:
                            # Get the primary (first) address
                            primary_address = addresses_list[0]
                            
                            wallet_addresses[currency] = {
                                'address': primary_address.get('address'),
                                'name': primary_address.get('name', f'{currency} Address'),
                                'account_id': account_id,
                                'account_name': account['name'],
                                'account_type': account['type'],
                                'balance': account['balance'],
                                'primary_account': account['primary'],
                                'network': primary_address.get('network'),
                                'created_at': primary_address.get('created_at'),
                                'total_addresses': len(addresses_list),
                                'all_addresses': [
                                    {
                                        'address': addr.get('address'),
                                        'name': addr.get('name'),
                                        'network': addr.get('network')
                                    } for addr in addresses_list
                                ]
                            }
                            
                            successful_fetches += 1
                            logger.info(f"✓ {currency}: {primary_address.get('address')}")
                        else:
                            wallet_addresses[currency] = {
                                'address': None,
                                'error': 'No addresses found for this account',
                                'account_id': account_id,
                                'account_name': account['name']
                            }
                            logger.warning(f"✗ {currency}: No addresses found")
                    
                    elif addresses_response.status_code == 403:
                        error_msg = f"Insufficient permissions to fetch {currency} addresses. Required scope: wallet:addresses:read"
                        wallet_addresses[currency] = {
                            'address': None,
                            'error': error_msg,
                            'account_id': account_id,
                            'scope_required': 'wallet:addresses:read'
                        }
                        logger.error(f"✗ {currency}: {error_msg}")
                    
                    else:
                        error_msg = f"Failed to fetch {currency} addresses: HTTP {addresses_response.status_code}"
                        wallet_addresses[currency] = {
                            'address': None,
                            'error': error_msg,
                            'account_id': account_id,
                            'status_code': addresses_response.status_code
                        }
                        logger.error(f"✗ {currency}: {error_msg}")
                
                except Exception as e:
                    error_msg = f"Error fetching {currency} addresses: {str(e)}"
                    wallet_addresses[currency] = {
                        'address': None,
                        'error': error_msg,
                        'account_id': account_id
                    }
                    logger.error(f"✗ {currency}: {error_msg}")
            
            # Return comprehensive result
            return {
                'success': True,
                'wallet_addresses': wallet_addresses,
                'accounts': target_accounts,
                'summary': {
                    'requested_currencies': currencies,
                    'accounts_found': len(target_accounts),
                    'addresses_fetched': successful_fetches,
                    'total_user_accounts': len(all_accounts)
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error fetching wallet addresses: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_primary_wallet_address(self, currency='BTC'):
        """
        Get the primary receiving address for a specific currency
        
        Args:
            currency (str): Currency code (e.g., 'BTC', 'ETH')
            
        Returns:
            dict: Primary wallet address information
        """
        try:
            result = self.get_wallet_addresses([currency])
            
            if result['success'] and currency in result['wallet_addresses']:
                address_info = result['wallet_addresses'][currency]
                
                if address_info.get('address'):
                    return {
                        'success': True,
                        'address': address_info['address'],
                        'currency': currency,
                        'account_id': address_info['account_id'],
                        'account_name': address_info['account_name'],
                        'balance': address_info.get('balance', {}),
                        'network': address_info.get('network'),
                        'primary_account': address_info.get('primary_account', False)
                    }
                else:
                    return {
                        'success': False,
                        'error': address_info.get('error', f'No {currency} address found'),
                        'currency': currency
                    }
            else:
                return {
                    'success': False,
                    'error': result.get('error', f'Failed to fetch {currency} wallet address'),
                    'currency': currency
                }
                
        except Exception as e:
            logger.error(f"Error getting primary {currency} address: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'currency': currency
            }


def example_usage():
    """
    Example demonstrating how to use the Coinbase wallet address fetcher
    """
    # Replace with your actual OAuth2 access token
    ACCESS_TOKEN = "your_oauth2_access_token_here"
    
    if ACCESS_TOKEN == "your_oauth2_access_token_here":
        print("\n❌ Please replace ACCESS_TOKEN with your actual Coinbase OAuth2 access token")
        print("\nTo get an access token:")
        print("1. Create a Coinbase OAuth2 application at https://www.coinbase.com/oauth/applications")
        print("2. Set the redirect URI to match your application")
        print("3. Request scopes: wallet:accounts:read,wallet:addresses:read")
        print("4. Complete the OAuth2 flow to get an access token")
        return
    
    # Initialize the fetcher
    fetcher = CoinbaseWalletAddressFetcher(ACCESS_TOKEN)
    
    # Validate scopes
    print("\n🔍 Validating OAuth2 scopes...")
    scope_validation = fetcher.validate_scopes()
    if not scope_validation['valid']:
        print(f"❌ Scope validation failed: {scope_validation['error']}")
        print(f"Required scopes: {scope_validation.get('required_scopes', [])}")
        return
    
    print("✅ OAuth2 scopes validated successfully")
    
    # Example 1: Get all accounts
    print("\n📋 Fetching all accounts...")
    accounts_result = fetcher.get_all_accounts()
    if accounts_result['success']:
        print(f"✅ Found {accounts_result['total_accounts']} accounts")
        for account in accounts_result['accounts']:
            currency = account.get('currency', {}).get('code', 'Unknown')
            balance = account.get('balance', {})
            amount = balance.get('amount', '0')
            print(f"  - {currency}: {amount} {currency} ({account.get('name', 'Unnamed')})")
    else:
        print(f"❌ Failed to fetch accounts: {accounts_result['error']}")
        return
    
    # Example 2: Get wallet addresses for BTC and ETH
    print("\n🏠 Fetching wallet addresses for BTC and ETH...")
    addresses_result = fetcher.get_wallet_addresses(['BTC', 'ETH'])
    
    if addresses_result['success']:
        wallet_addresses = addresses_result['wallet_addresses']
        
        for currency, info in wallet_addresses.items():
            if info.get('address'):
                print(f"\n✅ {currency} Wallet Address:")
                print(f"  Address: {info['address']}")
                print(f"  Account: {info['account_name']}")
                print(f"  Network: {info.get('network', 'N/A')}")
                print(f"  Balance: {info['balance'].get('amount', '0')} {currency}")
                print(f"  Primary Account: {info.get('primary_account', False)}")
            else:
                print(f"\n❌ {currency}: {info.get('error', 'Unknown error')}")
        
        print(f"\n📊 Summary:")
        summary = addresses_result['summary']
        print(f"  Requested: {summary['requested_currencies']}")
        print(f"  Accounts found: {summary['accounts_found']}")
        print(f"  Addresses fetched: {summary['addresses_fetched']}")
    else:
        print(f"❌ Failed to fetch addresses: {addresses_result['error']}")
    
    # Example 3: Get primary BTC address only
    print("\n₿ Fetching primary BTC address...")
    btc_result = fetcher.get_primary_wallet_address('BTC')
    
    if btc_result['success']:
        print(f"✅ Primary BTC Address: {btc_result['address']}")
        print(f"  Account: {btc_result['account_name']}")
        print(f"  Balance: {btc_result['balance'].get('amount', '0')} BTC")
    else:
        print(f"❌ Failed to get BTC address: {btc_result['error']}")


if __name__ == "__main__":
    print("🏦 Coinbase Wallet Address Fetcher")
    print("=" * 50)
    example_usage()