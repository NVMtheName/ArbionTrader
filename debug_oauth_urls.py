#!/usr/bin/env python3
"""
Debug script to check what OAuth redirect URLs are being generated
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from flask import url_for

def debug_oauth_urls():
    """Debug OAuth redirect URLs"""
    app = create_app()
    
    with app.app_context():
        print("=== OAuth Redirect URL Debug ===")
        
        # Get the URLs that would be generated
        try:
            schwab_url = url_for('main.oauth_callback_schwab', _external=True)
            print(f"Schwab OAuth redirect URL: {schwab_url}")
        except Exception as e:
            print(f"Error generating Schwab URL: {e}")
            
        try:
            coinbase_url = url_for('main.oauth_callback_coinbase', _external=True)
            print(f"Coinbase OAuth redirect URL: {coinbase_url}")
        except Exception as e:
            print(f"Error generating Coinbase URL: {e}")
            
        print("\n=== Environment Info ===")
        print(f"SERVER_NAME: {app.config.get('SERVER_NAME')}")
        print(f"APPLICATION_ROOT: {app.config.get('APPLICATION_ROOT')}")
        print(f"PREFERRED_URL_SCHEME: {app.config.get('PREFERRED_URL_SCHEME')}")
        
        print("\n=== Coinbase OAuth Setup Instructions ===")
        print("To fix the redirect issue, ensure your Coinbase OAuth app has this EXACT redirect URI:")
        print(f"  {coinbase_url}")
        print("\nSteps:")
        print("1. Go to Coinbase Developer Console")
        print("2. Edit your OAuth application")
        print("3. Set the redirect URI to exactly: https://arbion.ai/oauth_callback/crypto")
        print("4. Save the changes")
        print("5. Test the OAuth flow again")

if __name__ == '__main__':
    debug_oauth_urls()