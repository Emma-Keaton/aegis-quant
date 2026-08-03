"""Source management router - tenant and admin CRUD."""

import json
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.telegram_auth import get_current_user
from app.database import get_db
from app.models import Profile
from app.models.sources import UserSource, AdminSource
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sources", tags=["source-management"])
settings = get_settings()


# ── Pydantic Models ──────────────────────────────────────────────────

class SourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    source_type: str = Field(..., pattern="^(rss|twitter|telegram|reddit|onchain)$")
    url_or_handle: str = Field(..., min_length=1, max_length=500)
    priority: int = Field(5, ge=1, le=10)
    tags: List[str] = Field(default_factory=list)
    description: str = ""


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    url_or_handle: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=10)
    tags: Optional[List[str]] = None
    description: Optional[str] = None
    enabled: Optional[bool] = None


class SourceResponse(BaseModel):
    id: str
    name: str
    source_type: str
    url_or_handle: str
    priority: int
    tags: List[str]
    description: str
    enabled: bool
    is_default: bool = False
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class SourceListResponse(BaseModel):
    sources: List[SourceResponse]
    total: int


# ── Helper Functions ─────────────────────────────────────────────────

async def _get_profile(db: AsyncSession, telegram_id: int) -> Profile:
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


# ── Tenant Sources (User CRUD) ───────────────────────────────────────

@router.get("/my", response_model=SourceListResponse)
async def get_my_sources(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's custom sources."""
    profile = await _get_profile(db, user["id"])
    
    result = await db.execute(
        select(UserSource).where(UserSource.profile_id == profile.id)
        .order_by(UserSource.priority.desc())
    )
    sources = result.scalars().all()
    
    return SourceListResponse(
        sources=[SourceResponse(
            id=str(s.id),
            name=s.name,
            source_type=s.source_type,
            url_or_handle=s.url_or_handle,
            priority=s.priority,
            tags=json.loads(s.tags) if s.tags else [],
            description=s.description or "",
            enabled=s.enabled,
            is_default=False,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat() if s.updated_at else s.created_at.isoformat(),
        ) for s in sources],
        total=len(sources)
    )


@router.post("/my", response_model=SourceResponse, status_code=201)
async def create_my_source(
    source: SourceCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a custom source for the user."""
    profile = await _get_profile(db, user["id"])
    
    # Check for duplicates
    existing = await db.execute(
        select(UserSource).where(
            UserSource.profile_id == profile.id,
            UserSource.name == source.name
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Source '{source.name}' already exists")
    
    existing_url = await db.execute(
        select(UserSource).where(
            UserSource.profile_id == profile.id,
            UserSource.url_or_handle == source.url_or_handle
        )
    )
    if existing_url.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Source URL already exists")
    
    new_source = UserSource(
        profile_id=profile.id,
        name=source.name,
        source_type=source.source_type,
        url_or_handle=source.url_or_handle,
        priority=source.priority,
        tags=json.dumps(source.tags),
        description=source.description,
    )
    db.add(new_source)
    await db.commit()
    await db.refresh(new_source)
    
    logger.info(f"User {user['id']} added source: {source.name}")
    
    return SourceResponse(
        id=str(new_source.id),
        name=new_source.name,
        source_type=new_source.source_type,
        url_or_handle=new_source.url_or_handle,
        priority=new_source.priority,
        tags=source.tags,
        description=source.description,
        enabled=new_source.enabled,
        is_default=False,
        created_at=new_source.created_at.isoformat(),
        updated_at=new_source.created_at.isoformat(),
    )


@router.put("/my/{source_id}", response_model=SourceResponse)
async def update_my_source(
    source_id: str,
    updates: SourceUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a user's custom source."""
    profile = await _get_profile(db, user["id"])
    
    result = await db.execute(
        select(UserSource).where(
            UserSource.id == source_id,
            UserSource.profile_id == profile.id
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    if updates.name is not None:
        source.name = updates.name
    if updates.url_or_handle is not None:
        source.url_or_handle = updates.url_or_handle
    if updates.priority is not None:
        source.priority = updates.priority
    if updates.tags is not None:
        source.tags = json.dumps(updates.tags)
    if updates.description is not None:
        source.description = updates.description
    if updates.enabled is not None:
        source.enabled = updates.enabled
    
    await db.commit()
    await db.refresh(source)
    
    return SourceResponse(
        id=str(source.id),
        name=source.name,
        source_type=source.source_type,
        url_or_handle=source.url_or_handle,
        priority=source.priority,
        tags=json.loads(source.tags) if source.tags else [],
        description=source.description or "",
        enabled=source.enabled,
        is_default=False,
        created_at=source.created_at.isoformat(),
        updated_at=source.updated_at.isoformat() if source.updated_at else source.created_at.isoformat(),
    )


@router.delete("/my/{source_id}")
async def delete_my_source(
    source_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a user's custom source."""
    profile = await _get_profile(db, user["id"])
    
    result = await db.execute(
        select(UserSource).where(
            UserSource.id == source_id,
            UserSource.profile_id == profile.id
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    await db.delete(source)
    await db.commit()
    
    logger.info(f"User {user['id']} deleted source: {source.name}")
    return {"status": "success", "message": f"Source '{source.name}' deleted"}


# ── Admin Sources (Admin CRUD) ───────────────────────────────────────

@router.get("/admin", response_model=SourceListResponse)
async def get_admin_sources(
    source_type: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get admin-managed baseline sources."""
    query = select(AdminSource)
    if source_type:
        query = query.where(AdminSource.source_type == source_type)
    query = query.order_by(AdminSource.priority.desc())
    
    result = await db.execute(query)
    sources = result.scalars().all()
    
    return SourceListResponse(
        sources=[SourceResponse(
            id=str(s.id),
            name=s.name,
            source_type=s.source_type,
            url_or_handle=s.url_or_handle,
            priority=s.priority,
            tags=json.loads(s.tags) if s.tags else [],
            description=s.description or "",
            enabled=s.enabled,
            is_default=s.is_default,
            created_at=s.created_at.isoformat(),
            updated_at=s.updated_at.isoformat() if s.updated_at else s.created_at.isoformat(),
        ) for s in sources],
        total=len(sources)
    )


@router.post("/admin", response_model=SourceResponse, status_code=201)
async def create_admin_source(
    source: SourceCreate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a new baseline source (admin only)."""
    # Check admin access
    if user["id"] != settings.ADMIN_CHAT_ID:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    existing = await db.execute(
        select(AdminSource).where(AdminSource.name == source.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Source '{source.name}' already exists")
    
    new_source = AdminSource(
        name=source.name,
        source_type=source.source_type,
        url_or_handle=source.url_or_handle,
        priority=source.priority,
        tags=json.dumps(source.tags),
        description=source.description,
        is_default=False,
    )
    db.add(new_source)
    await db.commit()
    await db.refresh(new_source)
    
    logger.info(f"Admin added baseline source: {source.name}")
    
    return SourceResponse(
        id=str(new_source.id),
        name=new_source.name,
        source_type=new_source.source_type,
        url_or_handle=new_source.url_or_handle,
        priority=new_source.priority,
        tags=source.tags,
        description=source.description,
        enabled=new_source.enabled,
        is_default=False,
        created_at=new_source.created_at.isoformat(),
        updated_at=new_source.created_at.isoformat(),
    )


@router.put("/admin/{source_id}", response_model=SourceResponse)
async def update_admin_source(
    source_id: str,
    updates: SourceUpdate,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a baseline source (admin only)."""
    if user["id"] != settings.ADMIN_CHAT_ID:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.execute(select(AdminSource).where(AdminSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    if updates.name is not None:
        source.name = updates.name
    if updates.url_or_handle is not None:
        source.url_or_handle = updates.url_or_handle
    if updates.priority is not None:
        source.priority = updates.priority
    if updates.tags is not None:
        source.tags = json.dumps(updates.tags)
    if updates.description is not None:
        source.description = updates.description
    if updates.enabled is not None:
        source.enabled = updates.enabled
    
    await db.commit()
    await db.refresh(source)
    
    return SourceResponse(
        id=str(source.id),
        name=source.name,
        source_type=source.source_type,
        url_or_handle=source.url_or_handle,
        priority=source.priority,
        tags=json.loads(source.tags) if source.tags else [],
        description=source.description or "",
        enabled=source.enabled,
        is_default=source.is_default,
        created_at=source.created_at.isoformat(),
        updated_at=source.updated_at.isoformat() if source.updated_at else source.created_at.isoformat(),
    )


@router.delete("/admin/{source_id}")
async def delete_admin_source(
    source_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a baseline source (admin only)."""
    if user["id"] != settings.ADMIN_CHAT_ID:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.execute(select(AdminSource).where(AdminSource.id == source_id))
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    await db.delete(source)
    await db.commit()
    
    logger.info(f"Admin deleted baseline source: {source.name}")
    return {"status": "success", "message": f"Source '{source.name}' deleted"}


# ── Combined Sources (for Engine B) ─────────────────────────────────

@router.get("/combined")
async def get_combined_sources(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get combined sources (admin baseline + user custom) for a user."""
    profile = await _get_profile(db, user["id"])
    
    # Get admin sources
    admin_result = await db.execute(
        select(AdminSource).where(AdminSource.enabled == True)
        .order_by(AdminSource.priority.desc())
    )
    admin_sources = admin_result.scalars().all()
    
    # Get user sources
    user_result = await db.execute(
        select(UserSource).where(
            UserSource.profile_id == profile.id,
            UserSource.enabled == True
        )
        .order_by(UserSource.priority.desc())
    )
    user_sources = user_result.scalars().all()
    
    return {
        "sources": [
            {
                "id": str(s.id),
                "name": s.name,
                "source_type": s.source_type,
                "url_or_handle": s.url_or_handle,
                "priority": s.priority,
                "tags": json.loads(s.tags) if s.tags else [],
                "description": s.description or "",
                "enabled": s.enabled,
                "is_default": True,
            }
            for s in admin_sources
        ] + [
            {
                "id": str(s.id),
                "name": s.name,
                "source_type": s.source_type,
                "url_or_handle": s.url_or_handle,
                "priority": s.priority,
                "tags": json.loads(s.tags) if s.tags else [],
                "description": s.description or "",
                "enabled": s.enabled,
                "is_default": False,
            }
            for s in user_sources
        ],
        "total": len(admin_sources) + len(user_sources),
        "baseline_count": len(admin_sources),
        "user_count": len(user_sources),
    }
