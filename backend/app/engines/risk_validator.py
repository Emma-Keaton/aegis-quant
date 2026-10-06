"""Risk Validator - Validates trades against risk parameters"""

from dataclasses import dataclass
from typing import Optional
from decimal import Decimal

from app.models import Profile, RiskSettings
from app.core.math_helpers import (
    validate_trade_risk,
    calculate_position_size,
    kelly_criterion
)
from app.services.kronos_service import get_kronos_client


@dataclass
class RiskCheckResult:
    approved: bool
    reason: str
    side: str
    size: float
    stop_loss: Optional[float]
    take_profit: Optional[float]


class RiskValidator:
    """Validates trades against user risk settings and portfolio state"""

    async def validate(
        self,
        profile: Profile,
        symbol: str,
        signal_confidence: int,
        current_price: float,
        risk_settings: Optional[RiskSettings] = None,
        candles: Optional[list] = None,
    ) -> RiskCheckResult:
        """
        Validate a potential trade against all risk parameters.

        `candles`: optional recent OHLCV list; when present, SL/TP are
        ATR-based (adaptive to current vol) instead of fixed percentages.
        Returns RiskCheckResult with approved status and trade parameters.
        """
        # Get risk settings
        if risk_settings is None:
            from app.database import AsyncSessionLocal
            from sqlalchemy import select
            from app.models import RiskSettings as RSS
            
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(RSS).where(RSS.profile_id == profile.id)
                )
                risk_settings = result.scalar_one_or_none()
        
        if not risk_settings:
            # Use defaults from profile
            risk_settings = type('obj', (object,), {
                'stop_loss_pct': float(profile.max_allocation_pct) * 0.3,
                'take_profit_pct': float(profile.max_allocation_pct) * 0.6,
                'trailing_stop_pct': float(profile.max_allocation_pct) * 0.1,
                'max_allocation_pct': float(profile.max_allocation_pct),
                'max_concurrent_trades': profile.max_concurrent_trades,
                'max_daily_drawdown_pct': 5.0,
                'whitelist_only': True
            })()
        
        # 0. Reject unusable prices — a zero/absent price would divide by zero
        # below and would otherwise send a zero-size order to the venue.
        if not current_price or current_price <= 0:
            return RiskCheckResult(
                approved=False,
                reason="Invalid current price",
                side="buy",
                size=0,
                stop_loss=None,
                take_profit=None
            )

        if risk_settings.stop_loss_pct <= 0:
            return RiskCheckResult(
                approved=False,
                reason="stop_loss_pct must be greater than zero",
                side="buy",
                size=0,
                stop_loss=None,
                take_profit=None
            )

        # 1. Check max concurrent trades (open positions only — closed rows
        # must never count against the cap).
        from app.database import AsyncSessionLocal
        from sqlalchemy import select
        from app.models import Position

        async with AsyncSessionLocal() as db:
            pos_result = await db.execute(
                select(Position).where(
                    Position.profile_id == profile.id,
                    Position.is_closed.is_(False),
                )
            )
            open_positions = pos_result.scalars().all()
        
        if len(open_positions) >= risk_settings.max_concurrent_trades:
            return RiskCheckResult(
                approved=False,
                reason=f"Max concurrent trades ({risk_settings.max_concurrent_trades}) reached",
                side="buy",
                size=0,
                stop_loss=None,
                take_profit=None
            )
        
        # 2. Check whitelist if enabled
        if risk_settings.whitelist_only:
            from app.models import UserWhitelist
            async with AsyncSessionLocal() as db:
                wl_result = await db.execute(
                    select(UserWhitelist).where(
                        UserWhitelist.profile_id == profile.id,
                        UserWhitelist.symbol == symbol.replace("USDT", "").replace("USD", ""),
                        UserWhitelist.active == True
                    )
                )
                if not wl_result.scalar_one_or_none():
                    return RiskCheckResult(
                        approved=False,
                        reason=f"{symbol} not in whitelist",
                        side="buy",
                        size=0,
                        stop_loss=None,
                        take_profit=None
                    )
        
        # 3. Calculate position size using Kelly + allocation limits
        balance = await self._get_balance(profile)
        
        # Use signal confidence as win probability proxy
        win_prob = signal_confidence / 100
        win_loss_ratio = risk_settings.take_profit_pct / risk_settings.stop_loss_pct
        
        kelly_fraction = kelly_criterion(win_prob, win_loss_ratio)
        position_size = calculate_position_size(
            balance=balance,
            max_allocation_pct=float(risk_settings.max_allocation_pct),
            risk_pct=float(risk_settings.max_allocation_pct),  # Use allocation as risk cap
            confidence=win_prob,
            entry_price=current_price,
            stop_loss=current_price * (1 - risk_settings.stop_loss_pct / 100)
        )
        
        # Apply Kelly fraction as additional constraint
        max_kelly_size = balance * kelly_fraction / current_price
        final_size = min(position_size, max_kelly_size)
        
        if final_size <= 0:
            return RiskCheckResult(
                approved=False,
                reason="Calculated position size is zero",
                side="buy",
                size=0,
                stop_loss=None,
                take_profit=None
            )
        
        # 4. Calculate SL/TP
        side = "buy"  # Default to long for now
        stop_loss = current_price * (1 - risk_settings.stop_loss_pct / 100)
        take_profit = current_price * (1 + risk_settings.take_profit_pct / 100)
        # ATR-adaptive levels when candles are available (Engine A enrichment).
        if candles:
            try:
                import pandas as pd
                from app.core.indicators import atr_levels
                df = pd.DataFrame(candles)
                atr_lvl = atr_levels(df, side=side)
                if atr_lvl:
                    stop_loss = float(atr_lvl["stop_loss"])
                    take_profit = float(atr_lvl["take_profit"])
            except Exception:
                pass  # fall back to pct-based SL/TP
        
        # 5. Validate with comprehensive risk check
        risk_check = validate_trade_risk(
            balance=balance,
            position_size=final_size,
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            max_allocation_pct=float(risk_settings.max_allocation_pct),
            max_drawdown_pct=float(risk_settings.max_daily_drawdown_pct),
            current_drawdown=await self._get_current_drawdown(profile),
            open_positions=len(open_positions),
            max_concurrent=risk_settings.max_concurrent_trades
        )
        
        if not risk_check["approved"]:
            return RiskCheckResult(
                approved=False,
                reason=risk_check["reason"],
                side=side,
                size=0,
                stop_loss=None,
                take_profit=None
            )
        
        # Use adjusted size from risk check
        final_size = risk_check.get("adjusted_size", final_size)
        
        return RiskCheckResult(
            approved=True,
            reason="Risk checks passed",
            side=side,
            size=final_size,
            stop_loss=stop_loss,
            take_profit=take_profit
        )
    
    async def _get_balance(self, profile: Profile) -> float:
        """Get available balance (paper or live)"""
        from app.database import AsyncSessionLocal
        from app.models import PaperBalance
        from sqlalchemy import select
        
        async with AsyncSessionLocal() as db:
            from sqlalchemy import func
            total = (await db.execute(
                select(func.coalesce(func.sum(PaperBalance.balance), 0))
                .where(PaperBalance.profile_id == profile.id)
            )).scalar()
            if total is not None:
                return float(total)
        return 10000.0  # Default paper balance
    
    async def _get_current_drawdown(self, profile: Profile) -> float:
        """Current daily drawdown as a percentage of available equity.

        Measured as the sum of negative unrealized PnL on positions touched
        today, divided by the account's available balance. Closed trade logs
        carry no realized PnL column, so open-position losses are the only
        faithful drawdown signal available here.
        """
        from app.database import AsyncSessionLocal
        from app.models import Position
        from sqlalchemy import select, func
        from datetime import datetime, timezone

        async with AsyncSessionLocal() as db:
            today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            result = await db.execute(
                select(func.coalesce(func.sum(Position.unrealized_pnl), 0))
                .where(Position.profile_id == profile.id)
                .where(Position.is_closed.is_(False))
                .where(Position.updated_at >= today_start)
            )
            open_pnl = float(result.scalar() or 0)

        if open_pnl >= 0:
            return 0.0
        equity = await self._get_balance(profile) or 10000.0
        return min(abs(open_pnl) / equity * 100.0, 100.0)