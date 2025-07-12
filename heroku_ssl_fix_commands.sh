#!/bin/bash
# Heroku SSL Certificate Fix Commands for arbion.ai

echo "=== Heroku SSL Certificate Fix for arbion.ai ==="
echo

# Check current setup
echo "1. Checking current domains and certificates..."
echo "heroku domains --app arbion-ai-trading"
echo "heroku certs --app arbion-ai-trading"
echo

# The issue: Certificate only covers www.arbion.ai, not arbion.ai
echo "2. Current issue identified:"
echo "   - Certificate 'parasaurolophus-89788' only covers www.arbion.ai"
echo "   - Root domain arbion.ai is not included in certificate SAN"
echo

# Solution: Generate new certificate
echo "3. Fix: Generate new SSL certificate covering both domains"
echo

echo "Run these commands in your terminal:"
echo "=====================================";
echo

echo "# Step 1: Remove current certificate"
echo "heroku certs:remove parasaurolophus-89788 --app arbion-ai-trading"
echo

echo "# Step 2: Enable automatic SSL (will generate new certificate)"
echo "heroku certs:auto:enable --app arbion-ai-trading"
echo

echo "# Step 3: Wait for certificate generation (may take 5-10 minutes)"
echo "heroku certs:auto --app arbion-ai-trading"
echo

echo "# Step 4: Verify both domains are covered"
echo "heroku certs --app arbion-ai-trading"
echo

echo "# Step 5: Test SSL on both domains"
echo "curl -I https://arbion.ai"
echo "curl -I https://www.arbion.ai"
echo

echo "=== Alternative: Manual Certificate Upload ==="
echo "If automatic SSL doesn't work, you can:"
echo "1. Generate a certificate that covers both domains"
echo "2. Upload it manually:"
echo "   heroku certs:add server.crt server.key --app arbion-ai-trading"
echo

echo "=== Expected Result ==="
echo "- New SSL certificate will cover both arbion.ai and www.arbion.ai"
echo "- Both domains will show green lock in browsers"
echo "- No more 'unsafe' warnings"
echo

echo "=== If Problems Persist ==="
echo "Check DNS propagation (may take up to 24 hours):"
echo "- https://dnschecker.org"
echo "- https://www.whatsmydns.net"