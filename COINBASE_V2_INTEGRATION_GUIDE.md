# Coinbase Wallet API v2 Enhanced Integration Guide

## Overview

This guide documents the comprehensive integration of Coinbase Wallet API v2 features into the Arbion AI Trading Platform. The v2 integration provides advanced blockchain capabilities including Smart Accounts, transaction batching, gas sponsorship, and multi-network support.

## 🚀 New Features Integrated

### **Core v2 Capabilities**

✅ **Multi-Network Account Management**
- EVM accounts compatible across all EVM chains
- Solana account support for SOL and SPL tokens
- Base, Ethereum, Arbitrum, Optimism, Polygon, BNB, Avalanche support
- Cross-chain asset management

✅ **Smart Accounts (EIP-4337)**
- Account abstraction with smart contract-based accounts
- Gas sponsorship capabilities (free on Base Sepolia)
- Transaction batching in single user operations
- Spend permissions and access control
- Deterministic addresses using CREATE2

✅ **Enhanced Transaction Capabilities**
- Standard EVM transactions with automatic signing
- User operations for Smart Accounts
- Batch transaction execution
- Gas estimation and optimization
- Transaction status monitoring

✅ **Trading and Swaps**
- Real-time swap quotes across supported networks
- One-click swap execution
- DeFi integration capabilities
- Competitive price discovery

✅ **Security and Authentication**
- Secure private key management in AWS Nitro Enclave TEE
- Rotatable wallet secrets
- Message signing for authentication
- Multi-user credential isolation

## 📁 File Structure

```
Arbion Platform/
├── utils/
│   ├── coinbase_v2_client.py         # Enhanced v2 API client
│   ├── coinbase_v2_routes.py         # Flask routes for v2 features
│   ├── coinbase_oauth.py             # Existing OAuth integration
│   └── real_time_data.py             # Updated with v2 support
├── coinbase_v2_integration_example.py # Comprehensive demo
├── COINBASE_V2_INTEGRATION_GUIDE.md  # This guide
└── app.py                            # Updated with v2 blueprint registration
```

## 🔧 API Endpoints Added

### Account Management
- `POST /api/coinbase-v2/accounts/create-evm` - Create EVM account
- `POST /api/coinbase-v2/accounts/create-smart` - Create Smart Account
- `POST /api/coinbase-v2/accounts/create-solana` - Create Solana account
- `GET /api/coinbase-v2/accounts` - List all accounts
- `GET /api/coinbase-v2/accounts/<address>/balance` - Get account balance

### Transaction Operations
- `POST /api/coinbase-v2/transactions/send` - Send EVM transaction
- `POST /api/coinbase-v2/user-operations/send` - Send user operation
- `POST /api/coinbase-v2/transactions/batch` - Batch transactions
- `POST /api/coinbase-v2/transactions/sponsor` - Gas sponsored transactions
- `GET /api/coinbase-v2/transactions/<hash>/wait` - Wait for confirmation

### Trading and Swaps
- `GET /api/coinbase-v2/swaps/quote` - Get swap quote
- `POST /api/coinbase-v2/swaps/execute` - Execute swap

### Network Utilities
- `GET /api/coinbase-v2/networks` - List supported networks
- `GET /api/coinbase-v2/networks/<network>/fees` - Get network fees
- `POST /api/coinbase-v2/estimate-gas` - Estimate transaction gas

### Security and Utilities
- `POST /api/coinbase-v2/sign-message` - Sign messages
- `POST /api/coinbase-v2/faucet/request` - Request testnet tokens
- `GET /api/coinbase-v2/status` - API health status
- `POST /api/coinbase-v2/wallet-secret/rotate` - Rotate wallet secret

## 🔐 Credential Management

### Required Credentials

1. **CDP API Key ID** - Your Coinbase Developer Platform API key identifier
2. **CDP API Key Secret** - Your API key secret for authentication
3. **CDP Wallet Secret** - Single secret for all wallet operations
4. **Access Token** - OAuth2 access token (optional)

### Setup Process

1. **Create CDP Account**
   ```
   Visit: https://portal.cdp.coinbase.com/
   Create account and verify email
   Navigate to API Keys section
   Generate new API key pair
   ```

2. **Generate Wallet Secret**
   ```
   Go to Server Wallet section
   Create new wallet
   Copy the wallet secret (store securely)
   ```

3. **Save Credentials in Arbion**
   ```python
   POST /api/coinbase-v2/save-credentials
   {
     "api_key_id": "your_api_key_id",
     "api_key_secret": "your_api_key_secret", 
     "wallet_secret": "your_wallet_secret",
     "access_token": "optional_oauth_token"
   }
   ```

## 💻 Usage Examples

### Create and Fund Smart Account

```python
from utils.coinbase_v2_client import CoinbaseV2Client

# Initialize client
client = CoinbaseV2Client(user_id="your_user_id")

# Create EVM account as owner
evm_account = client.create_evm_account(network="base-sepolia")
owner_address = evm_account['address']

# Create Smart Account
smart_account = client.create_smart_account(owner_address, network="base-sepolia")
smart_address = smart_account['address']

# Fund with testnet ETH
faucet_result = client.request_faucet(smart_address, network="base-sepolia")
```

### Batch Multiple Transactions

```python
# Define multiple transactions
transactions = [
    {
        "to": "0x1234567890123456789012345678901234567890",
        "value": "1000000000000000000",  # 1 ETH in wei
        "data": "0x"
    },
    {
        "to": "0x0987654321098765432109876543210987654321", 
        "value": "500000000000000000",   # 0.5 ETH in wei
        "data": "0x"
    }
]

# Execute all transactions in single user operation
batch_result = client.batch_transactions(
    smart_account_address=smart_address,
    transactions=transactions,
    network="base-sepolia"
)
```

### Execute Token Swap

```python
# Get swap quote
quote = client.get_swap_quote(
    from_asset="ETH",
    to_asset="USDC",
    amount="1.0",
    network="base-mainnet"
)

# Execute the swap
if quote.get('quote_id'):
    swap_result = client.execute_swap(
        from_address=owner_address,
        quote_id=quote['quote_id'],
        network="base-mainnet"
    )
```

## 🌐 Multi-Network Support

### Supported Networks

**EVM Networks:**
- `base-sepolia` (testnet) - Free gas sponsorship
- `base-mainnet` (mainnet)
- `ethereum-sepolia` (testnet)
- `ethereum-mainnet` (mainnet)
- `arbitrum-sepolia` (testnet)
- `arbitrum-mainnet` (mainnet)
- `optimism-sepolia` (testnet)
- `optimism-mainnet` (mainnet)
- `polygon-mumbai` (testnet)
- `polygon-mainnet` (mainnet)

**Solana Networks:**
- `solana-devnet` (testnet)
- `solana-mainnet` (mainnet)

### Network-Specific Features

| Network | Smart Accounts | Gas Sponsorship | Faucet |
|---------|---------------|----------------|---------|
| Base Sepolia | ✅ | ✅ (Free) | ✅ |
| Base Mainnet | ✅ | ✅ (Paid) | ❌ |
| Ethereum | ✅ | ✅ (Paid) | ✅ |
| Arbitrum | ✅ | ✅ (Paid) | ❌ |
| Optimism | ✅ | ✅ (Paid) | ❌ |
| Polygon | ✅ | ✅ (Paid) | ❌ |
| Solana | ❌ | ✅ (Sponsored) | ✅ |

## 🔄 Integration with Existing Features

### Real-Time Data Enhancement

The `RealTimeDataFetcher` has been updated to use v2 API:

```python
# Enhanced balance fetching with v2 support
def get_live_coinbase_balance(self, access_token=None, user_id=None):
    # Tries v2 API first, falls back to v1
    # Supports multi-network balance aggregation
    # Returns enhanced data with network information
```

### OAuth2 Integration

Existing OAuth2 flow remains compatible:
- v1 OAuth2 tokens work with v2 client
- Enhanced scopes for additional permissions
- Backward compatibility maintained

### Multi-User Architecture

Full integration with Arbion's user system:
- Per-user credential isolation
- Encrypted credential storage
- User-specific wallet management
- Role-based access control maintained

## 🛡️ Security Features

### Enhanced Security Model

1. **Trusted Execution Environment (TEE)**
   - Private keys secured in AWS Nitro Enclave
   - Keys never exposed to Coinbase or external systems
   - Hardware-level security guarantees

2. **Credential Management**
   - AES encryption for all stored credentials
   - Rotatable wallet secrets
   - Secure credential isolation per user

3. **Access Control**
   - Single secret manages all accounts
   - Granular permission controls
   - Audit logging for all operations

4. **Network Security**
   - HTTPS-only communication
   - Request signing and validation
   - Rate limiting and error handling

## 🚨 Error Handling and Diagnostics

### Comprehensive Error Management

```python
# Built-in connection testing
connection_result = client.test_connection()
if not connection_result['success']:
    # Handle connection failure
    print(f"Connection failed: {connection_result['error']}")

# API status monitoring  
api_status = client.get_api_status()
print(f"API Status: {api_status['status']}")

# Transaction monitoring
tx_result = client.wait_for_transaction(tx_hash, timeout=300)
if tx_result['status'] == 'failed':
    # Handle transaction failure
    print(f"Transaction failed: {tx_result['error']}")
```

### Fallback Mechanisms

- Automatic fallback from v2 to v1 API
- Retry logic for failed requests
- Graceful degradation on network issues
- Comprehensive logging for diagnostics

## 📊 Production Deployment

### Environment Variables

```bash
# Coinbase v2 API Configuration
CDP_API_KEY_ID=your_api_key_id
CDP_API_KEY_SECRET=your_api_key_secret  
CDP_WALLET_SECRET=your_wallet_secret

# Existing environment variables remain unchanged
COINBASE_CLIENT_ID=your_oauth_client_id
COINBASE_CLIENT_SECRET=your_oauth_client_secret
```

### Database Migration

No database changes required - uses existing `APICredential` model:

```python
# Existing table structure supports v2 credentials
APICredential:
  - user_id
  - provider ('coinbase_v2')
  - encrypted_credentials (JSON with v2 keys)
  - is_active
  - created_at/updated_at
```

### Testing Checklist

- [ ] v2 credentials configured
- [ ] Account creation on testnet works
- [ ] Smart Account deployment successful
- [ ] Batch transactions execute correctly
- [ ] Gas sponsorship functioning (Base Sepolia)
- [ ] Swap quotes retrieving successfully
- [ ] Multi-network support verified
- [ ] Fallback to v1 API working
- [ ] Error handling comprehensive
- [ ] Security audit passed

## 📈 Performance Optimizations

### Efficient Operations

1. **Connection Pooling** - Reuse HTTP connections
2. **Batch Operations** - Combine multiple transactions
3. **Async Support** - Non-blocking transaction waiting
4. **Caching** - Cache network data and fees
5. **Smart Retry** - Intelligent retry logic

### Resource Management

- Minimal memory footprint
- Efficient credential storage
- Optimized API calls
- Smart rate limit handling

## 🔮 Future Enhancements

### Planned Features

1. **Advanced Smart Contract Interactions**
   - Custom contract deployment
   - DeFi protocol integrations
   - NFT minting and trading

2. **Enhanced Trading Features**
   - Automated trading strategies
   - Portfolio rebalancing
   - Advanced order types

3. **Cross-Chain Operations**
   - Bridge transactions
   - Multi-chain arbitrage
   - Cross-chain asset management

4. **Analytics and Reporting**
   - Transaction analytics
   - Performance metrics
   - Cost optimization reports

## 📞 Support and Resources

### Documentation Links

- [Coinbase Developer Platform](https://docs.cdp.coinbase.com/)
- [Wallet API v2 Documentation](https://docs.cdp.coinbase.com/wallet-api/v2/introduction/welcome)
- [Smart Accounts Guide](https://docs.cdp.coinbase.com/wallet-api/v2/evm-features/smart-accounts)
- [Gas Sponsorship](https://docs.cdp.coinbase.com/wallet-api/v2/evm-features/gas-sponsorship)

### Community Support

- [CDP Discord](https://discord.com/invite/cdp) - #wallet-api channel
- [GitHub Issues](https://github.com/coinbase/cdp-sdk/issues)
- [Stack Overflow](https://stackoverflow.com/questions/tagged/coinbase-api)

### Integration Support

For Arbion-specific integration questions:
- Check `coinbase_v2_integration_example.py` for complete examples
- Review error logs in application for diagnostics
- Test connection using `/api/coinbase-v2/test-connection` endpoint

## ✅ Conclusion

The Coinbase Wallet API v2 integration brings cutting-edge blockchain capabilities to the Arbion platform:

- **Enhanced User Experience** - Multi-network support and gas sponsorship
- **Advanced Features** - Smart Accounts with account abstraction
- **Improved Security** - TEE-based key management and credential isolation  
- **Better Performance** - Transaction batching and optimized operations
- **Future-Proof** - Latest blockchain standards and protocols

The integration maintains full backward compatibility while providing access to the most advanced Coinbase API features available.