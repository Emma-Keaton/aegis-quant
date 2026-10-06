-- aegis-quant: full database schema for Supabase.
--
-- Generated from app/models by scripts/generate_schema.py. Re-runnable:
-- every statement is CREATE ... IF NOT EXISTS, so applying it to a fresh
-- project or an existing one both succeed.
--
-- Run in the Supabase SQL editor, or:
--   psql "$DATABASE_URL" -f scripts/schema.sql
--
-- The app also runs create_all on startup, so this file exists for
-- operators who provision the database ahead of the first deploy.

-- Generated from SQLAlchemy metadata. Do not hand-edit.
--
-- Idempotent: every statement is IF NOT EXISTS, so this can be re-applied
-- to an existing database any number of times.

CREATE TABLE IF NOT EXISTS alert_rules (
		id UUID NOT NULL DEFAULT gen_random_uuid(),
	profile_id UUID NOT NULL, 
	metric VARCHAR(100) NOT NULL, 
	condition VARCHAR(20) NOT NULL, 
	value VARCHAR(50) NOT NULL, 
	action VARCHAR(200) NOT NULL, 
		active BOOLEAN NOT NULL DEFAULT TRUE,
		created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	triggered_at TIMESTAMP WITH TIME ZONE, 
		trigger_count INTEGER DEFAULT 0,
	PRIMARY KEY (id), 
	FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS copytrade_subscriptions (
		id UUID NOT NULL DEFAULT gen_random_uuid(),
	profile_id UUID NOT NULL, 
	channel_id VARCHAR(50) NOT NULL, 
		confidence_threshold INTEGER NOT NULL DEFAULT 70,
	parser_llm VARCHAR(20), 
		active BOOLEAN NOT NULL DEFAULT TRUE,
		created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
		updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	PRIMARY KEY (id), 
	CONSTRAINT uq_profile_channel_sub UNIQUE (profile_id, channel_id), 
	FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dex_snapshots (
	id VARCHAR(36) NOT NULL, 
	symbol VARCHAR(20) NOT NULL, 
	address VARCHAR(128), 
		chain VARCHAR(20) NOT NULL DEFAULT 'solana',
	dex_id VARCHAR(64), 
	pair_address VARCHAR(128), 
	price_usd FLOAT, 
	liquidity_usd FLOAT, 
	volume_usd FLOAT, 
	price_change_5m FLOAT, 
	price_change_1h FLOAT, 
	price_change_24h FLOAT, 
	buys INTEGER, 
	sells INTEGER, 
		source VARCHAR(24) NOT NULL DEFAULT 'dexscreener',
	raw JSONB, 
		ts TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS execution_audit (
		id UUID NOT NULL DEFAULT gen_random_uuid(),
	profile_id UUID NOT NULL, 
	mode trademode NOT NULL, 
	symbol VARCHAR(20) NOT NULL, 
	side orderside NOT NULL, 
	size NUMERIC(20, 8) NOT NULL, 
	price NUMERIC(20, 8) NOT NULL, 
	sl NUMERIC(20, 8), 
	tp NUMERIC(20, 8), 
	kronos_confidence INTEGER, 
	trigger_type VARCHAR(30) NOT NULL, 
	status orderstatus NOT NULL, 
	tx_hash TEXT, 
	error TEXT, 
		created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS kronos_forecasts (
		id UUID NOT NULL DEFAULT gen_random_uuid(),
	symbol VARCHAR(32) NOT NULL, 
		source VARCHAR(16) NOT NULL DEFAULT 'kronos',
	model VARCHAR(64), 
	horizon INTEGER NOT NULL, 
	interval_seconds INTEGER NOT NULL, 
		sample_count INTEGER NOT NULL DEFAULT 1,
	last_close FLOAT NOT NULL, 
	mean_path JSONB, 
	trajectories JSONB, 
	terminal_low FLOAT, 
	terminal_high FLOAT, 
	probability_up FLOAT, 
	confidence INTEGER, 
		scored BOOLEAN NOT NULL DEFAULT FALSE,
	realised FLOAT, 
	was_up BOOLEAN, 
	within_band BOOLEAN, 
	absolute_error FLOAT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	scored_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS learned_parameter_history (
		id UUID NOT NULL DEFAULT gen_random_uuid(),
	profile_id UUID NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	previous_value FLOAT, 
	new_value FLOAT NOT NULL, 
	version INTEGER NOT NULL, 
	sample_size INTEGER NOT NULL, 
	hit_rate FLOAT, 
	reason TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS learned_parameters (
		id UUID NOT NULL DEFAULT gen_random_uuid(),
	profile_id UUID NOT NULL, 
	name VARCHAR(64) NOT NULL, 
	value FLOAT NOT NULL, 
		version INTEGER NOT NULL DEFAULT 1,
		sample_size INTEGER NOT NULL DEFAULT 0,
	hit_rate FLOAT, 
		validated BOOLEAN NOT NULL DEFAULT FALSE,
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS model_assignments (
		id UUID NOT NULL DEFAULT gen_random_uuid(),
	profile_id UUID NOT NULL, 
		scope VARCHAR(16) NOT NULL DEFAULT 'global',
	symbol VARCHAR(32), 
	model VARCHAR(64) NOT NULL, 
	hit_rate FLOAT, 
		sample_size INTEGER NOT NULL DEFAULT 0,
	mean_latency_ms FLOAT, 
		promoted BOOLEAN NOT NULL DEFAULT FALSE,
	assigned_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	promoted_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS paper_balances (
	id SERIAL NOT NULL, 
	profile_id UUID NOT NULL, 
	asset VARCHAR(10) NOT NULL, 
		balance NUMERIC(20, 8) NOT NULL DEFAULT 0,
		updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	PRIMARY KEY (id), 
	CONSTRAINT uq_profile_asset UNIQUE (profile_id, asset), 
	FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS positions (
		id UUID NOT NULL DEFAULT gen_random_uuid(),
	profile_id UUID NOT NULL, 
	symbol VARCHAR(20) NOT NULL, 
	exchange VARCHAR(20) NOT NULL, 
	side orderside NOT NULL, 
	size NUMERIC(20, 8) NOT NULL, 
	entry_price NUMERIC(20, 8) NOT NULL, 
	current_price NUMERIC(20, 8) NOT NULL, 
		unrealized_pnl NUMERIC(20, 8) DEFAULT 0,
	stop_loss NUMERIC(20, 8), 
	take_profit NUMERIC(20, 8), 
	trailing_stop NUMERIC(20, 8), 
		leverage INTEGER DEFAULT 1,
	mode trademode NOT NULL, 
		is_closed BOOLEAN NOT NULL DEFAULT FALSE,
		opened_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
		updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS profiles (
		id UUID NOT NULL DEFAULT gen_random_uuid(),
	telegram_id BIGINT NOT NULL, 
	username VARCHAR(100), 
	first_name VARCHAR(100), 
	last_name VARCHAR(100), 
	language_code VARCHAR(10), 
		risk_level risklevel NOT NULL DEFAULT 'medium',
		max_allocation_pct NUMERIC(5, 2) NOT NULL DEFAULT 10.0,
		max_concurrent_trades INTEGER NOT NULL DEFAULT 3,
		trading_mode trademode NOT NULL DEFAULT 'paper',
		bot_enabled BOOLEAN NOT NULL DEFAULT FALSE,
		engine_a_enabled BOOLEAN NOT NULL DEFAULT TRUE,
		engine_a_price_threshold NUMERIC(5, 4) DEFAULT 0.02,
		engine_a_volume_threshold NUMERIC(5, 2) DEFAULT 3.0,
		engine_a_spread_bps INTEGER DEFAULT 10,
		engine_a_funding_flip BOOLEAN DEFAULT TRUE,
		engine_a_min_confidence NUMERIC(3, 2) DEFAULT 0.7,
		created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
		updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
		wallet_connected BOOLEAN NOT NULL DEFAULT FALSE,
	wallet_address VARCHAR(64), 
	wallet_network VARCHAR(10), 
	wallet_public_key VARCHAR(128), 
	solana_private_key_enc TEXT, 
	ton_mnemonic_enc TEXT, 
		engine_b_enabled BOOLEAN NOT NULL DEFAULT TRUE,
		engine_b_min_confidence NUMERIC(3, 2) DEFAULT 0.7,
		onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE,
		onboarding_pages TEXT NOT NULL DEFAULT '[]',
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS promotion_decisions (
	id VARCHAR(36) NOT NULL, 
	profile_id VARCHAR(36) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	reason TEXT, 
	evidence JSONB, 
		created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	decided_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS risk_settings (
	profile_id UUID NOT NULL, 
		stop_loss_pct NUMERIC(5, 2) NOT NULL DEFAULT 3.0,
		take_profit_pct NUMERIC(5, 2) NOT NULL DEFAULT 6.0,
		trailing_stop_pct NUMERIC(5, 2) NOT NULL DEFAULT 1.0,
		max_allocation_pct NUMERIC(5, 2) NOT NULL DEFAULT 10.0,
		max_concurrent_trades INTEGER NOT NULL DEFAULT 3,
		max_daily_drawdown_pct NUMERIC(5, 2) NOT NULL DEFAULT 5.0,
		whitelist_only BOOLEAN NOT NULL DEFAULT TRUE,
		spot_margin_enabled BOOLEAN NOT NULL DEFAULT TRUE,
		base_trade_usd NUMERIC(5, 2) NOT NULL DEFAULT 10.0,
		updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	PRIMARY KEY (profile_id), 
	FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS signals (
		id UUID NOT NULL DEFAULT gen_random_uuid(),
	engine VARCHAR(1) NOT NULL, 
	ticker VARCHAR(20) NOT NULL, 
	category VARCHAR(50), 
	badge VARCHAR(50), 
	source VARCHAR(100) NOT NULL, 
	metric VARCHAR(100), 
	analysis TEXT, 
	confidence INTEGER NOT NULL, 
	action_label VARCHAR(100), 
	kronos_trajectories JSONB, 
	kronos_mean_path JSONB, 
	kronos_confidence_90 JSONB, 
	sentiment_score NUMERIC(4, 3), 
	mentions_per_hour INTEGER, 
	liquidity_usd NUMERIC(20, 2), 
		created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS telegram_links (
	profile_id UUID NOT NULL, 
	phone VARCHAR(30), 
	session_encrypted TEXT, 
		status VARCHAR(30) NOT NULL DEFAULT 'pending',
		created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
		updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	PRIMARY KEY (profile_id), 
	FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trade_logs (
		id UUID NOT NULL DEFAULT gen_random_uuid(),
	profile_id UUID NOT NULL, 
	symbol VARCHAR(20) NOT NULL, 
	exchange VARCHAR(20) NOT NULL, 
	side orderside NOT NULL, 
	execution_type executiontype NOT NULL, 
	size NUMERIC(20, 8) NOT NULL, 
	price NUMERIC(20, 8) NOT NULL, 
	total_value_usd NUMERIC(20, 2) NOT NULL, 
		status orderstatus NOT NULL DEFAULT 'pending',
		slippage NUMERIC(6, 4) DEFAULT 0,
		commission NUMERIC(20, 8) DEFAULT 0,
	tx_hash TEXT, 
	order_id VARCHAR(50), 
	error_message TEXT, 
		executed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	realized_pnl NUMERIC(20, 8), 
	entry_price NUMERIC(20, 8), 
	exit_price NUMERIC(20, 8), 
	closed_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trading_breaker (
		id INTEGER NOT NULL DEFAULT 1,
		state VARCHAR(10) NOT NULL DEFAULT 'closed',
	peak_equity FLOAT, 
		daily_loss_usd FLOAT NOT NULL DEFAULT 0.0,
		consecutive_losses INTEGER NOT NULL DEFAULT 0,
	reason TEXT, 
		updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS user_credentials (
	id SERIAL NOT NULL, 
	profile_id UUID NOT NULL, 
	exchange VARCHAR(20) NOT NULL, 
	encrypted_api_key TEXT NOT NULL, 
	encrypted_api_secret TEXT NOT NULL, 
	encrypted_passphrase TEXT, 
		is_active BOOLEAN NOT NULL DEFAULT TRUE,
		created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
		updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	PRIMARY KEY (id), 
	CONSTRAINT uq_profile_exchange UNIQUE (profile_id, exchange), 
	FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_sessions (
		id UUID NOT NULL DEFAULT gen_random_uuid(),
	telegram_id BIGINT NOT NULL, 
	profile_id UUID, 
	token VARCHAR(512) NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	ip_address VARCHAR(45), 
	user_agent VARCHAR(500), 
		created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	PRIMARY KEY (id), 
	FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_whitelist (
	profile_id UUID NOT NULL, 
	symbol VARCHAR(20) NOT NULL, 
		exchange VARCHAR(20) NOT NULL DEFAULT 'bybit',
		timeframe VARCHAR(10) NOT NULL DEFAULT '1m',
		active BOOLEAN NOT NULL DEFAULT TRUE,
		added_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	PRIMARY KEY (profile_id, symbol, exchange), 
	FOREIGN KEY(profile_id) REFERENCES profiles (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS whale_flows (
	id VARCHAR(36) NOT NULL, 
	wallet VARCHAR(128) NOT NULL, 
	symbol VARCHAR(20) NOT NULL, 
		chain VARCHAR(20) NOT NULL DEFAULT 'solana',
	ts TIMESTAMP WITH TIME ZONE NOT NULL, 
		side VARCHAR(10) NOT NULL DEFAULT 'unknown',
	amount_usd FLOAT NOT NULL, 
	token_amount FLOAT, 
	tx_signature VARCHAR(128) NOT NULL, 
	raw JSONB, 
		created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
	PRIMARY KEY (id), 
	CONSTRAINT uq_whale_flow_key UNIQUE (tx_signature, symbol, wallet, side)
);


CREATE INDEX IF NOT EXISTS ix_copytrade_subscriptions_channel_id ON copytrade_subscriptions (channel_id);

CREATE INDEX IF NOT EXISTS ix_dex_snapshots_chain_ts ON dex_snapshots (chain, ts);
CREATE INDEX IF NOT EXISTS ix_dex_snapshots_symbol ON dex_snapshots (symbol);
CREATE INDEX IF NOT EXISTS ix_dex_snapshots_symbol_ts ON dex_snapshots (symbol, ts);

CREATE INDEX IF NOT EXISTS idx_audit_profile_time ON execution_audit (profile_id, created_at);
CREATE INDEX IF NOT EXISTS ix_execution_audit_created_at ON execution_audit (created_at);

CREATE INDEX IF NOT EXISTS ix_kronos_forecasts_created_at ON kronos_forecasts (created_at);
CREATE INDEX IF NOT EXISTS ix_kronos_forecasts_pending ON kronos_forecasts (created_at) WHERE scored = false;
CREATE INDEX IF NOT EXISTS ix_kronos_forecasts_scored ON kronos_forecasts (confidence) WHERE scored = true;
CREATE INDEX IF NOT EXISTS ix_kronos_forecasts_symbol ON kronos_forecasts (symbol);
CREATE INDEX IF NOT EXISTS ix_kronos_forecasts_symbol_time ON kronos_forecasts (symbol, created_at);

CREATE INDEX IF NOT EXISTS ix_learned_parameter_history_created_at ON learned_parameter_history (created_at);
CREATE INDEX IF NOT EXISTS ix_learned_parameter_history_lookup ON learned_parameter_history (profile_id, name, created_at);

CREATE UNIQUE INDEX IF NOT EXISTS ux_learned_parameters_scope_name ON learned_parameters (profile_id, name);

CREATE UNIQUE INDEX IF NOT EXISTS ux_model_assignments_scope ON model_assignments (profile_id, scope, symbol);


CREATE INDEX IF NOT EXISTS idx_positions_profile_symbol ON positions (profile_id, symbol);

CREATE UNIQUE INDEX IF NOT EXISTS ix_profiles_telegram_id ON profiles (telegram_id);

CREATE INDEX IF NOT EXISTS ix_promotion_decisions_profile_id ON promotion_decisions (profile_id);


CREATE INDEX IF NOT EXISTS idx_signals_engine_ticker_time ON signals (engine, ticker, created_at);
CREATE INDEX IF NOT EXISTS ix_signals_created_at ON signals (created_at);
CREATE INDEX IF NOT EXISTS ix_signals_ticker ON signals (ticker);


CREATE INDEX IF NOT EXISTS idx_trades_profile_time ON trade_logs (profile_id, executed_at);



CREATE INDEX IF NOT EXISTS ix_user_sessions_telegram_id ON user_sessions (telegram_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_user_sessions_token ON user_sessions (token);


CREATE INDEX IF NOT EXISTS ix_whale_flows_symbol ON whale_flows (symbol);
CREATE INDEX IF NOT EXISTS ix_whale_flows_ts ON whale_flows (ts);
