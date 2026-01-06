# Trading Algorithm Strategies Implementation

This document describes the three automated trading strategies implemented in ArbionTrader.

## Overview

The platform now supports three fully-integrated trading strategies that can be enabled/disabled individually:

1. **Wheel Strategy** - Options income generation through cash-secured puts and covered calls
2. **Collar Strategy** - Portfolio protection using protective puts and covered calls
3. **AI Strategy** - AI-powered trading decisions using OpenAI's GPT-4

## Architecture

### Core Components

#### 1. Options Trading Utilities (`utils/options_trading.py`)

A comprehensive module providing:
- **OptionsCalculator**: Calculates option prices and Greeks (Delta) using simplified Black-Scholes
- **WheelStrategy**: Implements wheel strategy logic with strike selection and premium calculations
- **CollarStrategy**: Implements collar strategy with risk/reward analysis
- **AIStrategyHelper**: Market analysis and position sizing for AI-driven trades

#### 2. Auto Trading Engine (`tasks/auto_trading_tasks.py`)

Enhanced with full strategy implementations:
- Multi-user support for all strategies
- Real options pricing and Greeks calculations
- OpenAI API integration for intelligent trading
- Comprehensive execution logging and trade records

## Strategy Details

### 1. Wheel Strategy

**How it Works:**
The wheel strategy generates income by systematically selling options:
1. Sell cash-secured puts on quality stocks
2. If assigned, own the stock and sell covered calls
3. If called away, restart with cash-secured puts

**Implementation Features:**
- Target delta selection (default: 0.30 for 30-delta options)
- Days to expiration (default: 30 days)
- Automatic strike price calculation
- Premium collection tracking
- Annualized return calculations

**Example Trade Details:**
```json
{
  "strategy": "cash_secured_put",
  "symbol": "AAPL",
  "stock_price": 175.00,
  "strike": 166.25,
  "delta": -0.30,
  "premium": 2.50,
  "premium_collected": 250.00,
  "cash_required": 16625.00,
  "annualized_return": 18.2,
  "days_to_expiration": 30
}
```

**Watchlist:**
- AAPL, MSFT, GOOGL, TSLA, NVDA

### 2. Collar Strategy

**How it Works:**
The collar protects existing stock positions:
1. Buy protective put (downside protection)
2. Sell covered call (finance the put)
3. Creates a protected price range

**Implementation Features:**
- Customizable put delta (default: 0.20) for protection level
- Customizable call delta (default: 0.30) for upside cap
- Net debit/credit calculation
- Risk/reward ratio analysis
- Max loss and max gain calculations

**Example Trade Details:**
```json
{
  "strategy": "collar",
  "symbol": "SPY",
  "stock_price": 450.00,
  "put_strike": 427.50,
  "call_strike": 467.50,
  "net_cost": -50.00,
  "net_debit_credit": "CREDIT",
  "protected_range": "$427.50 - $467.50",
  "max_loss": 2200.00,
  "max_gain": 1800.00,
  "risk_reward_ratio": 0.82
}
```

**Watchlist:**
- SPY, QQQ, IWM (ETFs commonly held for protection)

### 3. AI Strategy

**How it Works:**
Uses OpenAI's GPT-4 to make intelligent trading decisions:
1. Analyzes current market conditions
2. Generates AI-powered trading recommendations
3. Evaluates confidence levels
4. Executes trades meeting confidence threshold (≥70%)

**Implementation Features:**
- Real-time market analysis
- Trend detection (bullish, bearish, neutral)
- Volume signal analysis
- Momentum scoring
- AI-generated reasoning for each trade
- Confidence-based execution filtering

**Example Trade Details:**
```json
{
  "strategy": "ai_driven",
  "symbol": "NVDA",
  "stock_price": 480.00,
  "action": "BUY",
  "confidence": 0.85,
  "quantity": 10,
  "trend": "bullish",
  "momentum_score": 0.15,
  "ai_reasoning": "Strong momentum with high volume support"
}
```

**Watchlist:**
- AAPL, GOOGL, MSFT, NVDA, TSLA

**OpenAI Integration:**
- Uses GPT-4 for analysis
- Parses natural language trading prompts
- Generates structured trading recommendations
- Requires valid OpenAI API key per user

## Configuration

### Enabling/Disabling Strategies

Strategies can be toggled via the Auto-Trading page (`/auto_trading`):

1. **Master Switch**: Enable/disable entire auto-trading system
2. **Simulation Mode**: Test strategies without real trades
3. **Individual Strategy Toggles**:
   - Wheel Strategy
   - Collar Strategy
   - AI Strategy

### Database Settings

The `AutoTradingSettings` table stores configuration:
```python
{
  'is_enabled': True/False,
  'simulation_mode': True/False,
  'wheel_enabled': True/False,
  'collar_enabled': True/False,
  'ai_enabled': True/False,
  'last_run': datetime
}
```

## Options Pricing Model

### Simplified Black-Scholes Implementation

The system uses a simplified options pricing model suitable for simulation:

**Call Option Price:**
```
intrinsic_value = max(0, stock_price - strike)
time_premium = stock_price × volatility × sqrt(time_to_expiration)
call_price = intrinsic_value + time_premium
```

**Put Option Price:**
```
intrinsic_value = max(0, strike - stock_price)
time_premium = stock_price × volatility × sqrt(time_to_expiration)
put_price = intrinsic_value + time_premium
```

**Delta Calculation:**
- Call delta: 0.05 to 0.95 (based on moneyness)
- Put delta: -0.95 to -0.05 (based on moneyness)
- Adjusts based on strike relative to stock price

### Strike Selection

The system finds optimal strikes for target deltas:

1. Start at ATM (at-the-money)
2. Iterate in 1% increments
3. Calculate delta for each strike
4. Select strike closest to target delta
5. Maximum 20% OTM (out-of-the-money)

## Trade Execution Flow

### Wheel Strategy Flow

```
1. Get user's Schwab credentials
2. For each symbol in watchlist:
   a. Get current stock price
   b. Check if user owns shares
   c. If owns shares:
      - Calculate covered call details
      - Create covered call trade record
   d. If no shares:
      - Calculate cash-secured put details
      - Create CSP trade record
3. Log execution results
```

### Collar Strategy Flow

```
1. Get user's Schwab credentials
2. For each symbol in watchlist:
   a. Get current stock price
   b. Check if user owns shares (required)
   c. If owns shares:
      - Calculate protective put details
      - Calculate covered call details
      - Create both trade records (collar)
   d. If no shares, skip symbol
3. Log execution results
```

### AI Strategy Flow

```
1. Get user's OpenAI credentials
2. Test OpenAI API connection
3. For each symbol in watchlist:
   a. Get current market data
   b. Analyze with AI helper
   c. Request OpenAI recommendation
   d. Parse AI response
   e. If confidence ≥ 70%:
      - Create AI-driven trade record
4. Log execution results
```

## Multi-User Support

All strategies support multiple users:
- Isolated trade execution per user
- Per-user credential management
- User-specific API keys (Schwab, OpenAI)
- Individual trade history tracking

## Risk Management

### Position Limits
- Wheel: Maximum 5 concurrent positions
- Collar: Limited to owned stock positions
- AI: Confidence threshold filtering (70%+)

### Safety Features
- Simulation mode for testing
- Trade validation before execution
- Error handling and logging
- Per-user credential isolation

## Trade Recording

All trades are recorded in the `Trade` table with:
- User ID
- Provider (schwab, coinbase, openai)
- Symbol
- Side (buy/sell)
- Quantity
- Price
- Trade type (covered_call, cash_secured_put, etc.)
- Strategy (wheel, collar, ai)
- Status (pending, executed, failed)
- Simulation flag
- Detailed execution JSON

### Execution Details JSON

Each trade includes comprehensive details:
```json
{
  "strategy_type": "cash_secured_put",
  "stock_price": 175.00,
  "strike": 166.25,
  "delta": -0.30,
  "premium": 2.50,
  "premium_collected": 250.00,
  "expiration_date": "2026-02-05",
  "days_to_expiration": 30,
  "annualized_return": 18.2,
  "cash_required": 16625.00,
  "breakeven": 163.75,
  "max_profit": 250.00
}
```

## System Logs

All strategy activities are logged to `SystemLog` table:
- Strategy start/completion
- Trade executions
- Errors and warnings
- User-specific events

## Testing

### Test Script

Run `test_trading_strategies.py` to verify:
- Strategy initialization
- Trade execution
- Multi-user isolation
- Toggle functionality
- Simulation mode

### Manual Testing

1. Enable simulation mode
2. Enable individual strategies
3. Check trade history
4. Verify execution details
5. Review system logs

## Production Considerations

### Before Going Live

1. **Replace Simulated Data:**
   - Implement real market data API
   - Connect to actual broker APIs
   - Remove `_get_simulated_stock_price()`
   - Implement real portfolio checking

2. **Add Real Broker Integration:**
   - Schwab order placement
   - Coinbase order placement
   - Order status tracking
   - Position management

3. **Enhance Risk Management:**
   - Account balance checking
   - Position size limits
   - Daily loss limits
   - Margin requirement calculations

4. **Add Monitoring:**
   - Real-time trade monitoring
   - Alert system for failures
   - Performance analytics
   - Risk exposure tracking

## API Requirements

### Required API Keys

1. **Schwab API** (wheel & collar strategies):
   - For options trading
   - Account management
   - Market data

2. **OpenAI API** (AI strategy):
   - GPT-4 access required
   - Usage tracking
   - Rate limit management

3. **Coinbase API** (optional):
   - For crypto trading
   - Multi-asset portfolios

## Future Enhancements

### Potential Improvements

1. **Advanced Options Pricing:**
   - Full Black-Scholes implementation
   - IV (Implied Volatility) tracking
   - Greeks monitoring (Gamma, Theta, Vega)

2. **Strategy Customization:**
   - User-defined parameters
   - Custom watchlists
   - Risk tolerance settings

3. **Performance Analytics:**
   - Strategy backtesting
   - P&L tracking
   - Sharpe ratio calculation
   - Win rate analysis

4. **Enhanced AI Features:**
   - Multi-model ensemble
   - Sentiment analysis
   - News integration
   - Technical indicator analysis

5. **Additional Strategies:**
   - Iron Condor
   - Butterfly Spreads
   - Straddles/Strangles
   - Credit/Debit Spreads

## Support and Documentation

### Key Files

- `tasks/auto_trading_tasks.py` - Main trading engine
- `utils/options_trading.py` - Options calculations
- `utils/openai_trader.py` - OpenAI integration
- `templates/auto_trading.html` - UI controls
- `routes.py` - Toggle endpoints

### Configuration

Settings stored in database, managed through web UI at `/auto_trading` endpoint.

### Troubleshooting

1. **Strategies not executing:**
   - Check master switch is enabled
   - Verify simulation mode setting
   - Confirm API credentials
   - Review system logs

2. **AI strategy failing:**
   - Verify OpenAI API key
   - Check API quota/billing
   - Review rate limits
   - Check internet connectivity

3. **No trades generated:**
   - Verify user has credentials
   - Check watchlist symbols
   - Review confidence thresholds
   - Inspect execution logs

---

**Version:** 1.0
**Last Updated:** 2026-01-06
**Author:** Claude (Anthropic AI)
