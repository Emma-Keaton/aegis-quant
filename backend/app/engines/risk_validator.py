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
from app.engines.kronos_client import KronosClient


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
    
    def __init__(self):
        self.kronos = KronosClient()
    
    async def validate(
        self,
        profile: Profile,
        symbol: str,
        signal_confidence: int,
        current_price: float,
        risk_settings: Optional[RiskSettings] = None
    ) -> RiskCheckResult:
        """
        Validate a potential trade against all risk parameters.
        
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
        
        # 1. Check max concurrent trades
        from app.database import AsyncSessionLocal
        from sqlalchemy import select
        from app.models import Position
        
        async with AsyncSessionLocal() as db:
            pos_result = await db.execute(
                select(Position).where(Position.profile_id == profile.id)
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
        # TODO: Implement actual balance fetching
        # For paper trading, return from paper_balances table
        # For live, fetch from exchange
        return 10000.0  # Default paper balance
    
    async def _get_current_drawdown(self, profile: Profile) -> float:
        """Calculate current daily drawdown percentage"""
        # TODO: Implement from trade_logs
        return 0.0