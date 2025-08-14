# Arbion AI Trading Platform

## Overview
Arbion is a secure, AI-powered trading platform designed to enable users to connect their real brokerage APIs, execute trades using natural language, and optionally automate trading strategies. The platform aims to provide a comprehensive solution for both manual and automated trading, featuring real-time market data, advanced risk management, and a robust multi-user architecture. Its business vision is to democratize sophisticated trading tools, offering market potential in both retail and institutional trading sectors by providing a secure, reliable, and intelligent platform.

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
- **Authentication**: Flask-Login with role-based access control and Werkzeug password hashing.
- **Security**: AES encryption using Fernet for sensitive API credentials, secure cookie handling for sessions, and comprehensive OAuth2 security hardening (state parameter validation, rate limiting, secure redirect URI validation, session timestamp validation, RFC 6749, RFC 6750, RFC 7636 compliance).
- **Task Processing**: Celery with Redis for production, threading for development, for automated trading and background tasks.
- **API Integration**: Custom connectors for Coinbase, Schwab, E-trade, and OpenAI APIs, designed for multi-user, per-user credential management with intelligent rate limiting, retry logic, and connection health monitoring.

### Key Features
- **API Credential Management**: Secure, encrypted storage of API credentials per user, supporting connection testing and credential rotation.
- **Trading Engine**: OpenAI GPT-4 for natural language instruction parsing, multi-platform trade execution, and a simulation mode for strategy testing. Supports function calling, multi-model support (GPT-4 Omni, O1-Preview), and streaming conversational interfaces.
- **Auto-Trading System**: Supports various strategies (Wheel, Collar, AI-driven) with Celery for background execution, risk management (position sizing, stop-loss), and comprehensive logging.
- **Real-time Data System**: Real-time fetching and display of account balances and market data from connected APIs, with continuous updates without page refresh.
- **Comprehensive Market Coverage**: Integration with a ComprehensiveMarketDataProvider covering a vast range of stock symbols across major global exchanges and market sectors.
- **AI-Powered Agents**: Integration for intelligent agents that autonomously analyze markets using OpenAI, execute trades through Smart Accounts, manage multi-network portfolios, and run sophisticated trading strategies with built-in risk management and 24/7 operation capabilities.
- **Enhanced Coinbase v2 Integration**: Complete Wallet API v2 implementation with Smart Accounts (EIP-4337), transaction batching, gas sponsorship, multi-network support (Base, Ethereum, Arbitrum, Optimism, Polygon, BNB, Avalanche, Solana), token swaps, and TEE-secured private key management.
- **AI Trading Bot**: Advanced AI-powered trading bot using OpenAI GPT-4 for autonomous market analysis, signal generation, and trading decisions with sophisticated risk management, paper trading mode, and multi-symbol monitoring.

## External Dependencies

### Required APIs
- **OpenAI API**: GPT-4 for natural language processing, and Codex for code editing.
- **Coinbase API**: Cryptocurrency trading execution with dual API support - v1 OAuth2 for standard operations and v2 Wallet API with Smart Accounts, transaction batching, gas sponsorship, and multi-network support.
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