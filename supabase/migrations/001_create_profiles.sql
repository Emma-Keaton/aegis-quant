-- 001_create_profiles.sql
-- Creates the "profiles" table matching src/db/profiles.ts interface
CREATE TABLE IF NOT EXISTS profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  telegram_id BIGINT NOT NULL UNIQUE,
  username TEXT,
  first_name TEXT,
  last_name TEXT,
  language_code TEXT,
  wallet_connected BOOLEAN NOT NULL DEFAULT FALSE,
  wallet_address TEXT,
  wallet_network TEXT,
  wallet_public_key TEXT,
  risk_level TEXT NOT NULL DEFAULT 'CONSERVATIVE',
  max_allocation_pct NUMERIC NOT NULL DEFAULT 15,
  max_concurrent_trades INT NOT NULL DEFAULT 3,
  trading_mode TEXT NOT NULL CHECK (trading_mode IN ('paper','live')) DEFAULT 'paper',
  bot_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Trigger to update updated_at on row change
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ language plpgsql;

DROP TRIGGER IF EXISTS set_timestamp ON profiles;
CREATE TRIGGER set_timestamp BEFORE UPDATE ON profiles
FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
