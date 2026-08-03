-- 004_create_positions.sql
-- Table to store user positions referenced in server.ts
CREATE TABLE IF NOT EXISTS positions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
  symbol TEXT NOT NULL,
  size NUMERIC NOT NULL,
  entry_price NUMERIC NOT NULL,
  current_price NUMERIC NOT NULL,
  unrealized_pnl NUMERIC NOT NULL DEFAULT 0,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Update timestamp trigger for positions
DROP TRIGGER IF EXISTS set_timestamp ON positions;
CREATE TRIGGER set_timestamp BEFORE UPDATE ON positions
FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
