from dotenv import load_dotenv
import os

# Load environment variables before importing app
load_dotenv()

from app import create_app
from flask import request, redirect
import os

# Create application instance
app = create_app()

@app.before_request
def force_https():
    """Force HTTPS in production"""
    if not request.is_secure and request.headers.get('X-Forwarded-Proto') != 'https':
        if os.environ.get('FLASK_ENV') == 'production' or request.host.endswith('.herokuapp.com'):
            return redirect(request.url.replace('http://', 'https://'))

@app.before_request
def redirect_to_www():
    """Redirect root domain to www for SSL compatibility"""
    if request.host == 'arbion.ai':
        return redirect(f'https://www.arbion.ai{request.path}', code=301)

if __name__ == '__main__':
    # Set up environment for development
    os.environ.setdefault('FLASK_ENV', 'development')
    os.environ.setdefault('FLASK_DEBUG', '1')
    
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)
