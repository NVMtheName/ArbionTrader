#!/bin/bash
# Heroku Environment Variable Setup Script
# Run this to configure encryption keys on Heroku

# Replace 'your-app-name' with your actual Heroku app name
APP_NAME="your-app-name"

echo "Setting encryption environment variables on Heroku..."

# Option 1: ENCRYPTION_KEY (Recommended - Most Secure)
heroku config:set ENCRYPTION_KEY="6JT4wJnzgG8izcQj4Iq8MpLfbndVrPTHD3rshOZDn1o=" --app $APP_NAME

# ENCRYPTION_SALT (Required if using ENCRYPTION_SECRET instead of ENCRYPTION_KEY)
heroku config:set ENCRYPTION_SALT="79d6ea9554bbe4dab7030440e3c03ca0" --app $APP_NAME

# SESSION_SECRET (Required for Flask sessions)
heroku config:set SESSION_SECRET="UyR2zVGKXStUVUdLRjphMcPxUCA3LYslKQBlYiD9BD0" --app $APP_NAME

# Optional: Set superadmin credentials
heroku config:set SUPERADMIN_EMAIL="admin@yourdomain.com" --app $APP_NAME
heroku config:set SUPERADMIN_PASSWORD="your-secure-password-here" --app $APP_NAME

echo "✅ Environment variables set successfully!"
echo "Restarting app..."
heroku restart --app $APP_NAME

echo "Check app logs:"
echo "heroku logs --tail --app $APP_NAME"
