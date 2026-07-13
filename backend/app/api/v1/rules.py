from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, List, Literal

from app.database import get_db
from app.core.telegram_auth import get_current_user
from app.models import Profile, AlertRule

router = APIRouter(prefix="/rules", tags=["rules"])


class AlertRuleCreate(BaseModel):
    metric: str = Field(..., description="Metric to monitor (e.g., 'Portfolio Drawdown', 'RSI (14) SOL')")
    condition: str = Field(..., description="Condition: >, <, >=, <=, ==, crosses_above, crosses_below")
    value: str = Field(..., description="Threshold value")
    action: str = Field(..., description="Action to take (e.g., 'Pause TON Grid Bot', 'Send Telegram Alert & Buy SOL')")


class AlertRuleUpdate(BaseModel):
    metric: Optional[str] = None
    condition: Optional[str] = None
    value: Optional[str] = None
    action: Optional[str] = None
    active: Optional[bool] = None


class AlertRuleResponse(BaseModel):
    id: str
    metric: str
    condition: str
    value: str
    action: str
    active: bool
    created_at: str
    triggered_at: Optional[str]
    trigger_count: int
    
    class Config:
        from_attributes = True


@router.get("", response_model=List[AlertRuleResponse])
async def get_rules(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all alert rules for user"""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    rules_result = await db.execute(
        select(AlertRule).where(AlertRule.profile_id == profile.id).order_by(AlertRule.created_at.desc())
    )
    rules = rules_result.scalars().all()
    
    return [AlertRuleResponse.model_validate(r) for r in rules]


@router.post("", response_model=AlertRuleResponse, status_code=201)
async def create_rule(
    rule: AlertRuleCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create new alert rule"""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    new_rule = AlertRule(
        profile_id=profile.id,
        metric=rule.metric,
        condition=rule.condition,
        value=rule.value,
        action=rule.action,
        active=True
    )
    db.add(new_rule)
    await db.commit()
    await db.refresh(new_rule)
    
    return AlertRuleResponse.model_validate(new_rule)


@router.patch("/{rule_id}", response_model=AlertRuleResponse)
async def update_rule(
    rule_id: str,
    updates: AlertRuleUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update alert rule"""
    import uuid
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    rule_result = await db.execute(
        select(AlertRule).where(
            AlertRule.id == uuid.UUID(rule_id),
            AlertRule.profile_id == profile.id
        )
    )
    rule = rule_result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)
    
    await db.commit()
    await db.refresh(rule)
    
    return AlertRuleResponse.model_validate(rule)


@router.post("/{rule_id}/toggle", response_model=AlertRuleResponse)
async def toggle_rule(
    rule_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Toggle rule active status"""
    import uuid
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    rule_result = await db.execute(
        select(AlertRule).where(
            AlertRule.id == uuid.UUID(rule_id),
            AlertRule.profile_id == profile.id
        )
    )
    rule = rule_result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    rule.active = not rule.active
    await db.commit()
    await db.refresh(rule)
    
    return AlertRuleResponse.model_validate(rule)


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete alert rule"""
    import uuid
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    rule_result = await db.execute(
        select(AlertRule).where(
            AlertRule.id == uuid.UUID(rule_id),
            AlertRule.profile_id == profile.id
        )
    )
    rule = rule_result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    await db.delete(rule)
    await db.commit()
    
    return {"message": "Rule deleted"}