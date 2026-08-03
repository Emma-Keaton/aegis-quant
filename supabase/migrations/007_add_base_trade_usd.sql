-- Add base_trade_usd column to risk_settings table
ALTER TABLE risk_settings ADD COLUMN base_trade_usd NUMERIC(5,2) NOT NULL DEFAULT 10.0;
