from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.telegram_auth import get_current_user
from app.models import Profile, UserWhitelist, RiskSettings

router = APIRouter()


@router.get("/state")
async def get_user_state(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get complete user dashboard state"""
    telegram_id = user["id"]
    
    # Get or create profile
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        profile = Profile(
            telegram_id=telegram_id,
            risk_level="medium",
            max_allocation_pct=10.0,
            max_concurrent_trades=3,
            trading_mode="paper",
            bot_enabled=False,
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    
    # Get whitelist
    wl_result = await db.execute(
        select(UserWhitelist).where(UserWhitelist.user_id == profile.id)
    )
    whitelist = [w.symbol for w in wl_result.scalars().all()]
    
    # Get risk settings
    risk_result = await db.execute(
        select(RiskSettings).where(RiskSettings.profile_id == profile.id)
    )
    risk_settings = risk_result.scalar_one_or_none()
    
    return {
        "profile": {
            "telegram_id": profile.telegram_id,
            "risk_level": profile.risk_level,
            "max_allocation_pct": profile.max_allocation_pct,
            "max_concurrent_trades": profile.max_concurrent_trades,
            "trading_mode": profile.trading_mode,
            "bot_enabled": profile.bot_enabled,
        },
        "whitelist": whitelist,
        "risk_settings": {
            "stop_loss_pct": risk_settings.stop_loss_pct if risk_settings else 3.0,
            "take_profit_pct": risk_settings.take_profit_pct if risk_settings else 6.0,
            "trailing_stop_pct": risk_settings.trailing_stop_pct if risk_settings else 1.0,
        } if risk_settings else {}
    }


@router.patch("/state/mode")
async def toggle_trading_mode(
    mode: str,  # "paper" or "live"
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Toggle paper/live trading mode"""
    if mode not in ["paper", "live"]:
        return {"error": "Invalid mode. Use 'paper' or 'live'"}
    
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        return {"error": "Profile not found"}
    
    profile.trading_mode = mode
    await db.commit()
    
    return {"trading_mode": mode, "message": f"Switched to {mode} trading"}


@router.patch("/state/bot")
async def toggle_bot(
    enabled: bool,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Enable/disable trading bot"""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        return {"error": "Profile not found"}
    
    profile.bot_enabled = enabled
    await db.commit()
    
    return {"bot_enabled": enabled, "message": f"Bot {'enabled' if enabled else 'disabled'}"}