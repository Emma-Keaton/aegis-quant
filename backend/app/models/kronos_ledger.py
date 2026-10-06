"""Kronos prediction ledger and learned-parameter models.

Kronos is a frozen forecaster: it predicts and never learns. Everything in this
module exists because of that. To improve behaviour from real trading outcomes,
this backend must (a) persist every prediction, (b) score it against realised
prices once the horizon elapses, and (c) store the parameters derived from those
scores.

The persistence is not optional bookkeeping. Both backends run on Render's free
tier, which suspends idle instances after ~15 minutes and discards process
memory. An in-memory record of predictions cannot survive that, and a learner
that forgets between every spin-down never learns anything.

`rerunnable_schema.sql` mirrors these tables for direct application in Supabase.
Keep the two in sync; the SQL is additive and idempotent.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB as _PG_JSONB

# JSONB is postgres-only; the sqlite variant keeps `create_all` working for the
# in-memory test database, exactly like the sqlalchemy.Uuid choice above.
JSONB = _PG_JSONB().with_variant(JSON(), "sqlite")


def _utcnow() -> datetime:
    """Timezone-aware UTC now, for column defaults.

    These columns are declared `DateTime(timezone=True)`, but `datetime.utcnow`
    returns a *naive* value. The mismatch is not cosmetic: comparing a stored
    naive `created_at` against an aware `now()` raises `TypeError`, which made
    `LedgerStore.due_forecasts()` fail on every unscored row. `utcnow` is also
    deprecated. One aware source of truth for every timestamp default.
    """
    return datetime.now(timezone.utc)

from app.database import Base

# `sqlalchemy.Uuid` rather than `postgresql.UUID`: it renders as `UUID` on
# Postgres (identical DDL, confirmed against the generated schema) and as
# CHAR(32) on sqlite, so these tables can be exercised in tests. The
# postgres-dialect UUID type does not bind on sqlite at all.


class KronosForecast(Base):
    """One prediction Kronos produced, later scored against realised prices."""

    __tablename__ = "kronos_forecasts"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Identity
    symbol = Column(String(32), nullable=False, index=True)
    # 'kronos' | 'fallback' | 'placeholder'. Recorded so a replacement forecast
    # is never mistaken for a real one during calibration.
    source = Column(String(16), nullable=False, default="kronos")
    model = Column(String(64), nullable=True)

    # Request shape, so a score can be joined back to how it was asked for.
    horizon = Column(Integer, nullable=False)
    interval_seconds = Column(Integer, nullable=False)
    sample_count = Column(Integer, nullable=False, default=1)

    # Market state at prediction time.
    last_close = Column(Float, nullable=False)

    # Prediction. `trajectories` holds one path per sampled sample and can be
    # large, so it is kept separate from the frequently-read scalar columns.
    mean_path = Column(JSONB, nullable=True)
    trajectories = Column(JSONB, nullable=True)
    terminal_low = Column(Float, nullable=True)
    terminal_high = Column(Float, nullable=True)

    # Model-derived signal. Uncalibrated: this is P(up), not a validated
    # probability. Do not gate capital on it until `scored` rows exist.
    probability_up = Column(Float, nullable=True)
    confidence = Column(Integer, nullable=True)

    # Scoring, filled once the horizon has elapsed.
    scored = Column(Boolean, nullable=False, default=False)
    realised = Column(Float, nullable=True)
    was_up = Column(Boolean, nullable=True)
    within_band = Column(Boolean, nullable=True)
    absolute_error = Column(Float, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, index=True)
    scored_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # The hot path is "unscored, oldest first".
        Index(
            "ix_kronos_forecasts_pending",
            "created_at",
            postgresql_where=Column("scored") == False,  # noqa: E712
        ),
        Index("ix_kronos_forecasts_symbol_time", "symbol", "created_at"),
        Index(
            "ix_kronos_forecasts_scored",
            "confidence",
            postgresql_where=Column("scored") == True,  # noqa: E712
        ),
    )


#: Sentinel used in place of a per-user key so learned parameters and model
#: assignments are workspace-global rather than per-profile.
#:
#: Learning is a property of the forecaster, not of a user. Kronos is the same
#: frozen model for everyone, so evidence from one profile's trades legitimately
#: improves the estimate for all of them. Keying per-profile would fragment the
#: evidence until each had hundreds of scored forecasts on its own — which on a
#: paper-trading tier may never happen, leaving every user permanently stuck at
#: the configured defaults.
#:
#: `uuid.UUID(int=0)` is used rather than a nullable column so the existing
#: uniqueness constraints stay meaningful; a NULL would defeat them.
GLOBAL_KEY = uuid.UUID(int=0)


class LearnedParameter(Base):
    """A learned scalar, plus the evidence that justifies it.

    Workspace-global: one row per `name`, improved by every profile's scored
    forecasts. See `GLOBAL_KEY`.

    `validated` is the gate. A value derived from a handful of observations is
    stored for inspection but is not applied to trading until it clears
    `strategy_learner.MIN_SAMPLES` and beats a coin flip with statistical
    confidence. `sample_size` and `hit_rate` travel with the value so it can be
    sanity-checked at a glance.
    """

    __tablename__ = "learned_parameters"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Always GLOBAL_KEY. Retained as a column so a future per-profile override
    # can coexist, and so the unique constraint stays total.
    profile_id = Column(Uuid(as_uuid=True), nullable=False, default=GLOBAL_KEY)
    name = Column(String(64), nullable=False)
    value = Column(Float, nullable=False)

    version = Column(Integer, nullable=False, default=1)
    sample_size = Column(Integer, nullable=False, default=0)
    hit_rate = Column(Float, nullable=True)
    validated = Column(Boolean, nullable=False, default=False)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ux_learned_parameters_scope_name", "profile_id", "name", unique=True),
    )


class LearnedParameterHistory(Base):
    """Append-only audit of every parameter change.

    Without this, a bad threshold is unauditable: there is no way to tell what
    evidence produced it or when it changed.
    """

    __tablename__ = "learned_parameter_history"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(Uuid(as_uuid=True), nullable=False, default=GLOBAL_KEY)
    name = Column(String(64), nullable=False)
    previous_value = Column(Float, nullable=True)
    new_value = Column(Float, nullable=False)
    version = Column(Integer, nullable=False)
    sample_size = Column(Integer, nullable=False)
    hit_rate = Column(Float, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, index=True)

    __table_args__ = (
        Index("ix_learned_parameter_history_lookup", "profile_id", "name", "created_at"),
    )


class ModelAssignment(Base):
    """Which Kronos variant serves a scope, and how it has performed.

    Workspace-global per (scope, symbol), so a model proven on one profile's
    trades is immediately usable by every other profile. See `GLOBAL_KEY`.

    Model selection is a ranking problem, not a guess: a variant is promoted
    only after beating a coin flip with enough samples to justify the claim.
    `promoted_at` records when, so a rotation is auditable.
    """

    __tablename__ = "model_assignments"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(Uuid(as_uuid=True), nullable=False, default=GLOBAL_KEY)

    scope = Column(String(16), nullable=False, default="global")
    symbol = Column(String(32), nullable=True)
    model = Column(String(64), nullable=False)

    # Evidence for the current assignment.
    hit_rate = Column(Float, nullable=True)
    sample_size = Column(Integer, nullable=False, default=0)
    mean_latency_ms = Column(Float, nullable=True)
    # False until the model has cleared the promotion gate.
    promoted = Column(Boolean, nullable=False, default=False)

    assigned_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    promoted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index(
            "ux_model_assignments_scope",
            "profile_id",
            "scope",
            "symbol",
            unique=True,
        ),
    )