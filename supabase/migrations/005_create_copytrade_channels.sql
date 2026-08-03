-- 005_create_copytrade_channels.sql
-- Table to store copy‑trading channel subscriptions and confidence thresholds
CREATE TABLE IF NOT EXISTS copytrade_channels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel_id TEXT NOT NULL UNIQUE,
  confidence_threshold NUMERIC NOT NULL CHECK (confidence_threshold >= 0 AND confidence_threshold <= 100),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Reuse the timestamp trigger defined for other tables
DROP TRIGGER IF EXISTS set_timestamp ON copytrade_channels;
CREATE TRIGGER set_timestamp BEFORE UPDATE ON copytrade_channels
FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
