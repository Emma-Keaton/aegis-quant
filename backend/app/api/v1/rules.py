"""Alert rules — persisted to PostgreSQL."""

import logging
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.telegram_auth import get_current_user
from app.database import get_db
from app.models import Profile, AlertRule

logger = logging.getLogger(__name__)
router = APIRouter(tags=["rules"])


class RuleCreate(BaseModel):
    metric: str = Field(..., min_length=1, max_length=100)
    condition: str = Field(..., min_length=1, max_length=20)
    value: str = Field(..., min_length=1, max_length=50)
    action: str = Field(..., min_length=1, max_length=200)


class RuleItem(BaseModel):
    id: str
    metric: str
    condition: str
    value: str
    action: str
    active: bool


class RulesResponse(BaseModel):
    status: str
    data: List[RuleItem]
    allRules: List[RuleItem] = []


@router.get("/api/rules")
async def get_rules(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        return RulesResponse(status="success", data=[])
    
    res = await db.execute(
        select(AlertRule).where(AlertRule.profile_id == profile.id).order_by(AlertRule.created_at.desc())
    )
    rules = res.scalars().all()
    
    data = [RuleItem(
        id=str(r.id), metric=r.metric, condition=r.condition,
        value=r.value, action=r.action, active=r.active,
    ) for r in rules]
    
    return RulesResponse(status="success", data=data, allRules=data)


@router.post("/api/rules", response_model=RulesResponse)
async def create_rule(
    rule: RuleCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
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
        active=True,
    )
    db.add(new_rule)
    await db.commit()
    await db.refresh(new_rule)
    
    all_res = await db.execute(select(AlertRule).where(AlertRule.profile_id == profile.id))
    all_rules = all_res.scalars().all()
    
    data = [RuleItem(id=str(r.id), metric=r.metric, condition=r.condition,
                     value=r.value, action=r.action, active=r.active) for r in all_rules]
    
    return RulesResponse(status="success", data=data, allRules=data)


@router.post("/api/rules/toggle")
async def toggle_rule(
    request: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    rule_id = request.get("id")
    if not rule_id:
        raise HTTPException(status_code=400, detail="id required")
    
    import uuid
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    res = await db.execute(
        select(AlertRule).where(AlertRule.id == uuid.UUID(rule_id), AlertRule.profile_id == profile.id)
    )
    rule = res.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    rule.active = not rule.active
    await db.commit()
    await db.refresh(rule)
    
    return {"status": "success", "allRules": [
        {"id": str(r.id), "metric": r.metric, "condition": r.condition,
         "value": r.value, "action": r.action, "active": r.active}
        for r in [rule]
    ]}


@router.post("/api/rules/delete")
async def delete_rule(
    request: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    rule_id = request.get("id")
    if not rule_id:
        raise HTTPException(status_code=400, detail="id required")
    
    import uuid
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    res = await db.execute(
        select(AlertRule).where(AlertRule.id == uuid.UUID(rule_id), AlertRule.profile_id == profile.id)
    )
    rule = res.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    await db.delete(rule)
    await db.commit()
    
    return {"status": "success"}
