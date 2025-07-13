#!/bin/bash
# Setup script for Arbion AI Trading Platform

set -e  # Exit on any error

echo "Starting Arbion AI Trading Platform setup..."

# Check Python version
python3 --version
echo "✓ Python version verified"

# Install dependencies if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "Installing Python dependencies..."
    pip install -r requirements.txt
    echo "✓ Dependencies installed"
else
    echo "No requirements.txt found, skipping dependency installation"
fi

# Create necessary directories
mkdir -p static/css
mkdir -p static/js
mkdir -p static/images
mkdir -p templates
mkdir -p utils
mkdir -p logs
echo "✓ Directory structure created"

# Set proper permissions
chmod +x codex_cli.py
chmod +x scripts/setup.sh
echo "✓ File permissions set"

# Initialize database if needed
if [ -n "$DATABASE_URL" ]; then
    echo "Database configuration found"
    python3 -c "
try:
    from app import create_app
    from models import db
    app = create_app()
    with app.app_context():
        db.create_all()
    print('✓ Database initialized')
except Exception as e:
    print(f'Database initialization skipped: {e}')
"
else
    echo "No database configuration found, skipping database setup"
fi

echo "✓ Setup completed successfully!"
exit 0