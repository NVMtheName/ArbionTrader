-- Migration: OAuth Token Lifecycle State Machine
-- Date: 2026-02-20
-- Description: Adds columns to api_credential for the token lifecycle state machine.
--   - credential_type: distinguishes API keys from OAuth tokens
--   - status: state machine (active, refreshing, reauth_required, error)
--   - last_error/last_error_at: stores the provider error for UI display
--   - last_refresh_at: when the token was last successfully refreshed
--   - consecutive_failures: retry counter for exponential backoff
--   - provider_user_id: provider's user ID for correlation
--   - token_type: bearer, etc.
--
-- IMPORTANT: All columns have defaults so this is safe to run on existing data.
-- Existing rows will get status='active', credential_type='oauth', consecutive_failures=0.
--
-- Run with: heroku pg:psql < migrations/oauth_token_lifecycle.sql
-- Or locally: psql $DATABASE_URL < migrations/oauth_token_lifecycle.sql

-- Credential type: oauth vs api_key
ALTER TABLE api_credential ADD COLUMN IF NOT EXISTS credential_type VARCHAR(20) DEFAULT 'oauth';

-- State machine: active, refreshing, reauth_required, error
ALTER TABLE api_credential ADD COLUMN IF NOT EXISTS status VARCHAR(30) DEFAULT 'active';

-- Last error message from provider (human-readable, for UI display)
ALTER TABLE api_credential ADD COLUMN IF NOT EXISTS last_error TEXT;

-- When the last error occurred
ALTER TABLE api_credential ADD COLUMN IF NOT EXISTS last_error_at TIMESTAMP;

-- When the token was last successfully refreshed
ALTER TABLE api_credential ADD COLUMN IF NOT EXISTS last_refresh_at TIMESTAMP;

-- Number of consecutive transient failures (reset on success)
ALTER TABLE api_credential ADD COLUMN IF NOT EXISTS consecutive_failures INTEGER DEFAULT 0;

-- Provider's user ID (for correlation / debugging)
ALTER TABLE api_credential ADD COLUMN IF NOT EXISTS provider_user_id VARCHAR(256);

-- Token type (bearer, etc.)
ALTER TABLE api_credential ADD COLUMN IF NOT EXISTS token_type VARCHAR(30);

-- Index for the maintenance query that filters by status
CREATE INDEX IF NOT EXISTS idx_api_credential_status ON api_credential (status);

-- Mark existing OpenAI credentials as api_key type (they don't use OAuth)
UPDATE api_credential SET credential_type = 'api_key' WHERE provider = 'openai' AND credential_type IS NULL;
UPDATE api_credential SET credential_type = 'api_key' WHERE provider = 'etrade' AND credential_type IS NULL;

-- Ensure all existing active credentials start with status='active'
UPDATE api_credential SET status = 'active' WHERE status IS NULL;
UPDATE api_credential SET consecutive_failures = 0 WHERE consecutive_failures IS NULL;
