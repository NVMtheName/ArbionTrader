#!/usr/bin/env python3
"""
Fix script to standardize Coinbase OAuth redirect URI configuration
"""

import os
import sys
from app import create_app
from models import OAuthClientCredential, User

def fix_coinbase_redirect():
    """Fix Coinbase OAuth redirect URI configuration"""
    app = create_app()
    
    with app.app_context():
        print("="*60)
        print("FIXING COINBASE OAUTH REDIRECT URI")
        print("="*60)
        
        # Check all users' Coinbase OAuth configurations
        coinbase_configs = OAuthClientCredential.query.filter_by(
            provider='coinbase'
        ).all()
        
        if not coinbase_configs:
            print("❌ No Coinbase OAuth configurations found")
            return
        
        # Standard redirect URI (use www subdomain to match your error message)
        standard_redirect_uri = "https://www.arbion.ai/oauth_callback/crypto"
        
        print(f"🔧 Setting all Coinbase OAuth configurations to use: {standard_redirect_uri}")
        
        from app import db
        
        for config in coinbase_configs:
            user = User.query.get(config.user_id)
            old_uri = config.redirect_uri
            
            print(f"\n👤 User: {user.username if user else 'Unknown'} (ID: {config.user_id})")
            print(f"📱 Client ID: {config.client_id}")
            print(f"🔗 Old Redirect URI: {old_uri}")
            print(f"🔗 New Redirect URI: {standard_redirect_uri}")
            
            # Update the redirect URI
            config.redirect_uri = standard_redirect_uri
            config.is_active = True
            
            print("✅ Updated successfully")
        
        # Commit changes
        db.session.commit()
        
        print("\n" + "="*60)
        print("INSTRUCTIONS:")
        print("="*60)
        print("1. Your Coinbase OAuth app should be configured with:")
        print(f"   Redirect URI: {standard_redirect_uri}")
        print("")
        print("2. Make sure your Coinbase OAuth app settings match exactly:")
        print("   - Go to https://www.coinbase.com/settings/api")
        print("   - Edit your OAuth2 application")
        print(f"   - Set redirect URI to: {standard_redirect_uri}")
        print("   - Save the changes")
        print("")
        print("3. Try the OAuth flow again from Arbion's API Settings")
        print("")
        print("✅ All redirect URIs have been standardized!")

if __name__ == "__main__":
    fix_coinbase_redirect()