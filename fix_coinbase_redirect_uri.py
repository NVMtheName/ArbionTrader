#!/usr/bin/env python3
"""
Fix script to update Coinbase OAuth redirect URI configuration
"""

import os
import sys
from app import create_app
from models import OAuthClientCredential, User
from app import db

def fix_coinbase_redirect_uri():
    """Fix Coinbase OAuth redirect URI configuration"""
    app = create_app()
    
    with app.app_context():
        print("="*80)
        print("COINBASE OAUTH REDIRECT URI FIXER")
        print("="*80)
        
        # Get all Coinbase OAuth configurations
        coinbase_configs = OAuthClientCredential.query.filter_by(
            provider='coinbase',
            is_active=True
        ).all()
        
        if not coinbase_configs:
            print("❌ No active Coinbase OAuth configurations found")
            return
        
        for config in coinbase_configs:
            user = User.query.get(config.user_id)
            print(f"\n👤 User: {user.username if user else 'Unknown'}")
            print(f"📝 Current Redirect URI: {config.redirect_uri}")
            
            # Check current URI and suggest the correct one
            current_uri = config.redirect_uri
            
            # Determine the correct URI based on the error message
            if "https://www.arbion.ai/oauth_callback/crypto" in current_uri:
                # Already using www version - this should be correct
                print("✅ Using www version - this matches the error message")
                continue
            elif "https://arbion.ai/oauth_callback/crypto" in current_uri:
                # Using non-www version, but error shows www version is expected
                correct_uri = "https://www.arbion.ai/oauth_callback/crypto"
                print(f"🔧 Updating to: {correct_uri}")
                
                # Update the redirect URI
                config.redirect_uri = correct_uri
                db.session.commit()
                print("✅ Updated successfully!")
            else:
                # Some other URI - set to the expected one
                correct_uri = "https://www.arbion.ai/oauth_callback/crypto"
                print(f"🔧 Updating to: {correct_uri}")
                
                # Update the redirect URI
                config.redirect_uri = correct_uri
                db.session.commit()
                print("✅ Updated successfully!")
        
        print("\n" + "="*80)
        print("IMPORTANT: After updating the redirect URI here, you must also:")
        print("1. Log in to your Coinbase Developer Console")
        print("2. Go to your OAuth2 app settings")
        print("3. Update the redirect URI to: https://www.arbion.ai/oauth_callback/crypto")
        print("4. Save the changes in Coinbase")
        print("="*80)

if __name__ == "__main__":
    fix_coinbase_redirect_uri()