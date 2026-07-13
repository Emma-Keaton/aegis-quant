from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.core.telegram_auth import get_current_user
from app.models import Profile, Signal
from app.schemas.signals import SignalResponse, SignalListResponse

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=SignalListResponse)
async def get_signals(
    engine: Optional[str] = None,
    limit: int = 20,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get combined Engine A + B signals"""
    query = select(Signal).order_by(Signal.created_at.desc()).limit(limit)
    
    if engine:
        query = query.where(Signal.engine == engine.upper())
    
    result = await db.execute(query)
    signals = result.scalars().all()
    
    return SignalListResponse(
        signals=[SignalResponse.model_validate(s) for s in signals],
        count=len(signals)
    )


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(
    signal_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get single signal by ID"""
    from sqlalchemy import select
    import uuid
    
    result = await db.execute(
        select(Signal).where(Signal.id == uuid.UUID(signal_id))
    )
    signal = result.scalar_one_or_none()
    
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    
    return SignalResponse.model_validate(signal)