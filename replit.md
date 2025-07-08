# Arbion AI Trading Platform

## Overview

Arbion is a secure, AI-powered trading platform that enables users to connect their real brokerage APIs (Schwab, Coinbase), execute trades using natural language powered by OpenAI, and optionally automate trading strategies. The platform is built with Flask and PostgreSQL, featuring a role-based authentication system with superadmin, admin, and standard user tiers.

## System Architecture

### Frontend Architecture
- **Framework**: Server-side rendered HTML templates with Jinja2
- **Styling**: TailwindCSS with custom dark theme inspired by Coinbase Pro
- **JavaScript**: Vanilla JavaScript for interactive features
- **UI Components**: Feather icons for consistent iconography
- **Responsive Design**: Mobile-first approach with grid layouts

### Backend Architecture
- **Framework**: Flask with Blueprint-based modular structure
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: Flask-Login with role-based access control
- **Security**: Cryptography library for API credential encryption
- **Task Processing**: Celery with Redis for production, threading for development
- **API Integration**: Custom connectors for Coinbase Pro and Schwab APIs

### Data Storage Solutions
- **Primary Database**: PostgreSQL for user data, trades, and system logs
- **Encryption**: AES encryption for sensitive API credentials using Fernet
- **Session Management**: Flask sessions with secure cookie handling
- **Migration Support**: Flask-Migrate for database schema management

## Key Components

### Authentication System
- **User Model**: Supports three roles (superadmin, admin, standard)
- **Password Security**: Werkzeug password hashing
- **Session Management**: Flask-Login for user session handling
- **Access Control**: Decorator-based role validation

### API Credential Management
- **Secure Storage**: Encrypted credentials using PBKDF2 key derivation
- **Provider Support**: Coinbase Pro, Schwab, and OpenAI integrations
- **Connection Testing**: Built-in API connectivity validation
- **Credential Rotation**: Support for updating and testing credentials

### Trading Engine
- **Natural Language Processing**: OpenAI GPT-4 for trade instruction parsing
- **Multi-Platform Support**: Coinbase Pro for crypto, Schwab for stocks
- **Trade Execution**: Real-time order placement and management
- **Simulation Mode**: Safe testing environment for strategies

### Auto-Trading System
- **Strategy Support**: Wheel, Collar, and AI-driven strategies
- **Background Processing**: Celery tasks for automated execution
- **Risk Management**: Position sizing and stop-loss mechanisms
- **Monitoring**: Comprehensive logging and error handling

## Data Flow

### User Authentication Flow
1. User submits credentials via login form
2. Password hash verification using Werkzeug
3. Flask-Login session establishment
4. Role-based access control validation
5. Redirect to appropriate dashboard

### Trading Execution Flow
1. User enters natural language trading instruction
2. OpenAI API parses instruction into structured format
3. System validates user credentials and permissions
4. Trade execution via appropriate API connector
5. Trade record creation and user notification
6. Real-time status updates and logging

### Auto-Trading Flow
1. Background task scheduler initiates trading cycle
2. System retrieves enabled strategies and settings
3. Market data analysis and signal generation
4. Risk assessment and position sizing
5. Automated trade execution with monitoring
6. Results logging and user notifications

## External Dependencies

### Required APIs
- **OpenAI API**: GPT-4 for natural language processing
- **Coinbase API**: Cryptocurrency trading execution (OAuth2 with state validation)
- **Schwab API**: Stock and options trading execution

### Infrastructure Dependencies
- **PostgreSQL**: Primary database server
- **Redis**: Celery task queue (recommended)
- **Heroku Scheduler**: Alternative to Celery for background tasks

### Python Libraries
- **Flask**: Web framework and extensions
- **SQLAlchemy**: Database ORM
- **Cryptography**: Encryption utilities
- **Requests**: HTTP client for API calls
- **Celery**: Distributed task queue

## Deployment Strategy

### Environment Configuration
- **Development**: Local PostgreSQL with debug mode enabled
- **Production**: Heroku deployment with PostgreSQL add-on
- **Environment Variables**: Secure configuration management

### Security Considerations
- **API Credentials**: Encrypted storage with PBKDF2 key derivation
- **Session Security**: Secure cookie settings and CSRF protection
- **Database Security**: Connection pooling and prepared statements
- **HTTPS**: TLS encryption for all production traffic

### Monitoring and Logging
- **Application Logging**: Python logging with database persistence
- **System Monitoring**: Trade execution and error tracking
- **Performance Metrics**: Response times and API usage monitoring

## Changelog

Changelog:
- July 08, 2025. Initial setup
- July 08, 2025. Enhanced with advanced features:
  - Real-time market data integration using yfinance and CoinGecko APIs
  - Advanced risk management system with position sizing and trade validation
  - Comprehensive technical indicators (RSI, MACD, SMA, Bollinger Bands)
  - Enhanced auto-trading engine with improved option chain processing
  - Background task scheduler for automated system maintenance
  - New API endpoints for market data, risk analysis, and portfolio management
  - Enhanced dashboard with live market data and technical indicators
  - Improved AI trading with comprehensive market analysis integration
  - Schwab OAuth2 integration with PKCE for secure authentication
  - Coinbase OAuth2 integration with secure state validation
  - Enhanced API settings interface with OAuth2 and legacy key support
  - Comprehensive test suite showing 71.4% success rate on core features
- July 08, 2025. Production deployment configuration completed:
  - Fixed Heroku H14 deployment error with proper Procfile configuration
  - Implemented Celery worker support for background task processing
  - Created WSGI entry point (wsgi.py) for production deployment
  - Added Heroku release script for database migrations and setup
  - Updated scheduler to support both Celery (production) and threading (development)
  - Added Redis dependency for Celery task queue
  - Complete production-ready OAuth2 system with encrypted token storage
  - Fixed PostgreSQL dialect compatibility for newer SQLAlchemy versions
  - Added custom domain setup documentation and scripts for arbion.ai

## User Preferences

Preferred communication style: Simple, everyday language.

## Deployment Information

### Custom Domain Configuration
- **Root Domain**: arbion.ai → fathomless-honeydew-zv6ene3xmo3rbgkjenzxyql4.herokudns.com
- **WWW Subdomain**: www.arbion.ai → hidden-seahorse-r47usw41xjogji02um4hhrq2.herokudns.com
- **SSL Certificate**: parasaurolophus-89788
- **Status**: Ready for DNS configuration