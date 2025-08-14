# Arbion AI Trading Platform

## Overview
Arbion is a secure, AI-powered trading platform designed to enable users to connect their real brokerage APIs (Schwab, Coinbase, E-trade), execute trades using natural language powered by OpenAI, and optionally automate trading strategies. The platform aims to provide a comprehensive solution for both manual and automated trading, featuring real-time market data, advanced risk management, and a robust multi-user architecture. Its business vision is to democratize sophisticated trading tools, offering market potential in both retail and institutional trading sectors by providing a secure, reliable, and intelligent platform.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Framework**: Server-side rendered HTML templates with Jinja2.
- **Styling**: TailwindCSS with a custom dark theme inspired by Coinbase Pro, featuring responsive design with a mobile-first approach.
- **JavaScript**: Vanilla JavaScript for interactive features.
- **UI Components**: Feather icons for consistent iconography.

### Backend Architecture
- **Framework**: Flask with a Blueprint-based modular structure.
- **Database**: PostgreSQL with SQLAlchemy ORM, managed with Flask-Migrate.
- **Authentication**: Flask-Login with role-based access control (superadmin, admin, standard user) and Werkzeug password hashing.
- **Security**: AES encryption using Fernet for sensitive API credentials (PBKDF2 key derivation), secure cookie handling for sessions, and comprehensive OAuth2 security hardening (state parameter validation, rate limiting, secure redirect URI validation, session timestamp validation).
- **Task Processing**: Celery with Redis for production, threading for development, for automated trading and background tasks.
- **API Integration**: Custom connectors for Coinbase, Schwab, E-trade, and OpenAI APIs, designed for multi-user, per-user credential management.

### Key Features
- **API Credential Management**: Secure, encrypted storage of API credentials per user, supporting connection testing and credential rotation.
- **Trading Engine**: OpenAI GPT-4 for natural language instruction parsing, multi-platform trade execution, and a simulation mode for strategy testing.
- **Auto-Trading System**: Supports various strategies (Wheel, Collar, AI-driven) with Celery for background execution, risk management (position sizing, stop-loss), and comprehensive logging.
- **Real-time Data System**: Real-time fetching and display of account balances and market data from connected APIs, with continuous updates without page refresh.
- **Comprehensive Market Coverage**: Integration with a ComprehensiveMarketDataProvider covering a vast range of stock symbols across major global exchanges and market sectors.
- **OpenAI Codex Integration**: Backend integration for AI-powered code editing and analysis, with REST API and CLI access.
- **Enhanced Coinbase v2 Integration**: Complete Wallet API v2 implementation with Smart Accounts (EIP-4337), transaction batching, gas sponsorship, multi-network support (Base, Ethereum, Arbitrum, Optimism, Polygon, BNB, Avalanche, Solana), token swaps, TEE-secured private key management, and advanced blockchain trading capabilities.
- **Autonomous AI Trading Agents**: Revolutionary Agent Kit integration creating intelligent agents that autonomously analyze markets using OpenAI, execute trades through Smart Accounts, manage multi-network portfolios, and run sophisticated trading strategies with built-in risk management and 24/7 operation capabilities.
- **Enhanced OpenAI Integration**: Comprehensive natural language processing system with function calling, multi-model support (GPT-4 Omni, O1-Preview), streaming conversational interfaces, advanced market analysis, AI-powered strategy generation, and intelligent risk assessment for seamless voice/text trading commands.

## External Dependencies

### Required APIs
- **OpenAI API**: GPT-4 for natural language processing, and Codex for code editing.
- **Coinbase API**: Cryptocurrency trading execution with dual API support - v1 OAuth2 for standard operations and v2 Wallet API with Smart Accounts, transaction batching, gas sponsorship, and multi-network support (EVM and Solana).
- **Schwab API**: Stock and options trading execution (OAuth2 with 3-legged flow and RFC 6750 Bearer Token compliance).
- **E-trade API**: Stock and options trading execution (OAuth 1.0a).
- **CoinGecko API**: For cryptocurrency price conversion.

### Infrastructure Dependencies
- **PostgreSQL**: Primary database server.
- **Redis**: For Celery task queue management.

### Python Libraries
- **Flask** and its extensions (Flask-Login, Flask-Migrate, Flask-SQLAlchemy).
- **SQLAlchemy**: ORM for database interactions.
- **Cryptography**: For encryption utilities.
- **Requests**: HTTP client for API calls.
- **Celery**: Distributed task queue.
- **Werkzeug**: For password hashing.

## Recent Major Updates

### Coinbase Wallet API v2 Integration (August 6, 2025)
- **MAJOR ENHANCEMENT**: Complete Coinbase Wallet API v2 integration with comprehensive blockchain capabilities
- **Smart Accounts**: Implemented EIP-4337 account abstraction with transaction batching and gas sponsorship
- **Multi-Network Support**: Full support for EVM chains (Base, Ethereum, Arbitrum, Optimism, Polygon) and Solana
- **Advanced Trading**: Token swaps, DeFi integration, automated trading bots, and programmable strategies
- **Enhanced Security**: TEE-based private key management, rotatable wallet secrets, and single secret authentication
- **Developer Features**: Comprehensive REST API, extensive documentation, and integration examples
- **Production Ready**: Full backward compatibility with v1 OAuth2, automatic fallback mechanisms, and enterprise-grade security

### Coinbase Agent Kit Integration (August 6, 2025)
- **REVOLUTIONARY**: Autonomous AI trading agents using Coinbase Agent Kit concepts integrated with OpenAI
- **AI-Powered Trading**: OpenAI GPT-4 integration for intelligent market analysis and autonomous trading decisions
- **Smart Agent Architecture**: CoinbaseAgentKit class with multi-user support, wallet management, and strategy execution
- **Autonomous Operations**: Agents can create wallets, analyze markets, execute trades, and manage portfolios without human intervention
- **Advanced Blockchain Integration**: Built on v2 API with Smart Accounts, transaction batching, and multi-network support
- **Specialized Agent Types**: General trader, DeFi farmer, arbitrage hunter, and risk manager agent configurations
- **Comprehensive API**: Complete Flask endpoints for agent creation, market analysis, trade execution, and strategy management
- **Risk Management**: Built-in confidence thresholds, position limits, stop-loss automation, and portfolio protection
- **Production Ready**: Full integration example, documentation, and demo showcasing autonomous trading capabilities

### Enhanced OpenAI API Integration (August 6, 2025)
- **COMPREHENSIVE**: Advanced natural language processing for sophisticated trading command interpretation
- **Function Calling**: Direct trading execution through AI decisions with execute_trade, analyze_market, manage_portfolio, and set_alerts functions
- **Multi-Model Support**: GPT-4 Omni for comprehensive analysis, GPT-4 Omni Mini for fast responses, O1-Preview for complex reasoning
- **Streaming Interface**: Real-time conversational trading with progressive response delivery and context awareness
- **Advanced Analysis**: Multi-dimensional market analysis combining technical, fundamental, and sentiment data
- **Strategy Generation**: AI-powered trading strategy creation with risk assessment and portfolio optimization
- **Natural Language Commands**: Process complex instructions like "Buy Tesla when it drops 5%" with full context understanding
- **Persistent Assistants**: Create trading assistants with personality customization and memory retention
- **Risk Assessment**: Intelligent confidence scoring and risk evaluation for all trading recommendations
- **Production Ready**: Complete Flask API, streaming support, and comprehensive documentation with demo capabilities

### OpenAI Authentication Enhancement (August 7, 2025)
- **BULLETPROOF CONNECTIONS**: Enhanced authentication manager with automatic retry logic and exponential backoff for mission-critical reliability
- **Intelligent Rate Limiting**: Dynamic request throttling and quota management to prevent API exhaustion with smart wait time calculation
- **Connection Health Monitoring**: Real-time connection status tracking, health checks, and automatic recovery mechanisms
- **Comprehensive Error Handling**: Advanced error categorization, recovery strategies, and user-friendly error messages with actionable solutions
- **Secure Credential Management**: API key validation, format checking, and environment variable security best practices
- **Production Architecture**: Thread-safe operations, async/sync client support, and enterprise-grade connection management
- **Diagnostic Capabilities**: Real-time monitoring, performance metrics, and comprehensive status reporting for troubleshooting
- **Setup Validation**: Automated configuration checking, setup guides, and troubleshooting assistance
- **Demo Integration**: Live authentication testing with successful API calls demonstrating robust connection reliability

### Schwabdev Integration (August 7, 2025)
- **COMPREHENSIVE SCHWAB API ACCESS**: Complete integration of Schwabdev library for seamless Charles Schwab brokerage connectivity
- **OAuth 2.0 Authentication**: Full OAuth flow implementation with automatic token management, refresh logic, and secure credential storage
- **Real-time Account Data**: Live account balances, positions, buying power, P&L tracking, and comprehensive portfolio management
- **Market Data Integration**: Real-time quotes, multi-symbol retrieval, OHLC data, bid/ask spreads, and volume information
- **Order Management System**: Complete order placement, tracking, cancellation with support for market, limit, stop orders and options strategies  
- **Portfolio & Watchlist Management**: Position tracking with P&L calculations, watchlist monitoring, and multi-account support
- **Advanced Token Management**: Intelligent token validation, automatic refresh 5 minutes before expiry, and connection health monitoring
- **Comprehensive Error Handling**: Detailed error categorization, recovery strategies, and actionable user guidance
- **Production Architecture**: Multi-user support, encrypted credential storage, thread-safe operations, and enterprise-grade reliability
- **12 API Endpoints**: Complete REST API for authentication, account data, market quotes, order management, and demo capabilities
- **Natural Language Integration**: Seamless integration with OpenAI for voice/text trading commands and automated strategy execution

### AI Trading Bot Implementation (August 7, 2025)
- **INTELLIGENT TRADING BOT**: Advanced AI-powered trading bot using OpenAI GPT-4 for autonomous market analysis and trading decisions
- **Comprehensive Market Analysis**: Real-time market analysis with sentiment scoring, trend detection, and technical indicator interpretation
- **Automated Signal Generation**: AI-generated trading signals with confidence levels, risk assessment, and detailed reasoning
- **Sophisticated Risk Management**: Position sizing, stop-loss automation, daily trade limits, and portfolio risk controls
- **Paper Trading Mode**: Risk-free strategy testing and optimization before live trading deployment
- **Multi-Symbol Monitoring**: Simultaneous analysis and trading across entire watchlists with intelligent prioritization
- **Performance Analytics**: Detailed tracking of trading performance, win rates, P&L, and strategy optimization metrics
- **12 AI Trading Endpoints**: Complete REST API for bot control, signal generation, analysis, execution, and performance monitoring
- **Advanced Configuration**: Customizable trading strategies, risk parameters, confidence thresholds, and execution settings
- **Multi-Account Execution**: Unified strategy application across all connected broker accounts (Schwab, Coinbase, E-trade)
- **Cross-Asset Intelligence**: Smart mapping between stocks and crypto with unified risk management across asset classes
- **Integration Architecture**: Seamless integration with OpenAI for intelligence and multi-broker execution in unified trading system

### Critical Application Fix (August 13, 2025)
- **APPLICATION RECOVERY**: Successfully resolved all 500 internal server errors affecting multiple pages and platform functionality
- **Git Merge Conflict Resolution**: Eliminated persistent Git merge conflict markers in app.py causing syntax errors and application crashes
- **Database Schema Enhancement**: Updated api_credential table with missing OAuth token columns (access_token, refresh_token, token_expiry)
- **Server Stability**: Restored Gunicorn worker process stability with clean startup and reload functionality
- **Blueprint Registration**: Fixed all trading system route imports and registrations for proper module loading
- **Multi-Account Trading Restored**: All trading bot functionality operational across connected broker accounts
- **Production Ready**: Platform now fully operational with no critical errors, ready for live trading operations
- **System Validation**: Confirmed scheduler, token maintenance, and all core systems functioning correctly