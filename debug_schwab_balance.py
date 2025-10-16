#!/usr/bin/env python3
"""
Debug Schwab account balance fetching
"""

from app import create_app
app = create_app()

def debug_schwab_balance():
    with app.app_context():
        from models import APICredential, User
        from utils.encryption import decrypt_credentials
        from utils.real_time_data import RealTimeDataFetcher
        
        print("=== Schwab Balance Debug ===")
        
        # Find Schwab credentials
        schwab_creds = APICredential.query.filter_by(provider='schwab', is_active=True).all()
        print(f"Found {len(schwab_creds)} active Schwab credentials")
        
        for cred in schwab_creds:
            print(f"\nUser {cred.user_id}:")
            print(f"  Status: {cred.test_status}")
            print(f"  Last tested: {cred.last_tested}")
            
            try:
                decrypted_creds = decrypt_credentials(cred.encrypted_credentials)
                print(f"  Credential keys: {list(decrypted_creds.keys())}")
                
                # Check if access token exists
                if 'access_token' in decrypted_creds:
                    print(f"  Access token length: {len(decrypted_creds['access_token'])}")
                    
                    # Try to fetch balance
                    fetcher = RealTimeDataFetcher(cred.user_id)
                    result = fetcher.get_live_schwab_balance()
                    
                    if result.get('success'):
                        print(f"  ✓ Balance fetch successful: ${result['balance']:.2f}")
                        print(f"  Accounts: {len(result.get('accounts', []))}")
                    else:
                        print(f"  ✗ Balance fetch failed: {result.get('error', 'Unknown error')}")
                else:
                    print("  ✗ No access token found")
                    
                    # Try OAuth helper
                    try:
                        from utils.schwab_oauth import SchwabOAuth
                        schwab_oauth = SchwabOAuth(user_id=cred.user_id)
                        access_token = schwab_oauth.get_valid_token()
                        
                        if access_token:
                            print(f"  ✓ OAuth helper provided token: {len(access_token)} chars")
                            
                            result = fetcher.get_live_schwab_balance()
                            if result.get('success'):
                                print(f"  ✓ OAuth balance fetch successful: ${result['balance']:.2f}")
                            else:
                                print(f"  ✗ OAuth balance fetch failed: {result.get('error', 'Unknown error')}")
                        else:
                            print("  ✗ OAuth helper couldn't get token")
                    except Exception as oauth_error:
                        print(f"  ✗ OAuth helper error: {oauth_error}")
                        
            except Exception as e:
                print(f"  ✗ Error processing credentials: {e}")
                
        # Test the main balance function
        print("\n=== Testing Main Balance Function ===")
        try:
            from routes import get_account_balance
            from flask_login import login_user
            
            # Get first user
            user = User.query.first()
            if user:
                with app.test_request_context():
                    login_user(user)
                    balance_data = get_account_balance()
                    
                    print(f"Total balance: ${balance_data['total']:.2f}")
                    print(f"Accounts found: {len(balance_data['accounts'])}")
                    print(f"Errors: {balance_data['errors']}")
                    
                    for account in balance_data['accounts']:
                        if account['provider'] == 'schwab':
                            print(f"  Schwab: ${account['balance']:.2f} - {account['status']}")
            else:
                print("No users found")
                
        except Exception as e:
            print(f"Error testing main balance function: {e}")

if __name__ == "__main__":
    debug_schwab_balance()