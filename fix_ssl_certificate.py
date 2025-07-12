#!/usr/bin/env python3
"""
Fix SSL certificate configuration for arbion.ai
"""

import os
import requests
import json

def get_heroku_app_info():
    """Get Heroku app information"""
    try:
        # Get app name from environment or use default
        app_name = os.environ.get('HEROKU_APP_NAME', 'arbion-ai-trading')
        
        print(f"Heroku App: {app_name}")
        print(f"SSL Certificate: parasaurolophus-89788")
        
        return app_name
    except Exception as e:
        print(f"Error getting Heroku app info: {e}")
        return None

def check_heroku_domains():
    """Check current Heroku domain configuration"""
    print("\n=== Current Heroku Domain Configuration ===")
    print("According to your previous setup:")
    print("- Root domain: arbion.ai → fathomless-honeydew-zv6ene3xmo3rbgkjenzxyql4.herokudns.com")
    print("- WWW domain: www.arbion.ai → hidden-seahorse-r47usw41xjogji02um4hhrq2.herokudns.com")
    print("- SSL Certificate: parasaurolophus-89788")
    
    print("\n=== Issue Identified ===")
    print("✗ SSL certificate only covers www.arbion.ai")
    print("✗ Root domain arbion.ai is not covered by the certificate")
    print("✗ This causes 'unsafe' warning when accessing arbion.ai directly")

def generate_heroku_commands():
    """Generate Heroku CLI commands to fix SSL"""
    print("\n=== Heroku CLI Commands to Fix SSL ===")
    
    commands = [
        "# 1. Check current domains",
        "heroku domains --app arbion-ai-trading",
        "",
        "# 2. Check current SSL certificates", 
        "heroku certs --app arbion-ai-trading",
        "",
        "# 3. Remove the current SSL certificate",
        "heroku certs:remove parasaurolophus-89788 --app arbion-ai-trading",
        "",
        "# 4. Add a new SSL certificate that covers both domains",
        "heroku certs:auto:enable --app arbion-ai-trading",
        "",
        "# 5. Verify the new certificate covers both domains",
        "heroku certs --app arbion-ai-trading",
        "",
        "# 6. Check domain status",
        "heroku domains --app arbion-ai-trading"
    ]
    
    for cmd in commands:
        print(cmd)

def generate_dns_configuration():
    """Generate DNS configuration instructions"""
    print("\n=== DNS Configuration Instructions ===")
    
    print("In your DNS provider (where you bought arbion.ai), set these records:")
    print()
    print("CNAME Records:")
    print("- arbion.ai → fathomless-honeydew-zv6ene3xmo3rbgkjenzxyql4.herokudns.com")
    print("- www.arbion.ai → hidden-seahorse-r47usw41xjogji02um4hhrq2.herokudns.com")
    print()
    print("OR (Alternative - Single CNAME):")
    print("- arbion.ai → your-app-name.herokuapp.com")
    print("- www.arbion.ai → your-app-name.herokuapp.com")

def generate_flask_https_redirect():
    """Generate Flask HTTPS redirect configuration"""
    print("\n=== Flask HTTPS Redirect Configuration ===")
    
    flask_config = '''
# Add to your Flask app configuration (main.py or app.py)

from flask import Flask, request, redirect, url_for
import os

app = Flask(__name__)

@app.before_request
def force_https():
    """Force HTTPS in production"""
    if not request.is_secure and request.headers.get('X-Forwarded-Proto') != 'https':
        if os.environ.get('FLASK_ENV') == 'production':
            return redirect(request.url.replace('http://', 'https://'))

# Alternative: Use Flask-Talisman for comprehensive HTTPS enforcement
# pip install flask-talisman
# from flask_talisman import Talisman
# Talisman(app, force_https=True)
'''
    
    print(flask_config)

def main():
    """Main function to diagnose and fix SSL issues"""
    print("=== SSL Certificate Fix for arbion.ai ===")
    
    # Get Heroku app info
    app_name = get_heroku_app_info()
    
    # Check current domain configuration
    check_heroku_domains()
    
    # Generate Heroku commands
    generate_heroku_commands()
    
    # Generate DNS configuration
    generate_dns_configuration()
    
    # Generate Flask HTTPS redirect
    generate_flask_https_redirect()
    
    print("\n=== Summary of Actions Required ===")
    print("1. Run the Heroku CLI commands above to fix the SSL certificate")
    print("2. Update your DNS settings to use the correct CNAME records")
    print("3. Add HTTPS redirect to your Flask app (optional but recommended)")
    print("4. Wait 5-10 minutes for DNS propagation")
    print("5. Test both arbion.ai and www.arbion.ai")
    
    print("\n=== Expected Result ===")
    print("✓ Both arbion.ai and www.arbion.ai will show as secure (green lock)")
    print("✓ No more 'unsafe' warnings")
    print("✓ SSL certificate will cover both domains")

if __name__ == "__main__":
    main()