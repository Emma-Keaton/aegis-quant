-- 003_create_user_whitelist.sql
-- Creates the "user_whitelist" table matching src/db/whitelist.ts interface
CREATE TABLE IF NOT EXISTS user_whitelist (
  profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
  symbol TEXT NOT NULL,
  exchange TEXT NOT NULL DEFAULT 'bybit',
  timeframe TEXT NOT NULL DEFAULT '1m',
  active BOOLEAN NOT NULL DEFAULT TRUE,
  added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  PRIMARY KEY (profile_id, symbol, exchange)
);
