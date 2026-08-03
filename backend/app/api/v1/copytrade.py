"""Copy-trade channel management — register, list, update, unsubscribe channels."""

import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.telegram_auth import get_current_user
from app.database import get_db
from app.models import CopyTradeSubscription, Profile, Profile as ProfileType

router = APIRouter(prefix="/copytrade", tags=["copy-trading"])


@router.post("/channels/register")
async def register_channel(
    request: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Register a Telegram channel for copy-trading."""
    channel_id = request.get("channelId") or request.get("channel_id")
    confidence_threshold = request.get("confidenceThreshold") or request.get("confidence_threshold", 70)
    
    if not channel_id:
        raise HTTPException(status_code=400, detail="channelId is required")
    
    threshold = int(confidence_threshold)
    if not (0 <= threshold <= 100):
        raise HTTPException(status_code=400, detail="confidenceThreshold must be 0-100")
    
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Upsert
    existing = await db.execute(
        select(CopyTradeSubscription)
        .where(CopyTradeSubscription.profile_id == profile.id)
        .where(CopyTradeSubscription.channel_id == channel_id)
    )
    sub = existing.scalar_one_or_none()
    
    if sub:
        sub.confidence_threshold = threshold
        sub.updated_at = datetime.now(timezone.utc)
    else:
        sub = CopyTradeSubscription(
            profile_id=profile.id,
            channel_id=channel_id,
            confidence_threshold=threshold,
            active=True,
        )
        db.add(sub)
    
    await db.commit()
    await db.refresh(sub)
    
    return {
        "status": "success",
        "channelId": sub.channel_id,
        "confidenceThreshold": sub.confidence_threshold,
    }


@router.get("/channels")
async def list_channels(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all registered copy-trade channels."""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    subs = await db.execute(
        select(CopyTradeSubscription)
        .where(CopyTradeSubscription.profile_id == profile.id)
        .where(CopyTradeSubscription.active == True)
    )
    channels = subs.scalars().all()
    
    return {
        "status": "success",
        "data": [
            {
                "channelId": c.channel_id,
                "confidenceThreshold": c.confidence_threshold,
                "active": c.active,
                "createdAt": c.created_at.isoformat(),
            }
            for c in channels
        ]
    }


@router.patch("/channels/update")
async def update_channel(
    request: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a channel's confidence threshold."""
    channel_id = request.get("channelId") or request.get("channel_id")
    confidence_threshold = request.get("confidenceThreshold") or request.get("confidence_threshold")
    
    if not channel_id or confidence_threshold is None:
        raise HTTPException(status_code=400, detail="channelId and confidenceThreshold required")
    
    threshold = int(confidence_threshold)
    if not (0 <= threshold <= 100):
        raise HTTPException(status_code=400, detail="Invalid confidenceThreshold")
    
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    sub_result = await db.execute(
        select(CopyTradeSubscription)
        .where(CopyTradeSubscription.profile_id == profile.id)
        .where(CopyTradeSubscription.channel_id == channel_id)
    )
    sub = sub_result.scalar_one_or_none()
    
    if not sub:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    sub.confidence_threshold = threshold
    sub.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(sub)
    
    return {
        "status": "success",
        "channelId": sub.channel_id,
        "confidenceThreshold": sub.confidence_threshold,
    }


@router.delete("/channels/unregister")
async def unregister_channel(
    request: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Unsubscribe from a copy-trade channel."""
    channel_id = request.get("channelId") or request.get("channel_id")
    
    if not channel_id:
        raise HTTPException(status_code=400, detail="channelId required")
    
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    sub_result = await db.execute(
        select(CopyTradeSubscription)
        .where(CopyTradeSubscription.profile_id == profile.id)
        .where(CopyTradeSubscription.channel_id == channel_id)
    )
    sub = sub_result.scalar_one_or_none()
    
    if not sub:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    sub.active = False
    await db.commit()
    
    return {"status": "success", "channelId": channel_id}


@router.post("/channels/run")
async def run_copytrade_scan(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger a copy-trade signal scan (for testing)."""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    subs = await db.execute(
        select(CopyTradeSubscription)
        .where(CopyTradeSubscription.profile_id == profile.id)
        .where(CopyTradeSubscription.active == True)
    )
    channels = subs.scalars().all()
    
    return {
        "status": "success",
        "channelsScanned": len(channels),
        "results": []
    }
