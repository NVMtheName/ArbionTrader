# Schwab Trader API Production Deployment Guide

## Overview

This guide covers the production deployment of the Schwab Trader API integration for the Arbion AI Trading Platform. The implementation includes a complete OAuth2 3-legged authentication flow, token management, and real-time account/balance fetching.

## Features Implemented

✅ **Complete OAuth2 3-Legged Flow**
- Authorization URL generation with state parameter
- Secure OAuth callback handling at `/oauth_callback/broker`
- Authorization code exchange for access/refresh tokens
- Automatic token refresh with 5-minute buffer

✅ **Production-Ready Token Management**
- Secure token storage in encrypted database
- Automatic token validation and refresh
- Integration with Arbion's multi-user architecture
- Persistent API connections for continuous trading

✅ **Comprehensive API Coverage**
- Account listing: `GET /trader/v1/accounts`
- Account balances: `GET /trader/v1/accounts/{accountHash}`
- Account positions: `GET /trader/v1/accounts/{accountHash}/positions`
- RFC 6750 Bearer Token authentication

✅ **Production Error Handling**
- 401 Unauthorized with automatic token refresh
- Comprehensive logging and audit trails
- OAuth2 RFC 6749 compliance
- Graceful fallback for expired credentials

## Environment Variables Required

```bash
# Schwab API Credentials
SCHWAB_CLIENT_ID=your_schwab_client_id
SCHWAB_CLIENT_SECRET=your_schwab_client_secret
SCHWAB_REDIRECT_URI=https://www.arbion.ai/oauth_callback/broker

# Flask Configuration
FLASK_SECRET_KEY=your_secure_random_key
```

## File Structure

```
Arbion Platform/
├── schwab_trader_api_production.py    # Standalone production script
├── utils/schwab_trader_client.py      # Integrated client for platform
├── routes.py                          # Updated with OAuth endpoints
├── utils/real_time_data.py           # Updated for new client
└── SCHWAB_PRODUCTION_DEPLOYMENT.md   # This guide
```

## API Endpoints Added

### OAuth2 Flow Endpoints

1. **Initiate OAuth** - `GET /oauth/schwab/initiate`
   - Generates authorization URL with state parameter
   - Stores state in session for security validation
   - Returns authorization URL for user redirection

2. **OAuth Callback** - `GET /oauth_callback/broker`
   - Handles Schwab OAuth2 callback
   - Validates state parameter (CSRF protection)
   - Exchanges authorization code for tokens
   - Stores encrypted tokens in database

### API Data Endpoints

3. **Get Accounts** - `GET /api/schwab-accounts`
   - Fetches all user accounts from Schwab API
   - Automatic token refresh if expired
   - Returns account numbers and metadata

4. **Get Balances** - `GET /api/schwab-balances`
   - Fetches account balances and cash positions
   - Optional account_hash parameter for specific account
   - Returns total account value and breakdown

5. **Get Positions** - `GET /api/schwab-positions`
   - Fetches current positions for specified account
   - Requires account_hash parameter
   - Returns holdings, quantities, and market values

## Integration with Existing Platform

### Multi-User Architecture
- Credentials stored per-user in `OAuthClientCredential` model
- User-specific token management and refresh
- Isolated API connections for each user

### Real-Time Data Integration
- Updated `RealTimeDataFetcher` to use new Schwab client
- Live balance updates every 10 seconds
- Account position tracking for portfolio display

### Security Features
- AES encryption for all stored credentials
- CSRF protection with state parameter validation
- Automatic token rotation and refresh
- Comprehensive audit logging

## Deployment Steps

### 1. Environment Setup
```bash
# Set Schwab API credentials
export SCHWAB_CLIENT_ID="your_client_id"
export SCHWAB_CLIENT_SECRET="your_client_secret"
export SCHWAB_REDIRECT_URI="https://www.arbion.ai/oauth_callback/broker"
```

### 2. Database Migration
The existing database models support the new OAuth2 flow:
- `APICredential` table stores encrypted tokens
- `OAuthClientCredential` table stores client credentials
- No migration required

### 3. Schwab Developer App Configuration
Configure your Schwab developer application:
- **Redirect URI**: `https://www.arbion.ai/oauth_callback/broker`
- **Scopes**: `api` (full API access)
- **Application Type**: Web Application
- **Grant Type**: Authorization Code

### 4. Testing the Integration

#### Test OAuth Flow:
```bash
# 1. Start OAuth flow
curl -X GET "https://www.arbion.ai/oauth/schwab/initiate" \
  -H "Authorization: Bearer {user_token}"

# 2. Complete OAuth in browser (authorization_url from step 1)
# 3. Callback handled automatically

# 4. Test API endpoints
curl -X GET "https://www.arbion.ai/api/schwab-accounts" \
  -H "Authorization: Bearer {user_token}"
```

#### Test Direct API Access:
```python
from utils.schwab_trader_client import SchwabTraderClient

# Initialize client
client = SchwabTraderClient(user_id="your_user_id")

# Test connection
result = client.test_connection()
print(f"Connection test: {result}")

# Fetch accounts
accounts = client.get_accounts()
print(f"Accounts: {accounts}")
```

## Production Monitoring

### Key Metrics to Monitor
- Token refresh success rate
- API response times
- Authentication failure rates
- Account balance fetch success

### Logging Points
- OAuth flow initiation and completion
- Token refresh operations
- API request success/failure
- Error conditions and retries

### Health Check Endpoints
- `GET /api/schwab-accounts` - Validates authentication
- Token refresh operations logged in application logs
- Connection test available via `SchwabTraderClient.test_connection()`

## Security Considerations

### Token Security
- All tokens encrypted at rest using AES encryption
- Tokens refreshed automatically before expiration
- No tokens exposed in logs or error messages
- Secure session management for OAuth state

### API Rate Limiting
- Schwab API rate limits handled automatically
- Exponential backoff for failed requests
- Connection pooling for efficiency

### Access Control
- User-specific credential isolation
- Role-based access control maintained
- Audit logging for all API operations

## Troubleshooting

### Common Issues

1. **Invalid Client Credentials**
   - Verify `SCHWAB_CLIENT_ID` and `SCHWAB_CLIENT_SECRET`
   - Ensure redirect URI matches Schwab app configuration

2. **Token Refresh Failures**
   - Check token expiration and refresh logic
   - Verify client credentials are still valid
   - Re-authenticate user if refresh token expired

3. **API Rate Limits**
   - Implement exponential backoff
   - Monitor API usage patterns
   - Consider caching frequently accessed data

### Debug Mode
Enable debug logging for detailed troubleshooting:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Production Checklist

- [ ] Environment variables configured
- [ ] Schwab developer app configured with correct redirect URI
- [ ] SSL certificate active for OAuth callback
- [ ] Database encryption keys secured
- [ ] Monitoring and alerting configured
- [ ] Error handling tested
- [ ] Token refresh flow verified
- [ ] Multi-user isolation confirmed

## Support Information

For technical support:
- Check application logs for detailed error information
- Verify Schwab API status at developer.schwab.com
- Review OAuth2 flow state and token status
- Test connection using provided diagnostic tools

This implementation provides a production-ready Schwab Trader API integration that meets enterprise security standards and supports the full Arbion platform architecture.