#!/usr/bin/env python3
"""
Debug script to check Coinbase OAuth configuration
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app import create_app
from models import User, OAuthClientCredential
from flask import url_for

def debug_coinbase_oauth():
    """Debug Coinbase OAuth configuration"""
    app = create_app()
    
    with app.app_context():
        print("=== Coinbase OAuth Debug ===")
        
        # Check users and their OAuth credentials
        users = User.query.all()
        print(f"Total users: {len(users)}")
        
        for user in users:
            print(f"\nUser: {user.username} (ID: {user.id})")
            
            # Check OAuth client credentials
            oauth_creds = OAuthClientCredential.query.filter_by(
                user_id=user.id,
                provider='coinbase'
            ).all()
            
            print(f"Coinbase OAuth credentials: {len(oauth_creds)}")
            
            for cred in oauth_creds:
                print(f"  - Client ID: {cred.client_id}")
                print(f"  - Redirect URI: {cred.redirect_uri}")
                print(f"  - Active: {cred.is_active}")
                print(f"  - Created: {cred.created_at}")
                print(f"  - Updated: {cred.updated_at}")
        
        # Generate expected redirect URI
        try:
            expected_redirect = url_for('main.oauth_callback_coinbase', _external=True)
            print(f"\nExpected redirect URI: {expected_redirect}")
        except Exception as e:
            print(f"Error generating redirect URI: {e}")
        
        # Check server configuration
        print(f"\nServer configuration:")
        print(f"SERVER_NAME: {app.config.get('SERVER_NAME', 'Not set')}")
        print(f"PREFERRED_URL_SCHEME: {app.config.get('PREFERRED_URL_SCHEME', 'Not set')}")
        
        print("\n=== DNS Issue Information ===")
        print("Current DNS Status:")
        print("- www.arbion.ai: ✓ Working (points to hidden-seahorse-r47usw41xjogji02um4hhrq2.herokudns.com)")
        print("- arbion.ai: ✗ Not working (points to wrong server)")
        print("\nTo fix the OAuth issue:")
        print("1. Add A record for @ domain pointing to 3.33.241.96 in GoDaddy")
        print("2. Wait for DNS propagation (15 minutes to 24 hours)")
        print("3. OAuth callbacks will then work correctly")
        print("\nTemporary workaround:")
        print("- Use www.arbion.ai instead of arbion.ai for OAuth setup")
        print("- Update your Coinbase OAuth app redirect URI to use www.arbion.ai")

if __name__ == "__main__":
    debug_coinbase_oauth()