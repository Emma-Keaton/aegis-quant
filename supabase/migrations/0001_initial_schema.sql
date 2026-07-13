-- supabase/migrations/0001_initial_schema.sql
-- Complete database schema for Aegis Quant
-- Run this in Supabase SQL Editor

-- ============================================
-- EXTENSIONS
-- ============================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "timescaledb";
CREATE EXTENSION IF NOT EXISTS "pgvector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================
-- HELPER FUNCTIONS
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- ============================================
-- 1. PROFILES - Main user table (one per Telegram user)
-- ============================================
CREATE TABLE profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(100),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    language_code VARCHAR(10),
    
    -- Wallet
    wallet_connected BOOLEAN DEFAULT FALSE,
    wallet_address VARCHAR(100),
    wallet_network VARCHAR(20), -- 'ton' or 'evm'
    wallet_public_key TEXT,
    
    -- Trading Settings
    risk_level VARCHAR(20) DEFAULT 'medium' CHECK (risk_level IN ('conservative', 'medium', 'aggressive')),
    max_allocation_pct NUMERIC(5,2) DEFAULT 10.0 CHECK (max_allocation_pct >= 1.0 AND max_allocation_pct <= 100.0),
    max_concurrent_trades INT DEFAULT 3 CHECK (max_concurrent_trades >= 1 AND max_concurrent_trades <= 20),
    trading_mode VARCHAR(10) DEFAULT 'paper' CHECK (trading_mode IN ('paper', 'live')),
    bot_enabled BOOLEAN DEFAULT FALSE,
    
    -- Engine A Config
    engine_a_enabled BOOLEAN DEFAULT TRUE,
    engine_a_price_threshold NUMERIC(5,4) DEFAULT 0.0200,
    engine_a_volume_threshold NUMERIC(5,2) DEFAULT 3.00,
    engine_a_spread_bps INT DEFAULT 10,
    engine_a_funding_flip BOOLEAN DEFAULT TRUE,
    engine_a_min_confidence NUMERIC(3,2) DEFAULT 0.70,
    
    -- Engine B Config
    engine_b_enabled BOOLEAN DEFAULT TRUE,
    engine_b_min_confidence NUMERIC(3,2) DEFAULT 0.65,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_profiles_telegram_id ON profiles(telegram_id);
CREATE INDEX idx_profiles_bot_enabled ON profiles(bot_enabled) WHERE bot_enabled = TRUE;

-- Updated_at trigger
CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 2. USER_CREDENTIALS - Encrypted CEX API keys
-- ============================================
CREATE TABLE user_credentials (
    id BIGSERIAL PRIMARY KEY,
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    exchange VARCHAR(20) NOT NULL CHECK (exchange IN ('bybit', 'okx', 'binance', 'gateio', 'kucoin')),
    encrypted_api_key TEXT NOT NULL,
    encrypted_api_secret TEXT NOT NULL,
    encrypted_passphrase TEXT, -- Required for OKX
    is_active BOOLEAN DEFAULT TRUE,
    last_tested_at TIMESTAMPTZ,
    test_result JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(profile_id, exchange)
);

CREATE INDEX idx_user_credentials_profile_id ON user_credentials(profile_id);
CREATE INDEX idx_user_credentials_exchange ON user_credentials(exchange);
CREATE INDEX idx_user_credentials_active ON user_credentials(is_active) WHERE is_active = TRUE;

CREATE TRIGGER update_user_credentials_updated_at
    BEFORE UPDATE ON user_credentials
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 3. USER_WHITELIST - Engine A whitelist (CRUD from frontend)
-- ============================================
CREATE TABLE user_whitelist (
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(20) DEFAULT 'bybit' CHECK (exchange IN ('bybit', 'okx', 'binance', 'gateio', 'kucoin')),
    timeframe VARCHAR(10) DEFAULT '1m' CHECK (timeframe IN ('1m', '5m', '15m', '1h', '4h', '1d')),
    active BOOLEAN DEFAULT TRUE,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (profile_id, symbol, exchange)
);

CREATE INDEX idx_user_whitelist_profile_id ON user_whitelist(profile_id);
CREATE INDEX idx_user_whitelist_symbol ON user_whitelist(symbol);
CREATE INDEX idx_user_whitelist_active ON user_whitelist(active) WHERE active = TRUE;

-- ============================================
-- 4. RISK_SETTINGS - User risk management
-- ============================================
CREATE TABLE risk_settings (
    profile_id UUID PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
    stop_loss_pct NUMERIC(5,2) DEFAULT 3.00 CHECK (stop_loss_pct >= 0.10 AND stop_loss_pct <= 20.00),
    take_profit_pct NUMERIC(5,2) DEFAULT 6.00 CHECK (take_profit_pct >= 0.10 AND take_profit_pct <= 50.00),
    trailing_stop_pct NUMERIC(5,2) DEFAULT 1.00 CHECK (trailing_stop_pct >= 0.10 AND trailing_stop_pct <= 10.00),
    max_allocation_pct NUMERIC(5,2) DEFAULT 10.00 CHECK (max_allocation_pct >= 1.00 AND max_allocation_pct <= 50.00),
    max_concurrent_trades INT DEFAULT 3 CHECK (max_concurrent_trades >= 1 AND max_concurrent_trades <= 20),
    max_daily_drawdown_pct NUMERIC(5,2) DEFAULT 5.00 CHECK (max_daily_drawdown_pct >= 1.00 AND max_daily_drawdown_pct <= 20.00),
    whitelist_only BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TRIGGER update_risk_settings_updated_at
    BEFORE UPDATE ON risk_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 5. PAPER_BALANCES - Paper trading balances per asset
-- ============================================
CREATE TABLE paper_balances (
    id BIGSERIAL PRIMARY KEY,
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    asset VARCHAR(10) NOT NULL,
    balance NUMERIC(20,8) DEFAULT 0 NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(profile_id, asset)
);

CREATE INDEX idx_paper_balances_profile_id ON paper_balances(profile_id);

-- ============================================
-- 6. POSITIONS - Current open positions
-- ============================================
CREATE TYPE order_side AS ENUM ('buy', 'sell');
CREATE TYPE trade_mode AS ENUM ('paper', 'live');

CREATE TABLE positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    side order_side NOT NULL,
    size NUMERIC(20,8) NOT NULL,
    entry_price NUMERIC(20,8) NOT NULL,
    current_price NUMERIC(20,8) NOT NULL,
    unrealized_pnl NUMERIC(20,8) DEFAULT 0,
    stop_loss NUMERIC(20,8),
    take_profit NUMERIC(20,8),
    trailing_stop NUMERIC(20,8),
    leverage INT DEFAULT 1,
    mode trade_mode NOT NULL,
    opened_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_positions_profile_id ON positions(profile_id);
CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_mode ON positions(mode);

CREATE TRIGGER update_positions_updated_at
    BEFORE UPDATE ON positions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 7. TRADE_LOGS - Unified trade execution log (paper + live)
-- ============================================
CREATE TYPE order_status AS ENUM ('pending', 'filled', 'partial', 'cancelled', 'failed', 'rejected');
CREATE TYPE execution_type AS ENUM ('paper', 'live');

CREATE TABLE trade_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    side order_side NOT NULL,
    execution_type execution_type NOT NULL,
    size NUMERIC(20,8) NOT NULL,
    price NUMERIC(20,8) NOT NULL,
    total_value_usd NUMERIC(20,2) NOT NULL,
    status order_status DEFAULT 'pending',
    slippage NUMERIC(6,4) DEFAULT 0,
    commission NUMERIC(20,8) DEFAULT 0,
    tx_hash TEXT,
    order_id VARCHAR(50),
    error_message TEXT,
    executed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_trade_logs_profile_time ON trade_logs(profile_id, executed_at DESC);
CREATE INDEX idx_trade_logs_symbol ON trade_logs(symbol);
CREATE INDEX idx_trade_logs_execution_type ON trade_logs(execution_type);
CREATE INDEX idx_trade_logs_status ON trade_logs(status);

-- ============================================
-- 8. SIGNALS - Engine A/B signals with Kronos forecast
-- ============================================
CREATE TABLE signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id UUID REFERENCES profiles(id) ON DELETE SET NULL, -- NULL = global signal
    engine VARCHAR(1) NOT NULL CHECK (engine IN ('A', 'B')), -- 'A' = Technical, 'B' = Social
    ticker VARCHAR(20) NOT NULL,
    category VARCHAR(50),
    badge VARCHAR(50),
    source VARCHAR(100) NOT NULL,
    metric VARCHAR(100),
    analysis TEXT,
    confidence INT NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
    action_label VARCHAR(100),
    
    -- Engine A: Kronos forecast
    kronos_trajectories JSONB,
    kronos_mean_path JSONB,
    kronos_confidence_90 JSONB,
    
    -- Engine B: Social data
    sentiment_score NUMERIC(4,3),
    mentions_per_hour INT,
    liquidity_usd NUMERIC(20,2),
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_signals_engine_ticker_time ON signals(engine, ticker, created_at DESC);
CREATE INDEX idx_signals_profile_engine ON signals(profile_id, engine);
CREATE INDEX idx_signals_confidence ON signals(confidence DESC);

-- ============================================
-- 9. ALERT_RULES - User-defined alert rules
-- ============================================
CREATE TABLE alert_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    metric VARCHAR(100) NOT NULL,
    condition VARCHAR(20) NOT NULL CHECK (condition IN ('>', '<', '>=', '<=', '==', 'crosses_above', 'crosses_below')),
    value VARCHAR(50) NOT NULL,
    action VARCHAR(200) NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    triggered_at TIMESTAMPTZ,
    trigger_count INT DEFAULT 0
);

CREATE INDEX idx_alert_rules_profile_id ON alert_rules(profile_id);
CREATE INDEX idx_alert_rules_active ON alert_rules(active) WHERE active = TRUE;

-- ============================================
-- 10. EXECUTION_AUDIT - Immutable audit trail for every execution attempt
-- ============================================
CREATE TABLE execution_audit (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    mode trade_mode NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    side order_side NOT NULL,
    size NUMERIC(20,8) NOT NULL,
    price NUMERIC(20,8) NOT NULL,
    sl NUMERIC(20,8),
    tp NUMERIC(20,8),
    kronos_confidence INT,
    trigger_type VARCHAR(30) NOT NULL CHECK (trigger_type IN (
        'ws_price', 'ws_volume', 'ws_spread', 'ws_funding', 'scheduled', 'manual', 'social'
    )),
    status order_status NOT NULL,
    tx_hash TEXT,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_execution_audit_profile_time ON execution_audit(profile_id, created_at DESC);
CREATE INDEX idx_execution_audit_trigger ON execution_audit(trigger_type);
CREATE INDEX idx_execution_audit_status ON execution_audit(status);

-- ============================================
-- TIMESCALEDB HYPERTABLES (for high-volume time-series data)
-- ============================================

-- Market ticks (raw trades)
CREATE TABLE market_ticks (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    price NUMERIC(20,8) NOT NULL,
    volume NUMERIC(20,8) NOT NULL,
    side VARCHAR(4)
);
SELECT create_hypertable('market_ticks', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
CREATE INDEX idx_market_ticks_symbol_time ON market_ticks (symbol, time DESC);

-- Market candles (OHLCV)
CREATE TABLE market_candles (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    open NUMERIC(20,8) NOT NULL,
    high NUMERIC(20,8) NOT NULL,
    low NUMERIC(20,8) NOT NULL,
    close NUMERIC(20,8) NOT NULL,
    volume NUMERIC(20,8) NOT NULL
);
SELECT create_hypertable('market_candles', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
CREATE UNIQUE INDEX idx_market_candles_unique ON market_candles (symbol, exchange, timeframe, time);

-- Social signals (Engine B)
CREATE TABLE social_signals (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    source VARCHAR(50) NOT NULL,
    sentiment NUMERIC(4,3) NOT NULL,
    volume INT DEFAULT 0,
    metadata JSONB
);
SELECT create_hypertable('social_signals', 'time', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
CREATE INDEX idx_social_signals_symbol_time ON social_signals (symbol, time DESC);

-- ============================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_whitelist ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_balances ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE trade_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE alert_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE execution_audit ENABLE ROW LEVEL SECURITY;
-- TimescaleDB tables: RLS not needed (accessed via service_role)

-- Profiles policies
CREATE POLICY "Users can view own profile" ON profiles
    FOR SELECT USING (
        telegram_id::text = auth.uid()::text 
        OR auth.role() = 'service_role'
    );

CREATE POLICY "Users can update own profile" ON profiles
    FOR UPDATE USING (
        telegram_id::text = auth.uid()::text 
        OR auth.role() = 'service_role'
    );

CREATE POLICY "Service role full access profiles" ON profiles
    FOR ALL USING (auth.role() = 'service_role');

-- User credentials policies
CREATE POLICY "Users can view own credentials" ON user_credentials
    FOR SELECT USING (
        profile_id IN (SELECT id FROM profiles WHERE telegram_id::text = auth.uid()::text)
        OR auth.role() = 'service_role'
    );

CREATE POLICY "Users can manage own credentials" ON user_credentials
    FOR ALL USING (
        profile_id IN (SELECT id FROM profiles WHERE telegram_id::text = auth.uid()::text)
        OR auth.role() = 'service_role'
    );

-- Whitelist policies
CREATE POLICY "Users can view own whitelist" ON user_whitelist
    FOR SELECT USING (
        profile_id IN (SELECT id FROM profiles WHERE telegram_id::text = auth.uid()::text)
        OR auth.role() = 'service_role'
    );

CREATE POLICY "Users can manage own whitelist" ON user_whitelist
    FOR ALL USING (
        profile_id IN (SELECT id FROM profiles WHERE telegram_id::text = auth.uid()::text)
        OR auth.role() = 'service_role'
    );

-- Risk settings policies
CREATE POLICY "Users can view own risk settings" ON risk_settings
    FOR SELECT USING (
        profile_id IN (SELECT id FROM profiles WHERE telegram_id::text = auth.uid()::text)
        OR auth.role() = 'service_role'
    );

CREATE POLICY "Users can manage own risk settings" ON risk_settings
    FOR ALL USING (
        profile_id IN (SELECT id FROM profiles WHERE telegram_id::text = auth.uid()::text)
        OR auth.role() = 'service_role'
    );

-- Paper balances policies
CREATE POLICY "Users can view own paper balances" ON paper_balances
    FOR SELECT USING (
        profile_id IN (SELECT id FROM profiles WHERE telegram_id::text = auth.uid()::text)
        OR auth.role() = 'service_role'
    );

CREATE POLICY "Service role manage paper balances" ON paper_balances
    FOR ALL USING (auth.role() = 'service_role');

-- Positions policies
CREATE POLICY "Users can view own positions" ON positions
    FOR SELECT USING (
        profile_id IN (SELECT id FROM profiles WHERE telegram_id::text = auth.uid()::text)
        OR auth.role() = 'service_role'
    );

CREATE POLICY "Service role manage positions" ON positions
    FOR ALL USING (auth.role() = 'service_role');

-- Trade logs policies
CREATE POLICY "Users can view own trade logs" ON trade_logs
    FOR SELECT USING (
        profile_id IN (SELECT id FROM profiles WHERE telegram_id::text = auth.uid()::text)
        OR auth.role() = 'service_role'
    );

CREATE POLICY "Service role manage trade logs" ON trade_logs
    FOR ALL USING (auth.role() = 'service_role');

-- Signals policies (global signals visible to all, user-specific to owner)
CREATE POLICY "Global signals visible to authenticated" ON signals
    FOR SELECT USING (
        profile_id IS NULL 
        OR profile_id IN (SELECT id FROM profiles WHERE telegram_id::text = auth.uid()::text)
        OR auth.role() = 'service_role'
    );

CREATE POLICY "Service role manage signals" ON signals
    FOR ALL USING (auth.role() = 'service_role');

-- Alert rules policies
CREATE POLICY "Users can view own alert rules" ON alert_rules
    FOR SELECT USING (
        profile_id IN (SELECT id FROM profiles WHERE telegram_id::text = auth.uid()::text)
        OR auth.role() = 'service_role'
    );

CREATE POLICY "Users can manage own alert rules" ON alert_rules
    FOR ALL USING (
        profile_id IN (SELECT id FROM profiles WHERE telegram_id::text = auth.uid()::text)
        OR auth.role() = 'service_role'
    );

-- Execution audit policies
CREATE POLICY "Users can view own execution audit" ON execution_audit
    FOR SELECT USING (
        profile_id IN (SELECT id FROM profiles WHERE telegram_id::text = auth.uid()::text)
        OR auth.role() = 'service_role'
    );

CREATE POLICY "Service role manage execution audit" ON execution_audit
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================
-- GRANTS FOR SERVICE_ROLE (Backend API)
-- ============================================
GRANT USAGE ON SCHEMA public TO service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO service_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO service_role;

-- ============================================
-- HELPFUL VIEWS
-- ============================================

-- User dashboard view
CREATE OR REPLACE VIEW user_dashboard AS
SELECT 
    p.telegram_id,
    p.username,
    p.risk_level,
    p.max_allocation_pct,
    p.max_concurrent_trades,
    p.trading_mode,
    p.bot_enabled,
    p.wallet_connected,
    p.wallet_address,
    p.wallet_network,
    rs.stop_loss_pct,
    rs.take_profit_pct,
    rs.trailing_stop_pct,
    rs.max_daily_drawdown_pct,
    rs.whitelist_only,
    (SELECT json_agg(json_build_object('symbol', uw.symbol, 'exchange', uw.exchange, 'active', uw.active)) 
     FROM user_whitelist uw WHERE uw.profile_id = p.id AND uw.active = TRUE) as whitelist,
    (SELECT COUNT(*) FROM positions pos WHERE pos.profile_id = p.id) as open_positions_count,
    (SELECT COALESCE(SUM(pos.unrealized_pnl), 0) FROM positions pos WHERE pos.profile_id = p.id) as total_unrealized_pnl
FROM profiles p
LEFT JOIN risk_settings rs ON rs.profile_id = p.id;

-- Recent signals view
CREATE OR REPLACE VIEW recent_signals AS
SELECT 
    s.*,
    p.telegram_id
FROM signals s
LEFT JOIN profiles p ON p.id = s.profile_id
WHERE s.created_at > NOW() - INTERVAL '24 hours'
ORDER BY s.created_at DESC;

-- ============================================
-- COMPLETION MESSAGE
-- ============================================
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Aegis Quant Database Schema Deployed';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Tables created:';
    RAISE NOTICE '  - profiles (users)';
    RAISE NOTICE '  - user_credentials (encrypted CeFi keys)';
    RAISE NOTICE '  - user_whitelist (Engine A symbols)';
    RAISE NOTICE '  - risk_settings (risk management)';
    RAISE NOTICE '  - paper_balances (paper trading)';
    RAISE NOTICE '  - positions (open positions)';
    RAISE NOTICE '  - trade_logs (execution history)';
    RAISE NOTICE '  - signals (Engine A/B)';
    RAISE NOTICE '  - alert_rules (custom alerts)';
    RAISE NOTICE '  - execution_audit (immutable audit)';
    RAISE NOTICE '  - market_ticks (TimescaleDB)';
    RAISE NOTICE '  - market_candles (TimescaleDB)';
    RAISE NOTICE '  - social_signals (TimescaleDB)';
    RAISE NOTICE 'RLS policies enabled on all user tables';
    RAISE NOTICE 'Service role has full access for backend';
    RAISE NOTICE '========================================';
END $$;