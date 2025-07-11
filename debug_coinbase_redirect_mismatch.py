#!/usr/bin/env python3
"""
Debug script to identify and fix Coinbase OAuth redirect URI mismatch
"""

import os
import sys
from app import create_app
from models import OAuthClientCredential, User
from flask import url_for

def debug_coinbase_redirect_mismatch():
    """Debug Coinbase OAuth redirect URI mismatch"""
    app = create_app()
    
    with app.app_context():
        print("="*80)
        print("COINBASE OAUTH REDIRECT URI MISMATCH DEBUGGER")
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
            print(f"📝 Client ID: {config.client_id}")
            print(f"🔗 Configured Redirect URI: {config.redirect_uri}")
            
            # Check what URL Flask would generate
            with app.test_request_context():
                flask_url = url_for('main.oauth_callback_coinbase', _external=True)
                print(f"🏗️  Flask Generated URL: {flask_url}")
                
                # Check if they match
                if config.redirect_uri == flask_url:
                    print("✅ Redirect URIs MATCH")
                else:
                    print("❌ Redirect URIs DO NOT MATCH")
                    print(f"   Expected: {config.redirect_uri}")
                    print(f"   Generated: {flask_url}")
                    
                    # Suggest fix
                    print("\n🔧 SUGGESTED FIXES:")
                    print("1. Update your Coinbase OAuth app redirect URI to:")
                    print(f"   {flask_url}")
                    print("2. OR update the stored redirect URI in the database to:")
                    print(f"   {config.redirect_uri}")
                    
                    # Check common variations
                    print("\n🔍 COMMON VARIATIONS:")
                    variations = [
                        "https://arbion.ai/oauth_callback/crypto",
                        "https://www.arbion.ai/oauth_callback/crypto",
                        "https://arbion.ai/oauth_callback/coinbase",
                        "https://www.arbion.ai/oauth_callback/coinbase",
                    ]
                    
                    for var in variations:
                        print(f"   {var} {'✓' if var == config.redirect_uri else '✗'}")
        
        print("\n" + "="*80)
        print("ENVIRONMENT CONFIGURATION")
        print("="*80)
        print(f"SERVER_NAME: {app.config.get('SERVER_NAME', 'Not set')}")
        print(f"PREFERRED_URL_SCHEME: {app.config.get('PREFERRED_URL_SCHEME', 'Not set')}")
        print(f"APPLICATION_ROOT: {app.config.get('APPLICATION_ROOT', 'Not set')}")

if __name__ == "__main__":
    debug_coinbase_redirect_mismatch()