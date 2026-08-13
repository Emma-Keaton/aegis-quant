from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, List, Literal

from app.database import get_db
from app.core.telegram_auth import get_current_user
from app.models import Profile, RiskSettings, TradeMode

router = APIRouter(prefix="/api/risk", tags=["risk"])


class RiskSettingsUpdate(BaseModel):
    stop_loss_pct: Optional[float] = Field(None, ge=0.1, le=20.0)
    take_profit_pct: Optional[float] = Field(None, ge=0.1, le=50.0)
    trailing_stop_pct: Optional[float] = Field(None, ge=0.1, le=10.0)
    max_allocation_pct: Optional[float] = Field(None, ge=1.0, le=50.0)
    max_concurrent_trades: Optional[int] = Field(None, ge=1, le=20)
    max_daily_drawdown_pct: Optional[float] = Field(None, ge=1.0, le=20.0)
    whitelist_only: Optional[bool] = None
    base_trade_usd: Optional[float] = Field(None, ge=0.1, le=1000.0)
    spot_margin_enabled: Optional[bool] = None


class RiskSettingsResponse(BaseModel):
    stop_loss_pct: float
    take_profit_pct: float
    trailing_stop_pct: float
    max_allocation_pct: float
    max_concurrent_trades: int
    max_daily_drawdown_pct: float
    whitelist_only: bool
    base_trade_usd: float
    spot_margin_enabled: bool
    updated_at: str
    
    class Config:
        from_attributes = True


@router.get("", response_model=RiskSettingsResponse)
async def get_risk_settings(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's risk settings"""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    risk_result = await db.execute(
        select(RiskSettings).where(RiskSettings.profile_id == profile.id)
    )
    risk_settings = risk_result.scalar_one_or_none()
    
    if not risk_settings:
        # Create default
        risk_settings = RiskSettings(profile_id=profile.id)
        db.add(risk_settings)
        await db.commit()
        await db.refresh(risk_settings)
    
    return RiskSettingsResponse.model_validate(risk_settings)


@router.patch("", response_model=RiskSettingsResponse)
async def update_risk_settings(
    updates: RiskSettingsUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update risk settings"""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    risk_result = await db.execute(
        select(RiskSettings).where(RiskSettings.profile_id == profile.id)
    )
    risk_settings = risk_result.scalar_one_or_none()
    
    if not risk_settings:
        risk_settings = RiskSettings(profile_id=profile.id)
        db.add(risk_settings)
    
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(risk_settings, key, value)
    
    # Also update profile-level settings if provided
    if updates.max_allocation_pct is not None:
        profile.max_allocation_pct = updates.max_allocation_pct
    if updates.max_concurrent_trades is not None:
        profile.max_concurrent_trades = updates.max_concurrent_trades
    
    await db.commit()
    await db.refresh(risk_settings)
    
    return RiskSettingsResponse.model_validate(risk_settings)


class RiskProfile(BaseModel):
    risk_level: Literal["conservative", "medium", "aggressive"] = "medium"


@router.post("/preset")
async def apply_risk_preset(
    preset: RiskProfile,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Apply risk preset (conservative/medium/aggressive)"""
    presets = {
        "conservative": {
            "stop_loss_pct": 1.5,
            "take_profit_pct": 3.0,
            "trailing_stop_pct": 0.5,
            "max_allocation_pct": 5.0,
            "max_concurrent_trades": 2,
            "max_daily_drawdown_pct": 3.0,
        },
        "medium": {
            "stop_loss_pct": 3.0,
            "take_profit_pct": 6.0,
            "trailing_stop_pct": 1.0,
            "max_allocation_pct": 10.0,
            "max_concurrent_trades": 3,
            "max_daily_drawdown_pct": 5.0,
        },
        "aggressive": {
            "stop_loss_pct": 5.0,
            "take_profit_pct": 10.0,
            "trailing_stop_pct": 2.0,
            "max_allocation_pct": 15.0,
            "max_concurrent_trades": 5,
            "max_daily_drawdown_pct": 8.0,
        }
    }
    
    settings = presets.get(preset.risk_level)
    if not settings:
        raise HTTPException(status_code=400, detail="Invalid risk level")
    
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    risk_result = await db.execute(
        select(RiskSettings).where(RiskSettings.profile_id == profile.id)
    )
    risk_settings = risk_result.scalar_one_or_none()
    
    if not risk_settings:
        risk_settings = RiskSettings(profile_id=profile.id)
        db.add(risk_settings)
    
    for key, value in settings.items():
        setattr(risk_settings, key, value)
    
    profile.risk_level = preset.risk_level
    profile.max_allocation_pct = settings["max_allocation_pct"]
    profile.max_concurrent_trades = settings["max_concurrent_trades"]
    
    await db.commit()
    await db.refresh(risk_settings)
    
    return {"message": f"Applied {preset.risk_level} risk profile", "settings": settings}