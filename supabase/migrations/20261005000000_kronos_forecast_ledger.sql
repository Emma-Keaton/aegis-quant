-- Kronos prediction ledger and learned-parameter store.
--
-- Why this exists: Kronos predicts but never learns. To improve its trading
-- behaviour we must (a) keep every prediction and (b) score it against realised
-- prices. That state was previously in-memory, which Render's free tier destroys
-- on every spin-down after ~15 minutes idle. Persisting it is what makes the
-- feedback loop measurable at all.
--
-- Idempotent so it can be re-applied safely.

-- One row per prediction Kronos produced.
create table if not exists kronos_forecasts (
    id                  uuid primary key default gen_random_uuid(),

    -- Identity
    symbol              text        not null,
    source              text        not null default 'kronos',  -- kronos | fallback | placeholder
    model               text,

    -- Request shape, so a score can be joined back to how it was asked for.
    horizon             integer     not null,
    interval_seconds    integer     not null,
    sample_count        integer     not null default 1,

    -- Market state at prediction time.
    last_close          double precision not null,

    -- Prediction. `mean_path` and `terminals` are JSONB; `trajectories` is only
    -- populated when distribution_valid, and can be large, so it is kept apart
    -- from the frequently-read columns.
    mean_path           jsonb,
    trajectories        jsonb,
    terminal_low        double precision,
    terminal_high       double precision,

    -- Model-derived signal. Uncalibrated: this is P(up), not a validated
    -- probability.
    probability_up      double precision,
    confidence          integer,

    -- Scoring, filled in later once the horizon has elapsed.
    scored              boolean     not null default false,
    realised            double precision,
    was_up              boolean,
    within_band         boolean,
    absolute_error      double precision,

    created_at          timestamptz not null default now(),
    scored_at           timestamptz
);

-- The hot path is "unscored, oldest first".
create index if not exists ix_kronos_forecasts_pending
    on kronos_forecasts (created_at)
    where scored = false;

-- Calibration is read per symbol and per confidence bucket.
create index if not exists ix_kronos_forecasts_symbol_time
    on kronos_forecasts (symbol, created_at desc);

create index if not exists ix_kronos_forecasts_scored
    on kronos_forecasts (scored, confidence)
    where scored = true;

-- Learned parameters. One row per (profile, name): the model's weights are
-- per-user because risk tolerance and position sizing are.
--
-- `version` increments on every update so a change can be rolled back, and
-- `sample_size` / `hit_rate` travel with it so a weight can be sanity-checked
-- against the evidence that produced it. A weight derived from 12 observations
-- must not look like one derived from 12,000.
create table if not exists learned_parameters (
    id                  uuid primary key default gen_random_uuid(),

    profile_id          uuid        not null,
    name                text        not null,
    value               double precision not null,

    -- Provenance. Without these a number cannot be audited.
    version             integer     not null default 1,
    sample_size         integer     not null default 0,
    hit_rate            double precision,
    updated_at          timestamptz not null default now(),

    -- Only a value that cleared validation is eligible to gate a trade.
    validated           boolean     not null default false,

    unique (profile_id, name)
);

create index if not exists ix_learned_parameters_profile
    on learned_parameters (profile_id, validated);

-- Every update to a learned parameter, so a bad weight can be traced to the
-- evidence that produced it.
create table if not exists learned_parameter_history (
    id                  uuid primary key default gen_random_uuid(),
    profile_id          uuid        not null,
    name                text        not null,
    previous_value      double precision,
    new_value           double precision not null,
    version             integer     not null,
    sample_size         integer     not null,
    hit_rate            double precision,
    reason              text,
    created_at          timestamptz not null default now()
);

create index if not exists ix_learned_parameter_history_profile
    on learned_parameter_history (profile_id, name, created_at desc);