"""Unified execution for parsed signals (copy-trade, bot, chat).

Loads the profile, routes the order through `ExecutionRouter` (which handles
paper-balance debits, live CCXT fills, and the Spot & Margin gate), then
persists a `Signal` (so Intel renders it as a card) plus a `TradeLog` and
`Position` so `/api/state` reflects the open position.
"""
import logging
from decimal import Decimal

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import (
    Profile, Position, TradeLog, Signal, OrderSide, OrderStatus,
    ExecutionType, TradeMode, RiskSettings,
)
from app.engines.execution_router import ExecutionRouter
from app.core.exceptions import AegisQuantError

logger = logging.getLogger(__name__)


async def execute_parsed_signal(profile_id, parsed: dict, source: str = "copy-trade") -> dict:
    """Execute a parsed signal and persist it as an Intel card + log + position."""
    async with AsyncSessionLocal() as db:
        profile = await db.get(Profile, profile_id)
        if not profile:
            return {"executed": False, "reason": "Profile not found", "signal": parsed}

        symbol = str(parsed.get("symbol") or "").upper().lstrip("$")
        side = str(parsed.get("side") or "").lower()
        confidence = int(parsed.get("confidence") or 0)
        price = parsed.get("price")
        if not symbol or side not in ("buy", "sell"):
            return {"executed": False, "reason": "Missing symbol or side", "signal": parsed}

        # Live trading must be explicitly enabled.
        if profile.trading_mode == TradeMode.LIVE and not profile.bot_enabled:
            return {"executed": False, "reason": "Live trading not enabled", "signal": parsed}

        size = float(parsed.get("size") or 0)
        if size <= 0:
            rs_result = await db.execute(
                select(RiskSettings).where(RiskSettings.profile_id == profile.id)
            )
            rs = rs_result.scalar_one_or_none()
            size = float(rs.base_trade_usd) if rs and rs.base_trade_usd else 10.0

        router = ExecutionRouter()
        # Route to a DEX venue based on the connected wallet (live only).
        exchange_type = "centralized"
        wallet_address = None
        net = (profile.wallet_network or "").lower() if profile.wallet_network else ""
        if profile.trading_mode == TradeMode.LIVE and profile.wallet_address:
            if "sol" in net:
                exchange_type = "solana"
            elif net in ("ton", "toncoin"):
                exchange_type = "ton"
            if exchange_type != "centralized":
                wallet_address = profile.wallet_address

        try:
            result = await router.execute(
                profile=profile,
                symbol=f"{symbol}/USDT",
                side=side,
                size=size,
                price=float(price) if price else 0,
                stop_loss=None,
                take_profit=None,
                mode=profile.trading_mode.value,
                exchange_type=exchange_type,
                wallet_address=wallet_address,
            )
        except AegisQuantError as e:
            return {"executed": False, "reason": str(e), "signal": parsed}

        fill_price = float(result.price) if result and result.price else float(price or 0)

        # Persist a Signal so it shows on Intel (convergence + agent-actions).
        sig = Signal(
            profile_id=profile.id,
            engine="B",
            ticker=f"${symbol}",
            category="social",
            badge=f"{confidence}% CONFIDENCE",
            source=source,
            metric="Parsed channel message",
            analysis=str(parsed.get("reason") or ""),
            confidence=confidence,
            action_label=f"AGENT {side.upper()} {symbol}",
            sentiment_score=Decimal(str(parsed.get("sentiment", 0.0))),
            mentions_per_hour=None,
            liquidity_usd=None,
        )
        db.add(sig)

        trade_log = TradeLog(
            profile_id=profile.id,
            symbol=symbol,
            exchange=source,
            side=OrderSide(side),
            execution_type=ExecutionType(profile.trading_mode.value),
            size=size,
            price=fill_price,
            total_value_usd=size * fill_price,
            status=OrderStatus.FILLED if profile.trading_mode == TradeMode.PAPER else OrderStatus.PENDING,
        )
        db.add(trade_log)

        position = Position(
            profile_id=profile.id,
            symbol=symbol,
            exchange=source,
            side=OrderSide(side),
            size=size,
            entry_price=fill_price,
            current_price=fill_price,
            mode=profile.trading_mode,
        )
        db.add(position)

        await db.commit()

        logger.info(
            "Executed %s %s %s (%s) via %s → %s",
            side, size, symbol, source, profile.trading_mode.value,
            result.order_id if result else "n/a",
        )
        return {
            "executed": bool(result and result.executed),
            "symbol": symbol,
            "side": side,
            "size": size,
            "confidence": confidence,
            "order_id": result.order_id if result else None,
        }