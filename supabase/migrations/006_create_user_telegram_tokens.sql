-- 006_create_user_telegram_tokens.sql
-- Table to store each user's Telegram access token for copy‑trade channel polling
CREATE TABLE IF NOT EXISTS user_telegram_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  telegram_token TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

DROP TRIGGER IF EXISTS set_timestamp ON user_telegram_tokens;
CREATE TRIGGER set_timestamp BEFORE UPDATE ON user_telegram_tokens
FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
