#!/bin/bash
# Start script for Arbion AI Trading Platform

set -e  # Exit on any error

echo "Starting Arbion AI Trading Platform..."

# Check if main.py exists
if [ ! -f "main.py" ]; then
    echo "Error: main.py not found!"
    exit 1
fi

# Check if app.py exists
if [ ! -f "app.py" ]; then
    echo "Error: app.py not found!"
    exit 1
fi

# Start the application
echo "Starting Flask application..."
if [ "$FLASK_ENV" = "development" ]; then
    echo "Running in development mode"
    python3 main.py
else
    echo "Running in production mode with gunicorn"
    gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
fi

exit 0