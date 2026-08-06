-- Aegis Quant - Supabase schema (idempotent)
-- Safe to run multiple times. Compatible with backend SQLAlchemy models
-- (backend/app/models.py + backend/app/models/sources.py).
-- Run via SQL editor OR `supabase link --project-ref <ref> && supabase db push`

create extension if not exists pgcrypto;

-- ── Enum types (SQLAlchemy default naming = lowercase class name) ──────────
do $$
begin
  if not exists (select 1 from pg_type where typname = 'trademode') then
    create type trademode as enum ('paper', 'live');
  end if;
  if not exists (select 1 from pg_type where typname = 'risklevel') then
    create type risklevel as enum ('conservative', 'medium', 'aggressive');
  end if;
  if not exists (select 1 from pg_type where typname = 'orderside') then
    create type orderside as enum ('buy', 'sell');
  end if;
  if not exists (select 1 from pg_type where typname = 'orderstatus') then
    create type orderstatus as enum ('pending', 'filled', 'partial', 'cancelled', 'failed', 'rejected');
  end if;
  if not exists (select 1 from pg_type where typname = 'executiontype') then
    create type executiontype as enum ('paper', 'live');
  end if;
end $$;

-- ── profiles ──────────────────────────────────────────────────────────────
create table if not exists profiles (
  id uuid primary key default gen_random_uuid(),
  telegram_id bigint not null unique,
  username varchar(100),
  first_name varchar(100),
  last_name varchar(100),
  language_code varchar(10),
  wallet_connected boolean not null default false,
  wallet_address varchar(64),
  wallet_network varchar(10),
  wallet_public_key varchar(128),
  engine_b_enabled boolean not null default true,
  engine_b_min_confidence numeric(3, 2) default 0.70,
  risk_level risklevel not null default 'medium',
  max_allocation_pct numeric(5, 2) not null default 10.0,
  max_concurrent_trades integer not null default 3,
  trading_mode trademode not null default 'paper',
  bot_enabled boolean not null default false,
  engine_a_enabled boolean not null default true,
  engine_a_price_threshold numeric(5, 4) default 0.02,
  engine_a_volume_threshold numeric(5, 2) default 3.0,
  engine_a_spread_bps integer default 10,
  engine_a_funding_flip boolean default true,
  engine_a_min_confidence numeric(3, 2) default 0.70,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists ix_profiles_telegram_id on profiles (telegram_id);

-- ── user_credentials ─────────────────────────────────────────────────────
create table if not exists user_credentials (
  id serial primary key,
  profile_id uuid not null references profiles (id) on delete cascade,
  exchange varchar(20) not null,
  encrypted_api_key text not null,
  encrypted_api_secret text not null,
  encrypted_passphrase text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint uq_profile_exchange unique (profile_id, exchange)
);

-- ── user_whitelist ───────────────────────────────────────────────────────
create table if not exists user_whitelist (
  profile_id uuid not null references profiles (id) on delete cascade,
  symbol varchar(20) not null,
  exchange varchar(20) not null default 'bybit',
  timeframe varchar(10) not null default '1m',
  active boolean not null default true,
  added_at timestamptz not null default now(),
  primary key (profile_id, symbol, exchange)
);

-- ── risk_settings ────────────────────────────────────────────────────────
create table if not exists risk_settings (
  profile_id uuid primary key references profiles (id) on delete cascade,
  stop_loss_pct numeric(5, 2) not null default 3.0,
  take_profit_pct numeric(5, 2) not null default 6.0,
  trailing_stop_pct numeric(5, 2) not null default 1.0,
  max_allocation_pct numeric(5, 2) not null default 10.0,
  max_concurrent_trades integer not null default 3,
  max_daily_drawdown_pct numeric(5, 2) not null default 5.0,
  whitelist_only boolean not null default true,
  base_trade_usd numeric(5, 2) not null default 10.0,
  updated_at timestamptz not null default now()
);

-- ── paper_balances ───────────────────────────────────────────────────────
create table if not exists paper_balances (
  id serial primary key,
  profile_id uuid not null references profiles (id) on delete cascade,
  asset varchar(10) not null,
  balance numeric(20, 8) not null default 0,
  updated_at timestamptz not null default now(),
  constraint uq_profile_asset unique (profile_id, asset)
);

-- ── positions ────────────────────────────────────────────────────────────
create table if not exists positions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references profiles (id) on delete cascade,
  symbol varchar(20) not null,
  exchange varchar(20) not null,
  side orderside not null,
  size numeric(20, 8) not null,
  entry_price numeric(20, 8) not null,
  current_price numeric(20, 8) not null,
  unrealized_pnl numeric(20, 8) default 0,
  stop_loss numeric(20, 8),
  take_profit numeric(20, 8),
  trailing_stop numeric(20, 8),
  leverage integer default 1,
  mode trademode not null,
  is_closed boolean not null default false,
  opened_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists ix_positions_profile_symbol on positions (profile_id, symbol);

-- ── trade_logs ───────────────────────────────────────────────────────────
create table if not exists trade_logs (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references profiles (id) on delete cascade,
  symbol varchar(20) not null,
  exchange varchar(20) not null,
  side orderside not null,
  execution_type executiontype not null,
  size numeric(20, 8) not null,
  price numeric(20, 8) not null,
  total_value_usd numeric(20, 2) not null,
  status orderstatus not null default 'pending',
  slippage numeric(6, 4) default 0,
  commission numeric(20, 8) default 0,
  tx_hash text,
  order_id varchar(50),
  error_message text,
  executed_at timestamptz not null default now()
);
create index if not exists ix_trade_logs_profile_time on trade_logs (profile_id, executed_at);

-- ── signals ──────────────────────────────────────────────────────────────
create table if not exists signals (
  id uuid primary key default gen_random_uuid(),
  engine varchar(1) not null,
  ticker varchar(20) not null,
  category varchar(50),
  badge varchar(50),
  source varchar(100) not null,
  metric varchar(100),
  analysis text,
  confidence integer not null,
  action_label varchar(100),
  kronos_trajectories jsonb,
  kronos_mean_path jsonb,
  kronos_confidence_90 jsonb,
  sentiment_score numeric(4, 3),
  mentions_per_hour integer,
  liquidity_usd numeric(20, 2),
  created_at timestamptz not null default now()
);
create index if not exists ix_signals_created_at on signals (created_at);
create index if not exists ix_signals_engine_ticker_time on signals (engine, ticker, created_at);

-- ── alert_rules ──────────────────────────────────────────────────────────
create table if not exists alert_rules (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references profiles (id) on delete cascade,
  metric varchar(100) not null,
  condition varchar(20) not null,
  value varchar(50) not null,
  action varchar(200) not null,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  triggered_at timestamptz,
  trigger_count integer default 0
);

-- ── execution_audit ──────────────────────────────────────────────────────
create table if not exists execution_audit (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references profiles (id) on delete cascade,
  mode trademode not null,
  symbol varchar(20) not null,
  side orderside not null,
  size numeric(20, 8) not null,
  price numeric(20, 8) not null,
  sl numeric(20, 8),
  tp numeric(20, 8),
  kronos_confidence integer,
  trigger_type varchar(30) not null,
  status orderstatus not null,
  tx_hash text,
  error text,
  created_at timestamptz not null default now()
);
create index if not exists ix_execution_audit_created_at on execution_audit (created_at);

-- ── user_sessions ────────────────────────────────────────────────────────
create table if not exists user_sessions (
  id uuid primary key default gen_random_uuid(),
  telegram_id bigint not null,
  profile_id uuid references profiles (id) on delete cascade,
  token varchar(512) not null unique,
  expires_at timestamptz not null,
  ip_address varchar(45),
  user_agent varchar(500),
  created_at timestamptz not null default now()
);
create index if not exists ix_user_sessions_telegram_id on user_sessions (telegram_id);
create index if not exists ix_user_sessions_token on user_sessions (token);

-- ── copytrade_subscriptions ──────────────────────────────────────────────
create table if not exists copytrade_subscriptions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references profiles (id) on delete cascade,
  channel_id varchar(50) not null,
  confidence_threshold integer not null default 70,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint uq_profile_channel_sub unique (profile_id, channel_id)
);
create index if not exists ix_copytrade_subscriptions_channel_id on copytrade_subscriptions (channel_id);

-- ── user_sources / admin_sources ─────────────────────────────────────────
create table if not exists user_sources (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid not null references profiles (id) on delete cascade,
  name varchar(100) not null,
  source_type varchar(20) not null,
  url_or_handle varchar(500) not null,
  priority integer default 5,
  tags varchar(500) default '',
  description varchar(500),
  enabled boolean default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint uq_profile_source_name unique (profile_id, name),
  constraint uq_profile_source_url unique (profile_id, url_or_handle)
);

create table if not exists admin_sources (
  id uuid primary key default gen_random_uuid(),
  name varchar(100) not null unique,
  source_type varchar(20) not null,
  url_or_handle varchar(500) not null,
  priority integer default 5,
  tags varchar(500) default '',
  description text,
  enabled boolean default true,
  is_default boolean default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
-- ── updated_at maintenance ────────────────────────────────────────────────
create or replace function set_updated_at()
returns trigger language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end $$;

do $$
declare t text;
begin
  foreach t in array array['profiles', 'user_credentials', 'risk_settings', 'paper_balances', 'positions',
                          'copytrade_subscriptions', 'user_sources', 'admin_sources']
  loop
    if not exists (select 1 from pg_trigger where tgname = 'set_updated_at_' || t) then
      execute format('create trigger set_updated_at_%I before update on %I for each row execute function set_updated_at()', t, t);
    end if;
  end loop;
end $$;

-- ── seed default admin sources (matches legacy alembic migration 007) ────
insert into admin_sources (id, name, source_type, url_or_handle, priority, tags, description, is_default)
select * from (values
  (gen_random_uuid(), 'CoinTelegraph', 'rss', 'https://cointelegraph.com/rss', 8, '["general","major"]', 'Leading crypto news outlet', true),
  (gen_random_uuid(), 'Bitcoin Magazine', 'rss', 'https://bitcoinmagazine.com/.rss/full/', 7, '["btc","major"]', 'Bitcoin-focused news', true),
  (gen_random_uuid(), 'VitalikButerin', 'twitter', 'VitalikButerin', 9, '["ethereum","major"]', 'Ethereum founder', true),
  (gen_random_uuid(), 'WHAlerts', 'twitter', 'WHAlerts', 9, '["whale","alerts"]', 'Whale movement alerts', true),
  (gen_random_uuid(), 'CryptoWhale', 'telegram', '@CryptoWhale', 9, '["whale","alerts"]', 'Major whale alerts', true),
  (gen_random_uuid(), 'BitcoinWhale', 'telegram', '@BitcoinWhale', 8, '["bitcoin","whale"]', 'Bitcoin whale tracking', true)
) as s(id, name, source_type, url_or_handle, priority, tags, description, is_default)
where not exists (select 1 from admin_sources where name = s.name);
