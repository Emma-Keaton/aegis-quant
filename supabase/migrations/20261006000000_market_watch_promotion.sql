-- Market-watch (DEX snapshots, whale flows), circuit breaker, and the
-- paper→live promotion decision log.
--
-- Why this exists: the watchers are evidence collection, not trading. Snapshots
-- and flows feed Telegram pings and the Intel surface; the promotion gate is
-- the only path from that evidence to live orders, and every decision it makes
-- is kept verbatim so it can be re-audited. The breaker is a single row that
-- trips on drawdown / consecutive losses and never self-clears.
--
-- Idempotent so it can be re-applied safely. The app also runs create_all on
-- startup, so these tables appear even if this file is skipped.

-- Point-in-time DEX pool readings (dexwatch).
create table if not exists dex_snapshots (
    id                  varchar(36) primary key,
    symbol              varchar(20) not null,
    address             varchar(128),
    chain               varchar(20) not null default 'solana',
    dex_id              varchar(64),
    pair_address        varchar(128),
    price_usd           double precision,
    liquidity_usd       double precision,
    volume_usd          double precision,
    price_change_5m     double precision,
    price_change_1h     double precision,
    price_change_24h    double precision,
    buys                integer,
    sells               integer,
    source              varchar(24) not null default 'dexscreener',
    raw                 jsonb,
    ts                  timestamptz not null default now()
);
create index if not exists ix_dex_snapshots_symbol on dex_snapshots (symbol);
create index if not exists ix_dex_snapshots_symbol_ts on dex_snapshots (symbol, ts);
create index if not exists ix_dex_snapshots_chain_ts on dex_snapshots (chain, ts);

-- Large wallet movements of tracked mints (whalewatch). The unique key is the
-- dedupe identity from the reference implementation: signature + symbol +
-- wallet + side, so overlapping ticks and restarts cannot double-count.
create table if not exists whale_flows (
    id                  varchar(36) primary key,
    wallet              varchar(128) not null,
    symbol              varchar(20) not null,
    chain               varchar(20) not null default 'solana',
    ts                  timestamptz not null,
    side                varchar(10) not null default 'unknown',  -- buy | sell | unknown
    amount_usd          double precision not null,
    token_amount        double precision,
    tx_signature        varchar(128) not null,
    raw                 jsonb,
    created_at          timestamptz not null default now(),
    constraint uq_whale_flow_key unique (tx_signature, symbol, wallet, side)
);
create index if not exists ix_whale_flows_symbol on whale_flows (symbol);
create index if not exists ix_whale_flows_ts on whale_flows (ts);

-- Global trading circuit breaker (singleton row, id = 1).
-- `closed` trades normally, `warning` is advisory, `open` refuses new orders
-- until an operator calls resume — breakers never self-clear.
create table if not exists trading_breaker (
    id                  integer primary key default 1,
    state               varchar(10) not null default 'closed',
    peak_equity         double precision,
    daily_loss_usd      double precision not null default 0.0,
    consecutive_losses  integer not null default 0,
    reason              text,
    updated_at          timestamptz not null default now()
);

-- Audit trail for paper→live promotion evaluations. `status`:
-- rejected (evidence failed) | promoted (live orders allowed). `profile_id`
-- is text because decisions are keyed by the profile id string; the evidence
-- blob is kept verbatim so a decision can be re-audited.
create table if not exists promotion_decisions (
    id                  varchar(36) primary key,
    profile_id          varchar(36) not null,
    status              varchar(20) not null,
    reason              text,
    evidence            jsonb,
    created_at          timestamptz not null default now(),
    decided_at          timestamptz
);
create index if not exists ix_promotion_decisions_profile_id on promotion_decisions (profile_id);
