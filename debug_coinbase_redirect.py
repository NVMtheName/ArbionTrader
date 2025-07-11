#!/usr/bin/env python3
"""
Debug script to check Coinbase OAuth redirect URI configuration
"""

import os
import sys
from app import create_app
from models import OAuthClientCredential, User

def debug_coinbase_redirect():
    """Debug Coinbase OAuth redirect URI configuration"""
    app = create_app()
    
    with app.app_context():
        print("="*60)
        print("COINBASE OAUTH REDIRECT URI DEBUG")
        print("="*60)
        
        # Check all users' Coinbase OAuth configurations
        coinbase_configs = OAuthClientCredential.query.filter_by(
            provider='coinbase',
            is_active=True
        ).all()
        
        if not coinbase_configs:
            print("❌ No active Coinbase OAuth configurations found")
            return
        
        for config in coinbase_configs:
            user = User.query.get(config.user_id)
            print(f"\n👤 User: {user.username if user else 'Unknown'} (ID: {config.user_id})")
            print(f"📱 Client ID: {config.client_id}")
            print(f"🔑 Client Secret: {config.client_secret[:8]}...")
            print(f"🔗 Redirect URI: {config.redirect_uri}")
            print(f"✅ Status: {'Active' if config.is_active else 'Inactive'}")
            print(f"📅 Created: {config.created_at}")
            print(f"🔄 Updated: {config.updated_at}")
            
            # Check if redirect URI matches common patterns
            if 'www.arbion.ai' in config.redirect_uri:
                print("🌐 Uses WWW subdomain")
            elif 'arbion.ai' in config.redirect_uri:
                print("🌐 Uses root domain")
            else:
                print("🌐 Uses custom domain")
        
        print("\n" + "="*60)
        print("RECOMMENDATIONS:")
        print("="*60)
        
        # Check for mixed configurations
        redirect_uris = [config.redirect_uri for config in coinbase_configs]
        unique_uris = set(redirect_uris)
        
        if len(unique_uris) > 1:
            print("⚠️  WARNING: Multiple different redirect URIs detected!")
            for uri in unique_uris:
                print(f"   - {uri}")
            print("   This could cause authentication failures.")
            print("   Consider standardizing on one redirect URI.")
        
        # Check for common issues
        for uri in unique_uris:
            if 'localhost' in uri or '127.0.0.1' in uri:
                print(f"⚠️  WARNING: localhost/127.0.0.1 detected in {uri}")
                print("   This won't work in production.")
            
            if not uri.startswith('https://'):
                print(f"⚠️  WARNING: Non-HTTPS redirect URI: {uri}")
                print("   Coinbase requires HTTPS for production.")
            
            if '/oauth_callback/crypto' not in uri:
                print(f"⚠️  WARNING: Unexpected callback path in {uri}")
                print("   Expected path: /oauth_callback/crypto")
        
        print("\n✅ To fix the redirect URI mismatch:")
        print("1. Update your Coinbase OAuth app settings to use the exact redirect URI shown above")
        print("2. OR update the redirect URI in Arbion's API settings to match your Coinbase app")
        print("3. Make sure both match exactly (case-sensitive)")

if __name__ == "__main__":
    debug_coinbase_redirect()