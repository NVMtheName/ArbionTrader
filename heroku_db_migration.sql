-- Heroku Database Migration Script
-- Run this on your Heroku PostgreSQL database to fix the missing columns

-- Add missing columns to trade table if they don't exist
ALTER TABLE trade ADD COLUMN IF NOT EXISTS is_simulation BOOLEAN DEFAULT false;
ALTER TABLE trade ADD COLUMN IF NOT EXISTS fees DECIMAL(15,8) DEFAULT 0.0;
ALTER TABLE trade ADD COLUMN IF NOT EXISTS commission DECIMAL(15,8) DEFAULT 0.0;
ALTER TABLE trade ADD COLUMN IF NOT EXISTS realized_pnl DECIMAL(15,8);
ALTER TABLE trade ADD COLUMN IF NOT EXISTS unrealized_pnl DECIMAL(15,8);
ALTER TABLE trade ADD COLUMN IF NOT EXISTS market_value DECIMAL(15,8);
ALTER TABLE trade ADD COLUMN IF NOT EXISTS cost_basis DECIMAL(15,8);
ALTER TABLE trade ADD COLUMN IF NOT EXISTS portfolio_percentage DECIMAL(15,8);
ALTER TABLE trade ADD COLUMN IF NOT EXISTS risk_score DECIMAL(15,8);
ALTER TABLE trade ADD COLUMN IF NOT EXISTS confidence_score DECIMAL(15,8);
ALTER TABLE trade ADD COLUMN IF NOT EXISTS exit_price DECIMAL(15,8);
ALTER TABLE trade ADD COLUMN IF NOT EXISTS exit_date TIMESTAMP;
ALTER TABLE trade ADD COLUMN IF NOT EXISTS holding_period_days INTEGER;
ALTER TABLE trade ADD COLUMN IF NOT EXISTS trade_notes TEXT;

-- Update data types to match SQLAlchemy models (Float -> DECIMAL for precision)
ALTER TABLE trade ALTER COLUMN quantity TYPE DECIMAL(15,8);
ALTER TABLE trade ALTER COLUMN price TYPE DECIMAL(15,8);
ALTER TABLE trade ALTER COLUMN amount TYPE DECIMAL(15,8);

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_trade_user_id ON trade(user_id);
CREATE INDEX IF NOT EXISTS idx_trade_symbol ON trade(symbol);
CREATE INDEX IF NOT EXISTS idx_trade_status ON trade(status);
CREATE INDEX IF NOT EXISTS idx_trade_created_at ON trade(created_at);
CREATE INDEX IF NOT EXISTS idx_trade_is_simulation ON trade(is_simulation);

-- Create missing tables if they don't exist
CREATE TABLE IF NOT EXISTS portfolio (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id),
    provider VARCHAR(50) NOT NULL,
    account_id VARCHAR(100),
    total_value DECIMAL(15,8) DEFAULT 0.0,
    cash_balance DECIMAL(15,8) DEFAULT 0.0,
    invested_amount DECIMAL(15,8) DEFAULT 0.0,
    total_pnl DECIMAL(15,8) DEFAULT 0.0,
    day_pnl DECIMAL(15,8) DEFAULT 0.0,
    total_return_pct DECIMAL(15,8) DEFAULT 0.0,
    day_return_pct DECIMAL(15,8) DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trade_analytics (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id),
    date DATE NOT NULL,
    trades_count INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    total_volume DECIMAL(15,8) DEFAULT 0.0,
    total_pnl DECIMAL(15,8) DEFAULT 0.0,
    realized_pnl DECIMAL(15,8) DEFAULT 0.0,
    unrealized_pnl DECIMAL(15,8) DEFAULT 0.0,
    win_rate DECIMAL(15,8) DEFAULT 0.0,
    avg_win DECIMAL(15,8) DEFAULT 0.0,
    avg_loss DECIMAL(15,8) DEFAULT 0.0,
    profit_factor DECIMAL(15,8) DEFAULT 0.0,
    sharpe_ratio DECIMAL(15,8) DEFAULT 0.0,
    max_drawdown DECIMAL(15,8) DEFAULT 0.0,
    manual_trades INTEGER DEFAULT 0,
    ai_trades INTEGER DEFAULT 0,
    wheel_trades INTEGER DEFAULT 0,
    collar_trades INTEGER DEFAULT 0,
    portfolio_beta DECIMAL(15,8) DEFAULT 0.0,
    volatility DECIMAL(15,8) DEFAULT 0.0,
    value_at_risk DECIMAL(15,8) DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS performance_benchmark (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id),
    benchmark_symbol VARCHAR(20) NOT NULL,
    period VARCHAR(20) NOT NULL,
    user_return DECIMAL(15,8) DEFAULT 0.0,
    benchmark_return DECIMAL(15,8) DEFAULT 0.0,
    alpha DECIMAL(15,8) DEFAULT 0.0,
    beta DECIMAL(15,8) DEFAULT 0.0,
    tracking_error DECIMAL(15,8) DEFAULT 0.0,
    information_ratio DECIMAL(15,8) DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Add indexes for new tables
CREATE INDEX IF NOT EXISTS idx_portfolio_user_id ON portfolio(user_id);
CREATE INDEX IF NOT EXISTS idx_trade_analytics_user_id ON trade_analytics(user_id);
CREATE INDEX IF NOT EXISTS idx_trade_analytics_date ON trade_analytics(date);
CREATE INDEX IF NOT EXISTS idx_performance_benchmark_user_id ON performance_benchmark(user_id);

COMMIT;