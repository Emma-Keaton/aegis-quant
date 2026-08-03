import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    Column, String, Integer, BigInteger, Boolean, DateTime, Numeric, Text, JSON, ForeignKey, Enum as SQLEnum, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base
import enum


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
    """User profile - one per Telegram chat_id"""
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
    trade_mode = Column(SQLEnum(TradeMode), default=TradeMode.PAPER, nullable=False)
    bot_enabled = Column(Boolean, default=False, nullable=False)
    
    # Engine A config
    engine_a_enabled = Column(Boolean, default=True, nullable=False)
    engine_a_price_threshold = Column(Numeric(5, 4), default=0.02)  # 2%
    engine_a_volume_threshold = Column(Numeric(5, 2), default=3.0)   # 3x
    engine_a_spread_bps = Column(Integer, default=10)                # 10 bps
    engine_a_funding_flip = Column(Boolean, default=True)
    engine_a_min_confidence = Column(Numeric(3, 2), default=0.70)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Wallet
    wallet_connected = Column(Boolean, default=False, nullable=False)
    wallet_address = Column(String(64), nullable=True)
    wallet_network = Column(String(10), nullable=True)
    wallet_public_key = Column(String(128), nullable=True)
    
    # Engine B config
    engine_b_enabled = Column(Boolean, default=True, nullable=False)
    engine_b_min_confidence = Column(Numeric(3, 2), default=0.70)
    
    # Relationships
    credentials = relationship("UserCredential", back_populates="profile", cascade="all, delete-orphan")
    whitelist = relationship("UserWhitelist", back_populates="profile", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="profile", cascade="all, delete-orphan")
    trades = relationship("TradeLog", back_populates="profile", cascade="all, delete-orphan")
    paper_balances = relationship("PaperBalance", back_populates="profile", cascade="all, delete-orphan")
    alerts = relationship("AlertRule", back_populates="profile", cascade="all, delete-orphan")
    execution_audit = relationship("ExecutionAudit", back_populates="profile", cascade="all, delete-orphan")
    copytrade_subscriptions = relationship(
        "CopyTradeSubscription", back_populates="profile", cascade="all, delete-orphan"
    )


class UserCredential(Base):
    """Encrypted CEX API credentials"""
    __tablename__ = "user_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    exchange = Column(String(20), nullable=False)  # bybit, okx, binance
    encrypted_api_key = Column(Text, nullable=False)
    encrypted_api_secret = Column(Text, nullable=False)
    encrypted_passphrase = Column(Text, nullable=True)  # For OKX
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    profile = relationship("Profile", back_populates="credentials")

    __table_args__ = (UniqueConstraint("profile_id", "exchange", name="uq_profile_exchange"),)


class UserWhitelist(Base):
    """Engine A whitelist - CRUDable from frontend"""
    __tablename__ = "user_whitelist"

    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), primary_key=True)
    symbol = Column(String(20), primary_key=True)  # e.g., "BTC", "SOL"
    exchange = Column(String(20), default="bybit", primary_key=True)
    timeframe = Column(String(10), default="1m", nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    added_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    profile = relationship("Profile", back_populates="whitelist")


class PaperBalance(Base):
    """Paper trading balances per asset"""
    __tablename__ = "paper_balances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    asset = Column(String(10), nullable=False)
    balance = Column(Numeric(20, 8), default=0, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    profile = relationship("Profile", back_populates="paper_balances")

    __table_args__ = (UniqueConstraint("profile_id", "asset", name="uq_profile_asset"),)


class Position(Base):
    """Current open positions"""
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
    """Unified trade execution log (paper + live)"""
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
    order_id = Column(String(50), nullable=True)  # CEX order ID
    error_message = Column(Text, nullable=True)
    executed_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    profile = relationship("Profile", back_populates="trades")

    __table_args__ = (Index("idx_trades_profile_time", "profile_id", "executed_at"),)


class Signal(Base):
    """Engine A/B signals with Kronos forecast"""
    __tablename__ = "signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    engine = Column(String(1), nullable=False)  # 'A' or 'B'
    ticker = Column(String(20), nullable=False, index=True)
    category = Column(String(50), nullable=True)
    badge = Column(String(50), nullable=True)
    source = Column(String(100), nullable=False)
    metric = Column(String(100), nullable=True)
    analysis = Column(Text, nullable=True)
    confidence = Column(Integer, nullable=False)  # 0-100
    action_label = Column(String(100), nullable=True)
    
    # Kronos forecast data (Engine A only)
    kronos_trajectories = Column(JSONB, nullable=True)
    kronos_mean_path = Column(JSONB, nullable=True)
    kronos_confidence_90 = Column(JSONB, nullable=True)
    
    # Social data (Engine B only)
    sentiment_score = Column(Numeric(4, 3), nullable=True)
    mentions_per_hour = Column(Integer, nullable=True)
    liquidity_usd = Column(Numeric(20, 2), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (Index("idx_signals_engine_ticker_time", "engine", "ticker", "created_at"),)


class AlertRule(Base):
    """User-defined alert rules"""
    __tablename__ = "alert_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    metric = Column(String(100), nullable=False)
    condition = Column(String(20), nullable=False)  # >, <, >=, <=, ==, crosses_above, crosses_below
    value = Column(String(50), nullable=False)
    action = Column(String(200), nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    triggered_at = Column(DateTime(timezone=True), nullable=True)
    trigger_count = Column(Integer, default=0)

    profile = relationship("Profile", back_populates="alerts")


class ExecutionAudit(Base):
    """Immutable audit trail for every execution attempt"""
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
    trigger_type = Column(String(30), nullable=False)  # ws_price, ws_volume, ws_spread, ws_funding, scheduled
    status = Column(SQLEnum(OrderStatus), nullable=False)
    tx_hash = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False, index=True)

    profile = relationship("Profile", back_populates="execution_audit")

    __table_args__ = (Index("idx_audit_profile_time", "profile_id", "created_at"),)


class RiskSettings(Base):
    """User risk management settings"""
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


class UserSession(Base):
    """Authentication session — tied to telegram_id."""
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_id = Column(BigInteger, nullable=False, index=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=True)
    token = Column(String(512), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    profile = relationship("Profile")


class CopyTradeSubscription(Base):
    """User's subscription to a Telegram channel for copy-trading signals."""
    __tablename__ = "copytrade_subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    channel_id = Column(String(50), nullable=False, index=True)
    confidence_threshold = Column(Integer, default=70, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    
    profile = relationship("Profile", back_populates="copytrade_subscriptions")
    
    __table_args__ = (
        UniqueConstraint("profile_id", "channel_id", name="uq_profile_channel_sub"),
    )


# BigInteger import
from sqlalchemy import BigInteger