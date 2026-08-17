"""Pre-trade prerequisites check (paper | live).

Used by every execution route (API, copy-trade, bot, Engine A) so that no trade —
paper or live — is placed before its prerequisites are satisfied. Paper trades
need only a positive paper balance; live trades additionally require the agent to
be enabled, Spot & Margin permission, and a funded/connected venue.
"""
from __future__ import annotations

import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Profile, RiskSettings, PaperBalance, UserCredential, TradeMode,
)

logger = logging.getLogger(__name__)


class TradePrerequisitesError(Exception):
    """Raised when trade prerequisites are not satisfied (for direct execution)."""

    def __init__(self, reasons: List[str]):
        self.reasons = reasons
        super().__init__("; ".join(reasons))


async def collect_prerequisites(
    db: AsyncSession, profile: Profile
) -> List[str]:
    """Return a list of unmet prerequisite reasons. Empty list == ready to trade."""
    reasons: List[str] = []

    if profile is None:
        return ["No trading profile"]

    mode = profile.trading_mode.value if hasattr(profile.trading_mode, "value") else str(profile.trading_mode)

    # ---- Common prerequisites (paper + live) ----
    # Concurrency ceiling from RiskSettings (fallback to profile default).
    try:
        rs_result = await db.execute(
            select(RiskSettings).where(RiskSettings.profile_id == profile.id)
        )
        rs = rs_result.scalar_one_or_none()
    except Exception:
        rs = None
    max_concurrent = int(rs.max_concurrent_trades) if (rs and rs.max_concurrent_trades) else int(profile.max_concurrent_trades or 3)

    from app.models import Position
    try:
        pos_result = await db.execute(
            select(Position).where(Position.profile_id == profile.id)
        )
        open_positions = pos_result.scalars().all()
    except Exception:
        open_positions = []
    if len(open_positions) >= max_concurrent:
        reasons.append(f"Max concurrent trades ({max_concurrent}) reached")

    # ---- Paper mode prerequisites (paper balance > 0) ----
    if mode == TradeMode.PAPER.value:
        try:
            pb_result = await db.execute(
                select(PaperBalance).where(PaperBalance.profile_id == profile.id)
            )
            pb = pb_result.scalar_one_or_none()
        except Exception:
            pb = None
        balance = float(pb.balance) if (pb and pb.balance is not None) else 0.0
        if balance <= 0:
            reasons.append("Paper balance is 0 — set a paper trading balance in Settings")
        return reasons

    # ---- Live mode prerequisites ----
    if mode == TradeMode.LIVE.value:
        if not profile.bot_enabled:
            reasons.append("Live trading is not enabled (toggle the agent ON)")
        if rs is not None and not rs.spot_margin_enabled:
            reasons.append("Spot & margin trading is disabled in Risk Settings")
        # Live CEX requires active API credentials for at least one exchange.
        if not profile.wallet_connected:
            try:
                cred_result = await db.execute(
                    select(UserCredential).where(
                        UserCredential.profile_id == profile.id,
                        UserCredential.is_active == True,
                    )
                )
                creds = cred_result.scalars().all()
            except Exception:
                creds = []
            if not creds:
                reasons.append(
                    "Live trading needs a connected wallet (TON/Solana) or CEX API keys"
                )
        return reasons

    reasons.append(f"Unknown trading mode: {mode}")
    return reasons


async def assert_prerequisites(db: AsyncSession, profile: Profile) -> None:
    """Raise TradePrerequisitesError if prerequisites are not met."""
    reasons = await collect_prerequisites(db, profile)
    if reasons:
        raise TradePrerequisitesError(reasons)