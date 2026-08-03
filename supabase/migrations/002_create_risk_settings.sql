-- 002_create_risk_settings.sql
-- Creates the "risk_settings" table matching src/db/risk.ts interface
CREATE TABLE IF NOT EXISTS risk_settings (
  profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
  stop_loss_pct NUMERIC NOT NULL DEFAULT 3.0,
  take_profit_pct NUMERIC NOT NULL DEFAULT 6.5,
  trailing_stop_pct NUMERIC NOT NULL DEFAULT 1.0,
  max_allocation_pct NUMERIC NOT NULL DEFAULT 15,
  max_concurrent_trades INT NOT NULL DEFAULT 3,
  max_daily_drawdown_pct NUMERIC NOT NULL DEFAULT 5,
  whitelist_only BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (profile_id)
);
