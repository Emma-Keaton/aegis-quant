from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.core.telegram_auth import get_current_user
from app.models import Profile, UserWhitelist
from app.schemas.whitelist import WhitelistAdd, WhitelistResponse

router = APIRouter(prefix="/api/whitelist", tags=["whitelist"])


@router.get("", response_model=List[WhitelistResponse])
async def get_whitelist(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's Engine A whitelist"""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    wl_result = await db.execute(
        select(UserWhitelist)
        .where(UserWhitelist.profile_id == profile.id)
        .where(UserWhitelist.active == True)
    )
    whitelist = wl_result.scalars().all()
    return [
        WhitelistResponse(
            symbol=w.symbol,
            exchange=w.exchange,
            timeframe=w.timeframe,
            active=w.active,
            added_at=w.added_at
        )
        for w in whitelist
    ]


@router.post("", response_model=WhitelistResponse)
async def add_to_whitelist(
    payload: WhitelistAdd,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add symbol to Engine A whitelist"""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Check if already exists
    existing_result = await db.execute(
        select(UserWhitelist)
        .where(UserWhitelist.profile_id == profile.id)
        .where(UserWhitelist.symbol == payload.symbol.upper())
        .where(UserWhitelist.exchange == payload.exchange)
    )
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        if existing.active:
            raise HTTPException(status_code=400, detail=f"{payload.symbol} already in whitelist")
        existing.active = True
        await db.commit()
        return WhitelistResponse.model_validate(existing)
    
    whitelist_item = UserWhitelist(
        profile_id=profile.id,
        symbol=payload.symbol.upper(),
        exchange=payload.exchange,
        timeframe=payload.timeframe,
        active=True
    )
    db.add(whitelist_item)
    await db.commit()
    await db.refresh(whitelist_item)
    
    return WhitelistResponse.model_validate(whitelist_item)


@router.delete("/{symbol}")
async def remove_from_whitelist(
    symbol: str,
    exchange: str = "bybit",
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove symbol from Engine A whitelist (soft delete)"""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    wl_result = await db.execute(
        select(UserWhitelist)
        .where(UserWhitelist.profile_id == profile.id)
        .where(UserWhitelist.symbol == symbol.upper())
        .where(UserWhitelist.exchange == exchange)
    )
    whitelist_item = wl_result.scalar_one_or_none()
    
    if not whitelist_item:
        raise HTTPException(status_code=404, detail="Symbol not in whitelist")
    
    whitelist_item.active = False
    await db.commit()
    
    return {"message": f"Removed {symbol} from whitelist", "symbol": symbol.upper()}