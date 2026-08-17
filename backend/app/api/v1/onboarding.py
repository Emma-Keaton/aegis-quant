"""Onboarding router — persistent per-page tutorial completion for a profile.

The onboarding state lives on the Profile row:
  - onboarding_completed: bool   (overall flag; derived from pages)
  - onboarding_pages:     JSON   (list of completed page keys)

It is *only* reset to false when the user clicks "Reset onboarding tour" in
Settings. Each page's tutorial is shown until that page is marked complete, and
pages already completed never show their tutorial again.
"""
import json
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.core.telegram_auth import get_current_user
from app.models import Profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

ALL_PAGES = ["home", "wallet", "strategy", "intel", "logs"]


class CompleteRequest(BaseModel):
    page: str


def _parse_pages(raw) -> List[str]:
    try:
        data = json.loads(raw) if raw else []
        return [p for p in data if isinstance(p, str)]
    except Exception:
        return []


def _profile_state(profile: Profile) -> dict:
    pages = _parse_pages(profile.onboarding_pages)
    return {
        "completed_pages": pages,
        "onboarding_completed": bool(getattr(profile, "onboarding_completed", False)),
        "pages": ALL_PAGES,
        "pending_pages": [p for p in ALL_PAGES if p not in pages],
    }


@router.get("")
async def get_onboarding(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Profile).where(Profile.telegram_id == user["id"]))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"status": "success", "data": _profile_state(profile)}


@router.post("/complete")
async def complete_page(
    request: CompleteRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if request.page not in ALL_PAGES:
        raise HTTPException(status_code=422, detail=f"Unknown page: {request.page}")
    result = await db.execute(select(Profile).where(Profile.telegram_id == user["id"]))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    pages = _parse_pages(profile.onboarding_pages)
    if request.page not in pages:
        pages.append(request.page)
    profile.onboarding_pages = json.dumps(pages)
    profile.onboarding_completed = all(p in pages for p in ALL_PAGES)
    await db.commit()
    await db.refresh(profile)
    return {"status": "success", "data": _profile_state(profile)}


@router.post("/reset")
async def reset_onboarding(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reset all onboarding tours. Called from Settings — the ONLY place this resets."""
    result = await db.execute(select(Profile).where(Profile.telegram_id == user["id"]))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.onboarding_pages = "[]"
    profile.onboarding_completed = False
    await db.commit()
    await db.refresh(profile)
    return {"status": "success", "data": _profile_state(profile)}