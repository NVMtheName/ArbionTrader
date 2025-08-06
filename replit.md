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