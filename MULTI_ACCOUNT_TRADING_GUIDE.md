# Multi-Account AI Trading Bot Guide

## Overview

This guide describes the enhanced AI Trading Bot that can apply trading strategies across all connected API accounts simultaneously. The bot now supports multi-broker execution across Schwab, Coinbase, and E-trade accounts, enabling unified portfolio management and strategy deployment.

## 🌐 Multi-Account Features

### **Unified Strategy Execution**
- Apply single trading strategy across all connected broker accounts
- Synchronized signal generation and execution timing
- Cross-platform position sizing and risk management
- Unified performance tracking across all accounts

### **Multi-Broker Support**
- **Schwab Accounts**: Stock and options trading with real-time execution
- **Coinbase Accounts**: Cryptocurrency trading with smart asset mapping
- **E-trade Accounts**: Additional stock and options coverage (future implementation)

### **Intelligent Asset Mapping**
- Automatic conversion of stock signals to crypto equivalents
- Smart symbol mapping (AAPL → BTC, GOOGL → ETH, etc.)
- Cross-asset portfolio optimization and risk distribution

### **Consolidated Risk Management**
- Portfolio-wide risk controls across all accounts
- Account-specific position sizing based on account balance
- Unified stop-loss and take-profit management
- Cross-platform exposure monitoring

## 🔧 Enhanced API Endpoints

### Multi-Account Management
- `GET /api/ai-trading-bot/accounts` - Get all connected broker accounts
- `POST /api/ai-trading-bot/execute/<symbol>` - Execute signal across all accounts
- `POST /api/ai-trading-bot/cycle` - Run complete multi-account trading cycle

### Account-Specific Operations
- Each trading signal now executes across all connected accounts automatically
- Results include per-broker execution details and success rates
- Unified reporting of multi-account trading performance

## 🚀 Multi-Account Trading Flow

### 1. Connection Initialization
```python
# Initialize connections to all brokers
init_result = await bot.initialize_connections()

# Results include all broker connections
{
    'schwab': {'connected': True, 'accounts': 1},
    'coinbase': {'connected': True, 'accounts': 2}, 
    'etrade': {'connected': False, 'accounts': 0}
}
```

### 2. Signal Generation
```python
# Generate trading signal (same as before)
signal = await bot.generate_trading_signal('AAPL')
```

### 3. Multi-Account Execution
```python
# Execute across all connected accounts
execution_result = await bot.execute_trading_signal(signal)

# Results show per-broker execution
{
    'total_accounts': 3,
    'successful_executions': 2,
    'failed_executions': 1,
    'broker_results': {
        'schwab': [{'account': '123456', 'success': True}],
        'coinbase': [{'account': 'crypto_wallet', 'success': True}]
    }
}
```

## 💡 Smart Asset Mapping

### Stock-to-Crypto Mapping
```python
stock_to_crypto_map = {
    'AAPL': 'BTC',   # Tech leader → Bitcoin
    'GOOGL': 'ETH',  # Tech innovation → Ethereum
    'MSFT': 'ETH',   # Cloud/AI → Ethereum
    'TSLA': 'BTC',   # High volatility → Bitcoin
    'NVDA': 'ETH',   # AI/GPU → Ethereum
    'AMZN': 'BTC',   # Large cap → Bitcoin
    'META': 'ETH',   # Social/VR → Ethereum
    'NFLX': 'BTC'    # Growth stock → Bitcoin
}
```

### Cross-Asset Signal Conversion
- Automatically converts stock signals to appropriate crypto signals
- Adjusts position sizing for different asset classes
- Maintains risk profile across asset types
- Reduces confidence slightly for cross-asset trades

## 📊 Multi-Account Performance Tracking

### Enhanced Status Reporting
```python
status = bot.get_bot_status()

# Includes multi-account statistics
{
    'multi_account_stats': {
        'connected_accounts': {
            'schwab': [{'account_number': '123456'}],
            'coinbase': [{'name': 'Main Wallet'}]
        },
        'total_connected_accounts': 2,
        'multi_account_trades': 15,
        'total_account_executions': 28,
        'average_accounts_per_trade': 1.87
    }
}
```

### Trading Cycle Results
```python
cycle_results = await bot.run_trading_cycle()

# Enhanced with multi-account metrics
{
    'multi_account_executions': 5,
    'total_accounts_used': 12,
    'broker_breakdown': {
        'schwab': {'signals': 5, 'executions': 4},
        'coinbase': {'signals': 3, 'executions': 3}
    },
    'success_rate': 0.85,
    'multi_account_coverage': 2.4
}
```

## 🛡️ Enhanced Risk Management

### Account-Specific Risk Controls
```python
# Risk management now considers all accounts
class MultiAccountRiskManager:
    def calculate_position_size(self, signal, account_info):
        """Calculate position size per account"""
        account_balance = account_info['balance']
        risk_per_account = self.max_portfolio_risk / total_accounts
        
        return min(
            account_balance * risk_per_account,
            self.max_position_size
        )
    
    def validate_cross_platform_exposure(self, symbol):
        """Check total exposure across all platforms"""
        total_exposure = 0
        for broker in ['schwab', 'coinbase']:
            exposure = self.get_symbol_exposure(broker, symbol)
            total_exposure += exposure
        
        return total_exposure < self.max_symbol_exposure
```

### Portfolio-Wide Limits
- Maximum total exposure per symbol across all accounts
- Portfolio-wide daily trade limits
- Cross-platform position correlation monitoring
- Unified stop-loss and profit-taking across accounts

## 🌐 Configuration Examples

### Multi-Account Bot Configuration
```python
config = {
    'trading_strategy': 'ai_momentum',
    'multi_account_mode': True,
    'cross_asset_mapping': True,
    'account_allocation': {
        'schwab': 0.6,      # 60% of signals
        'coinbase': 0.4,    # 40% of signals
        'etrade': 0.0       # Not connected
    },
    'risk_distribution': 'equal',  # 'equal', 'proportional', 'custom'
    'max_accounts_per_trade': 5,
    'require_minimum_accounts': 1
}
```

### Account-Specific Settings
```python
account_configs = {
    'schwab': {
        'preferred_order_type': 'LIMIT',
        'max_position_size': 10000,
        'enable_options': True
    },
    'coinbase': {
        'preferred_order_type': 'MARKET',
        'max_position_size': 5000,
        'enable_staking': True
    }
}
```

## 📈 Usage Examples

### Start Multi-Account Bot
```bash
curl -X POST "http://localhost:5000/api/ai-trading-bot/start" \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "config": {
      "multi_account_mode": true,
      "cross_asset_mapping": true,
      "max_accounts_per_trade": 3
    }
  }'
```

### Get Connected Accounts
```bash
curl -X GET "http://localhost:5000/api/ai-trading-bot/accounts" \
  -H "Authorization: Bearer your-token"
```

### Execute Multi-Account Signal
```bash
curl -X POST "http://localhost:5000/api/ai-trading-bot/execute/AAPL" \
  -H "Authorization: Bearer your-token"
```

### Run Multi-Account Trading Cycle
```bash
curl -X POST "http://localhost:5000/api/ai-trading-bot/cycle" \
  -H "Authorization: Bearer your-token"
```

## 🔄 Integration Architecture

### Multi-Broker Manager
```python
class MultiAccountAITradingBot:
    def __init__(self, user_id):
        # Initialize all broker managers
        self.schwab_manager = create_schwabdev_manager(user_id)
        self.coinbase_manager = CoinbaseV2Manager(user_id)
        self.etrade_manager = EtradeManager(user_id)  # Future
        
        # Track connected accounts
        self.connected_accounts = {
            'schwab': [],
            'coinbase': [],
            'etrade': []
        }
    
    async def execute_multi_account_strategy(self, strategy):
        """Execute strategy across all accounts"""
        results = {}
        
        for broker, accounts in self.connected_accounts.items():
            broker_results = []
            for account in accounts:
                result = await self.execute_on_account(
                    broker, account, strategy
                )
                broker_results.append(result)
            results[broker] = broker_results
        
        return results
```

### Cross-Platform Signal Processing
```python
async def process_signal_for_platform(self, signal, platform):
    """Adapt signal for specific trading platform"""
    if platform == 'schwab':
        return self.prepare_schwab_order(signal)
    elif platform == 'coinbase':
        crypto_signal = await self.convert_to_crypto(signal)
        return self.prepare_coinbase_order(crypto_signal)
    elif platform == 'etrade':
        return self.prepare_etrade_order(signal)
```

## 🎯 Benefits of Multi-Account Trading

### Diversification Advantages
- **Risk Distribution**: Spread risk across multiple brokers and asset classes
- **Platform Redundancy**: Continue trading if one platform has issues
- **Regulatory Compliance**: Maintain separate accounts for different purposes

### Execution Benefits
- **Better Fill Rates**: Execute across multiple venues simultaneously
- **Cost Optimization**: Use most cost-effective platform per trade
- **Feature Access**: Leverage unique features of each platform

### Portfolio Management
- **Unified Strategy**: Apply consistent strategy across all accounts
- **Consolidated Reporting**: Single view of all trading activity
- **Cross-Platform Analytics**: Comprehensive performance analysis

## ⚠️ Important Considerations

### Risk Management
- Monitor total exposure across all accounts
- Set appropriate position limits per account
- Consider correlation between different asset classes
- Maintain emergency stop mechanisms for all platforms

### Compliance and Regulations
- Ensure compliance with regulations for each broker
- Maintain proper record-keeping across all accounts
- Consider tax implications of multi-account trading
- Follow pattern day trading rules where applicable

### Technical Considerations
- Network connectivity requirements for multiple APIs
- API rate limit management across platforms
- Error handling and recovery for each platform
- Data synchronization across different systems

## 🚀 Future Enhancements

### Additional Broker Support
- E-trade API integration completion
- Interactive Brokers support
- Robinhood API integration
- International broker support

### Advanced Features
- Cross-platform arbitrage detection
- Multi-account portfolio rebalancing
- Tax-loss harvesting across accounts
- Options strategies across platforms

### Analytics Enhancements
- Cross-platform performance attribution
- Risk-adjusted returns by broker
- Cost analysis per platform
- Execution quality metrics

The Multi-Account AI Trading Bot transforms your trading strategy from single-platform execution to a comprehensive multi-broker approach, maximizing diversification, execution quality, and risk management across your entire trading portfolio.