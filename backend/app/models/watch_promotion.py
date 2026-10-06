"""Market-watch and promotion models.

Ported from beast-trader's `dex_snapshots`, `whale_flows` and the promotion /
circuit-breaker state, rewritten for this SQLAlchemy stack. Three rules from
the reference design carry over verbatim:

1. Observations only — nothing in the watcher decides to trade. The promotion
   gate is the only path from evidence to a mode that can place live orders.
2. Degrade rather than fail — a missing API key or exhausted quota skips a
   tick instead of raising.
3. Dedupe at the database — flows carry a natural key so overlapping ticks
   (and restarts) cannot double-count evidence.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text, UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import JSON, JSONB
from sqlalchemy import BigInteger

from app.database import Base

# JSONB is postgres-only; sqlite variant keeps `create_all` working for the
# in-memory test database (same rationale as kronos_ledger.py).
_JSONB = JSONB().with_variant(JSON(), "sqlite")


class DexSnapshot(Base):
    """One point-in-time DEX pool reading for a token (dexwatch port)."""

    __tablename__ = "dex_snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol = Column(String(20), nullable=False, index=True)
    address = Column(String(128), nullable=True)
    chain = Column(String(20), nullable=False, default="solana")
    dex_id = Column(String(64), nullable=True)
    pair_address = Column(String(128), nullable=True)
    price_usd = Column(Float, nullable=True)
    liquidity_usd = Column(Float, nullable=True)
    volume_usd = Column(Float, nullable=True)
    price_change_5m = Column(Float, nullable=True)
    price_change_1h = Column(Float, nullable=True)
    price_change_24h = Column(Float, nullable=True)
    buys = Column(Integer, nullable=True)
    sells = Column(Integer, nullable=True)
    source = Column(String(24), nullable=False, default="dexscreener")
    raw = Column(_JSONB, nullable=True)
    ts = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_dex_snapshots_symbol_ts", "symbol", "ts"),
        Index("ix_dex_snapshots_chain_ts", "chain", "ts"),
    )


class WhaleFlow(Base):
    """A large wallet movement of a tracked mint (whalewatch port).

    The unique key is the dedupe identity from the reference implementation:
    signature + symbol + wallet + side, so overlapping ticks and process
    restarts cannot insert the same flow twice.
    """

    __tablename__ = "whale_flows"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wallet = Column(String(128), nullable=False)
    symbol = Column(String(20), nullable=False, index=True)
    chain = Column(String(20), nullable=False, default="solana")
    ts = Column(DateTime(timezone=True), nullable=False)
    side = Column(String(10), nullable=False, default="unknown")  # buy | sell | unknown
    amount_usd = Column(Float, nullable=False)
    token_amount = Column(Float, nullable=True)
    tx_signature = Column(String(128), nullable=False)
    raw = Column(_JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tx_signature", "symbol", "wallet", "side", name="uq_whale_flow_key"),
        Index("ix_whale_flows_ts", "ts"),
    )


class BreakerState(Base):
    """Global trading circuit breaker (singleton row, id = 1).

    `closed` trades normally, `warning` is advisory, `open` refuses every
    live order until an operator calls resume — breakers never self-clear.
    """

    __tablename__ = "trading_breaker"

    id = Column(Integer, primary_key=True, default=1)
    state = Column(String(10), nullable=False, default="closed")
    peak_equity = Column(Float, nullable=True)
    daily_loss_usd = Column(Float, nullable=False, default=0.0)
    consecutive_losses = Column(Integer, nullable=False, default=0)
    reason = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow,
                        onupdate=datetime.utcnow)


class PromotionDecision(Base):
    """Audit trail for paper → live promotion evaluations (one row per run).

    `status` is the outcome of the static bar: `rejected` (evidence failed),
    `eligible` (bar cleared, waiting for readiness), `promoted` (live orders
    allowed). Evidence is kept verbatim so a decision can be re-audited.
    """

    __tablename__ = "promotion_decisions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_id = Column(String(36), nullable=False, index=True)
    status = Column(String(20), nullable=False)
    reason = Column(Text, nullable=True)
    evidence = Column(_JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    decided_at = Column(DateTime(timezone=True), nullable=True)
