#!/usr/bin/env python3
"""
Debug script to check Schwab OAuth configuration
"""

import os
from app import app
from flask import url_for
from models import OAuthClientCredential, User

def debug_schwab_oauth():
    """Debug Schwab OAuth configuration"""
    
    with app.app_context():
        print("=== Schwab OAuth Debug ===")
        
        # Check Flask configuration
        print(f"SERVER_NAME: {app.config.get('SERVER_NAME')}")
        print(f"PREFERRED_URL_SCHEME: {app.config.get('PREFERRED_URL_SCHEME')}")
        print(f"APPLICATION_ROOT: {app.config.get('APPLICATION_ROOT')}")
        
        # Check OAuth callback URL
        callback_url = url_for('main.oauth_callback_schwab', _external=True)
        print(f"OAuth callback URL: {callback_url}")
        
        # Check all users and their OAuth credentials
        users = User.query.all()
        print(f"\nFound {len(users)} users:")
        
        for user in users:
            print(f"\nUser: {user.username} (ID: {user.id})")
            
            # Check Schwab OAuth credentials
            schwab_creds = OAuthClientCredential.query.filter_by(
                user_id=user.id,
                provider='schwab',
                is_active=True
            ).all()
            
            if schwab_creds:
                for cred in schwab_creds:
                    print(f"  ✓ Schwab OAuth configured:")
                    print(f"    Client ID: {cred.client_id[:10]}...")
                    print(f"    Redirect URI: {cred.redirect_uri}")
                    print(f"    Created: {cred.created_at}")
            else:
                print(f"  ✗ No Schwab OAuth credentials configured")
        
        print(f"\n=== Next Steps ===")
        print(f"1. In Arbion, go to API Settings and configure your Schwab OAuth2 client credentials")
        print(f"2. In Schwab Developer Portal, set redirect URI to: {callback_url}")
        print(f"3. Make sure your Schwab OAuth app is approved and active")
        print(f"4. Test the OAuth flow again")

if __name__ == "__main__":
    debug_schwab_oauth()