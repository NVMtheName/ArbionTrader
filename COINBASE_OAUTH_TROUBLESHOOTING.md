# Coinbase OAuth2 Troubleshooting Guide

## Problem: Token Exchange Failed with 401 Error

### Root Cause
The 401 error during token exchange is caused by a redirect URI mismatch between your Coinbase OAuth app configuration and the actual redirect URI being used by the application.

### Current DNS Issue
- **arbion.ai** (root domain): Points to wrong server, causing OAuth redirects to fail
- **www.arbion.ai** (www subdomain): Working correctly

### Immediate Solutions

#### Option 1: Fix DNS (Recommended)
1. **Add A Record in GoDaddy**
   - Record Type: A
   - Name: @ (root domain)
   - Value: 3.33.241.96
   - TTL: 600 (10 minutes)

2. **Wait for DNS Propagation**
   - Time: 15 minutes to 24 hours
   - Check progress: Use online DNS checker tools

3. **Verify Fix**
   - Test: Visit https://arbion.ai
   - Should redirect to correct Heroku app

#### Option 2: Use WWW Subdomain (Temporary)
1. **Update Coinbase OAuth App**
   - Go to Coinbase Cloud Console
   - Edit your OAuth app
   - Change redirect URI from:
     - `https://arbion.ai/oauth_callback/crypto`
   - To:
     - `https://www.arbion.ai/oauth_callback/crypto`

2. **Update Arbion Platform**
   - Go to API Settings
   - Coinbase OAuth2 section
   - Update redirect URI to use www.arbion.ai

### Common OAuth Error Messages

#### "Token exchange failed with status 401"
- **Cause**: Redirect URI mismatch
- **Solution**: Ensure redirect URI in Coinbase OAuth app matches exactly

#### "Missing state parameter"
- **Cause**: Session expired or browser didn't preserve state
- **Solution**: Start OAuth flow again

#### "Invalid state parameter"
- **Cause**: CSRF protection triggered
- **Solution**: Clear browser cache and start OAuth flow again

### Verification Steps

1. **Check Current Configuration**
   ```bash
   python debug_coinbase_oauth.py
   ```

2. **Test OAuth Flow**
   - Go to API Settings
   - Click "Authenticate with Coinbase OAuth2"
   - Should redirect to Coinbase
   - After authorization, should return to Arbion

3. **Verify Success**
   - Status should show "Connected"
   - Test API connection should work

### Technical Details

#### Expected Redirect URI Format
```
https://arbion.ai/oauth_callback/crypto
```

#### Coinbase OAuth2 Scopes Required
- `wallet:user:read`
- `wallet:accounts:read`
- `wallet:transactions:read`

#### OAuth2 Flow
1. User clicks "Authenticate with Coinbase"
2. Redirect to Coinbase with state parameter
3. User authorizes application
4. Coinbase redirects back with authorization code
5. Application exchanges code for access token
6. Tokens are encrypted and stored in database

### If Problems Persist

1. **Check Coinbase OAuth App Settings**
   - Verify redirect URI matches exactly
   - Ensure app is not in sandbox mode (unless intended)
   - Check that required scopes are enabled

2. **Check Browser Network Tab**
   - Look for 401 responses
   - Check redirect URI in actual requests
   - Verify state parameter consistency

3. **Enable Debug Logging**
   - OAuth callback logs all parameters
   - Check server logs for detailed error messages

### Contact Support

If none of these solutions work:
1. Check Coinbase OAuth app configuration
2. Verify your Coinbase account has OAuth2 permissions
3. Try creating a new OAuth app with correct redirect URI
4. Test with a simple redirect URI like `https://httpbin.org/get` to isolate the issue