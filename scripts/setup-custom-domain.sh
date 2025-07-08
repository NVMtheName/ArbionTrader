#!/bin/bash

# Setup script for custom domain configuration on Heroku
# Usage: ./scripts/setup-custom-domain.sh [app-name]

APP_NAME=${1:-"your-app-name"}
DOMAIN="arbion.ai"

echo "Setting up custom domain for $DOMAIN on Heroku app: $APP_NAME"

# Add custom domains to Heroku app
echo "Adding custom domains..."
heroku domains:add $DOMAIN --app $APP_NAME
heroku domains:add www.$DOMAIN --app $APP_NAME

# Get DNS targets
echo "Getting DNS targets..."
heroku domains --app $APP_NAME

echo ""
echo "========================================="
echo "NEXT STEPS:"
echo "========================================="
echo "1. Configure DNS records for $DOMAIN:"
echo "   - Root domain ($DOMAIN): Add ALIAS/ANAME record"
echo "   - WWW subdomain (www.$DOMAIN): Add CNAME record"
echo "   - Use the DNS targets shown above"
echo ""
echo "2. SSL certificates will be automatically provisioned"
echo "   Check status with: heroku certs --app $APP_NAME"
echo ""
echo "3. DNS propagation may take 24-48 hours"
echo "   Test with: nslookup $DOMAIN"
echo ""
echo "4. Test HTTPS access: https://$DOMAIN"
echo "========================================="