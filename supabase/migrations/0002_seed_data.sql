-- 0002_seed_data.sql
-- Seed data for development/testing

-- Insert default risk presets (referenced by frontend)
-- These are applied via the /api/v1/risk/preset endpoint

-- Default whitelist for new users (applied in backend on profile creation)
-- BTC, ETH, SOL, TON

-- Engine A default thresholds (can be overridden per user via profile)
-- engine_a_price_threshold = 0.02 (2%)
-- engine_a_volume_threshold = 3.0 (3x)
-- engine_a_spread_bps = 10
-- engine_a_funding_flip = true
-- engine_a_min_confidence = 0.70

-- Engine B defaults
-- engine_b_enabled = true
-- engine_b_min_confidence = 0.65

-- ============================================
-- Helper function for creating test user
-- ============================================

-- This is for local development only
-- In production, users are created via Telegram auth

INSERT INTO profiles (
    telegram_id, 
    username, 
    first_name, 
    risk_level, 
    max_allocation_pct, 
    max_concurrent_trades, 
    trading_mode, 
    bot_enabled,
    engine_a_enabled,
    engine_a_price_threshold,
    engine_a_volume_threshold,
    engine_a_spread_bps,
    engine_a_funding_flip,
    engine_a_min_confidence,
    engine_b_enabled,
    engine_b_min_confidence
) VALUES (
    123456789,  -- Replace with your Telegram ID
    'testuser',
    'Test',
    'medium',
    10.0,
    3,
    'paper',
    false,
    true,
    0.02,
    3.0,
    10,
    true,
    0.70,
    true,
    0.65
) ON CONFLICT (telegram_id) DO NOTHING;

-- Default whitelist for test user
INSERT INTO user_whitelist (profile_id, symbol, exchange, timeframe, active)
SELECT id, 'BTC', 'bybit', '1m', true FROM profiles WHERE telegram_id = 123456789
ON CONFLICT DO NOTHING;

INSERT INTO user_whitelist (profile_id, symbol, exchange, timeframe, active)
SELECT id, 'ETH', 'bybit', '1m', true FROM profiles WHERE telegram_id = 123456789
ON CONFLICT DO NOTHING;

INSERT INTO user_whitelist (profile_id, symbol, exchange, timeframe, active)
SELECT id, 'SOL', 'bybit', '1m', true FROM profiles WHERE telegram_id = 123456789
ON CONFLICT DO NOTHING;

INSERT INTO user_whitelist (profile_id, symbol, exchange, timeframe, active)
SELECT id, 'TON', 'bybit', '1m', true FROM profiles WHERE telegram_id = 123456789
ON CONFLICT DO NOTHING;

-- Default risk settings for test user
INSERT INTO risk_settings (profile_id, stop_loss_pct, take_profit_pct, trailing_stop_pct, max_allocation_pct, max_concurrent_trades, max_daily_drawdown_pct, whitelist_only)
SELECT id, 3.0, 6.0, 1.0, 10.0, 3, 5.0, true FROM profiles WHERE telegram_id = 123456789
ON CONFLICT (profile_id) DO NOTHING;

-- Paper balance for test user
INSERT INTO paper_balances (profile_id, asset, balance)
SELECT id, 'USDT', 10000.00 FROM profiles WHERE telegram_id = 123456789
ON CONFLICT (profile_id, asset) DO NOTHING;

-- ============================================
-- Mock signals for UI testing (global, no profile_id)
-- ============================================

INSERT INTO signals (
    engine, ticker, category, badge, source, metric, analysis, confidence, action_label,
    sentiment_score, mentions_per_hour, liquidity_usd
) VALUES 
('A', '$BTC', 'Blue Chip', 'INSTITUTIONAL', 'Kronos Forecast', 'Technical Breakout', 'Kronos: 85% Bullish - Strong momentum above 4h EMA', 85, 'ACTIVATE AGENT FOR $BTC', NULL, NULL, NULL),
('A', '$ETH', 'Blue Chip', 'TRENDING', 'Kronos Forecast', 'EMA Crossover', 'Kronos: 78% Bullish - Golden cross forming on 1h', 78, 'ACTIVATE AGENT FOR $ETH', NULL, NULL, NULL),
('A', '$SOL', 'Ecosystem Core', 'HIGH VOLATILITY', 'Kronos Forecast', 'Volume Spike', 'Kronos: 82% Bullish - 5x volume on breakout', 82, 'ACTIVATE AGENT FOR $SOL', NULL, NULL, NULL),
('A', '$TON', 'Ecosystem Core', 'INSTITUTIONAL', 'Kronos Forecast', 'Funding Flip', 'Kronos: 74% Neutral-Up - Funding turned positive', 74, 'ACTIVATE AGENT FOR $TON', NULL, NULL, NULL),

('B', '$WIF', 'Solana Memecoin', 'HIGH VOLATILITY', 'r/solana', '42/hr mentions', 'Social: 82% Bullish - Viral on Twitter + Reddit', 82, 'ACTIVATE AGENT FOR $WIF', 0.82, 42, 2500000),
('B', '$BONK', 'Solana Memecoin', 'HIGH VOLATILITY', 'Twitter', '1.2k/hr mentions', 'Social: 75% Bullish - Trending on CT', 75, 'ACTIVATE AGENT FOR $BONK', 0.75, 1200, 1800000),
('B', '$PEPE', 'Ethereum Memecoin', 'TRENDING', 'Reddit', '890/hr mentions', 'Social: 71% Bullish - Whale accumulation detected', 71, 'ACTIVATE AGENT FOR $PEPE', 0.71, 890, 3200000),
('B', '$DOGE', 'Major Memecoin', 'MACRO', 'RSS (CoinDesk)', 'Elon tweet', 'Social: 68% Bullish - Macro catalyst', 68, 'ACTIVATE AGENT FOR $DOGE', 0.68, 2100, 5000000)
ON CONFLICT DO NOTHING;