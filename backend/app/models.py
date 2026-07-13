import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Numeric, Text, ForeignKey, Enum as SQLEnum, Index, UniqueConstraint, BigInteger, select
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, declarative_base
import enum

Base = declarative_base()


class TradeMode(str, enum.Enum):
    PAPER = "paper"
    LIVE = "live"


class RiskLevel(str, enum.Enum):
    CONSERVATIVE = "conservative"
    MEDIUM = "medium"
    AGGRESSIVE = "aggressive"


class OrderSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    FAILED = "failed"
    REJECTED = "rejected"


class ExecutionType(str, enum.Enum):
    PAPER = "paper"
    LIVE = "live"


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    language_code = Column(String(10), nullable=True)
    
    # Trading settings
    risk_level = Column(SQLEnum(RiskLevel), default=RiskLevel.MEDIUM, nullable=False)
    max_allocation_pct = Column(Numeric(5, 2), default=10.0, nullable=False)
    max_concurrent_trades = Column(Integer, default=3, nullable=False)
    trading_mode = Column(SQLEnum(TradeMode), default=TradeMode.PAPER, nullable=False)
    bot_enabled = Column(Boolean, default=False, nullable=False)
    
    # Engine A config
    engine_a_enabled = Column(Boolean, default=True, nullable=False)
    engine_a_price_threshold = Column(Numeric(5, 4), default=0.02)
    engine_a_volume_threshold = Column(Numeric(5, 2), default=3.0)
    engine_a_spread_bps = Column(Integer, default=10)
    engine_a_funding_flip = Column(Boolean, default=True)
    engine_a_min_confidence = Column(Numeric(3, 2), default=0.70)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    credentials = relationship("UserCredential", back_populates="profile", cascade="all, delete-orphan")
    whitelist = relationship("UserWhitelist", back_populates="profile", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="profile", cascade="all, delete-orphan")
    trades = relationship("TradeLog", back_populates="profile", cascade="all, delete-orphan")
    paper_balances = relationship("PaperBalance", back_populates="profile", cascade="all, delete-orphan")
    alerts = relationship("AlertRule", back_populates="profile", cascade="all, delete-orphan")
    execution_audit = relationship("ExecutionAudit", back_populates="profile", cascade="all, delete-orphan")
    risk_settings = relationship("RiskSettings", back_populates="profile", uselist=False, cascade="all, delete-orphan")


class UserCredential(Base):
    __tablename__ = "user_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    exchange = Column(String(20), nullable=False)
    encrypted_api_key = Column(Text, nullable=False)
    encrypted_api_secret = Column(Text, nullable=False)
    encrypted_passphrase = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    profile = relationship("Profile", back_populates="credentials")

    __table_args__ = (UniqueConstraint("profile_id", "exchange", name="uq_profile_exchange"),)


class UserWhitelist(Base):
    __tablename__ = "user_whitelist"

    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    symbol = Column(String(20), primary_key=True)
    exchange = Column(String(20), default="bybit", primary_key=True)
    timeframe = Column(String(10), default="1m", nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    added_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    profile = relationship("Profile", back_populates="whitelist")


class RiskSettings(Base):
    __tablename__ = "risk_settings"

    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    stop_loss_pct = Column(Numeric(5, 2), default=3.0, nullable=False)
    take_profit_pct = Column(Numeric(5, 2), default=6.0, nullable=False)
    trailing_stop_pct = Column(Numeric(5, 2), default=1.0, nullable=False)
    max_allocation_pct = Column(Numeric(5, 2), default=10.0, nullable=False)
    max_concurrent_trades = Column(Integer, default=3, nullable=False)
    max_daily_drawdown_pct = Column(Numeric(5, 2), default=5.0, nullable=False)
    whitelist_only = Column(Boolean, default=True, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    profile = relationship("Profile", back_populates="risk_settings")


class PaperBalance(Base):
    __tablename__ = "paper_balances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    asset = Column(String(10), nullable=False)
    balance = Column(Numeric(20, 8), default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    profile = relationship("Profile", back_populates="paper_balances")

    __table_args__ = (UniqueConstraint("profile_id", "asset", name="uq_profile_asset"),)


class Position(Base):
    __tablename__ = "positions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String(20), nullable=False)
    exchange = Column(String(20), nullable=False)
    side = Column(SQLEnum(OrderSide), nullable=False)
    size = Column(Numeric(20, 8), nullable=False)
    entry_price = Column(Numeric(20, 8), nullable=False)
    current_price = Column(Numeric(20, 8), nullable=False)
    unrealized_pnl = Column(Numeric(20, 8), default=0)
    stop_loss = Column(Numeric(20, 8), nullable=True)
    take_profit = Column(Numeric(20, 8), nullable=True)
    trailing_stop = Column(Numeric(20, 8), nullable=True)
    leverage = Column(Integer, default=1)
    mode = Column(SQLEnum(TradeMode), nullable=False)
    opened_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    profile = relationship("Profile", back_populates="positions")

    __table_args__ = (Index("idx_positions_profile_symbol", "profile_id", "symbol"),)


class TradeLog(Base):
    __tablename__ = "trade_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    symbol = Column(String(20), nullable=False)
    exchange = Column(String(20), nullable=False)
    side = Column(SQLEnum(OrderSide), nullable=False)
    execution_type = Column(SQLEnum(ExecutionType), nullable=False)
    size = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(20, 8), nullable=False)
    total_value_usd = Column(Numeric(20, 2), nullable=False)
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    slippage = Column(Numeric(6, 4), default=0)
    commission = Column(Numeric(20, 8), default=0)
    tx_hash = Column(Text, nullable=True)
    order_id = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    executed_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    profile = relationship("Profile", back_populates="trades")

    __table_args__ = (Index("idx_trades_profile_time", "profile_id", "executed_at"),)


class Signal(Base):
    __tablename__ = "signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engine = Column(String(1), nullable=False, index=True)
    ticker = Column(String(20), nullable=False, index=True)
    category = Column(String(50), nullable=True)
    badge = Column(String(50), nullable=True)
    source = Column(String(100), nullable=False)
    metric = Column(String(100), nullable=True)
    analysis = Column(Text, nullable=True)
    confidence = Column(Integer, nullable=False)
    action_label = Column(String(100), nullable=True)
    kronos_trajectories = Column(JSONB, nullable=True)
    kronos_mean_path = Column(JSONB, nullable=True)
    kronos_confidence_90 = Column(JSONB, nullable=True)
    sentiment_score = Column(Numeric(4, 3), nullable=True)
    mentions_per_hour = Column(Integer, nullable=True)
    liquidity_usd = Column(Numeric(20, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (Index("idx_signals_engine_ticker_time", "engine", "ticker", "created_at"),)


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    metric = Column(String(100), nullable=False)
    condition = Column(String(20), nullable=False)
    value = Column(String(50), nullable=False)
    action = Column(String(200), nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    triggered_at = Column(DateTime(timezone=True), nullable=True)
    trigger_count = Column(Integer, default=0)

    profile = relationship("Profile", back_populates="alerts")


class ExecutionAudit(Base):
    __tablename__ = "execution_audit"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    mode = Column(SQLEnum(TradeMode), nullable=False)
    symbol = Column(String(20), nullable=False)
    side = Column(SQLEnum(OrderSide), nullable=False)
    size = Column(Numeric(20, 8), nullable=False)
    price = Column(Numeric(20, 8), nullable=False)
    sl = Column(Numeric(20, 8), nullable=True)
    tp = Column(Numeric(20, 8), nullable=True)
    kronos_confidence = Column(Integer, nullable=True)
    trigger_type = Column(String(30), nullable=False)
    status = Column(SQLEnum(OrderStatus), nullable=False)
    tx_hash = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)

    profile = relationship("Profile", back_populates="execution_audit")