"""Authentication router — Telegram init-data verification, session creation, token management."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.telegram_auth import verify_telegram_init_data
from app.database import get_db
from app.models import Profile, UserSession

router = APIRouter(prefix="/api/auth", tags=["authentication"])
security = HTTPBearer(auto_error=False)

settings = get_settings()

SESSION_TTL_HOURS = 720  # 30 days


def generate_session_token() -> str:
    return secrets.token_urlsafe(64)


def is_session_expired(session: UserSession) -> bool:
    if session.expires_at.tzinfo is None:
        session_expires = session.expires_at.replace(tzinfo=timezone.utc)
    else:
        session_expires = session.expires_at
    return datetime.now(timezone.utc) > session_expires


async def get_current_user_from_token(
    token: str,
    db: AsyncSession
) -> dict:
    """Validate session token and return user info."""
    session = await db.execute(
        select(UserSession)
        .where(UserSession.token == token)
        .where(UserSession.expires_at > datetime.now(timezone.utc))
    )
    sess = session.scalar_one_or_none()
    if not sess:
        raise HTTPException(status_code=401, detail="Invalid or expired session token")
    
    profile = await db.execute(
        select(Profile).where(Profile.telegram_id == sess.telegram_id)
    )
    profile_obj = profile.scalar_one_or_none()
    
    return {
        "id": sess.telegram_id,
        "profile_id": str(profile_obj.id) if profile_obj else None,
        "username": profile_obj.username if profile_obj else None,
        "first_name": profile_obj.first_name if profile_obj else None,
    }


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """Dependency: extract and validate session token from Authorization header."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    return await get_current_user_from_token(credentials.credentials, None)  # db injected later


@router.post("/init")
async def auth_init(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Step 1: Verify Telegram initData from Mini App launch.
    Returns session token + profile info.
    Called once when user clicks 'Start' on the bot.
    """
    init_data = request.headers.get("X-Telegram-Init-Data")
    if not init_data:
        raise HTTPException(status_code=400, detail="Missing X-Telegram-Init-Data header")
    
    verified = await verify_telegram_init_data(init_data, settings.TELEGRAM_BOT_TOKEN)
    user = verified["user"]
    telegram_id = user.get("id")
    
    if not telegram_id:
        raise HTTPException(status_code=400, detail="No user id in Telegram initData")
    
    # Get or create profile
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        profile = Profile(
            telegram_id=telegram_id,
            username=user.get("username"),
            first_name=user.get("first_name"),
            last_name=user.get("last_name"),
            language_code=user.get("language_code"),
            risk_level="medium",
            max_allocation_pct=10.0,
            max_concurrent_trades=3,
            trading_mode="paper",
            bot_enabled=False,
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    
    # Check for existing valid session
    existing = await db.execute(
        select(UserSession)
        .where(UserSession.telegram_id == telegram_id)
        .where(UserSession.expires_at > datetime.now(timezone.utc))
    )
    existing_session = existing.scalar_one_or_none()
    
    if existing_session:
        token = existing_session.token
    else:
        token = generate_session_token()
        session = UserSession(
            telegram_id=telegram_id,
            profile_id=profile.id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS),
        )
        db.add(session)
        await db.commit()
    
    return {
        "status": "success",
        "session_token": token,
        "profile": {
            "id": str(profile.id),
            "telegram_id": profile.telegram_id,
            "username": profile.username,
            "first_name": profile.first_name,
            "trading_mode": profile.trading_mode,
            "bot_enabled": profile.bot_enabled,
            "max_allocation_pct": float(profile.max_allocation_pct),
            "max_concurrent_trades": profile.max_concurrent_trades,
        }
    }


@router.post("/refresh")
async def auth_refresh(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Step 2: Refresh session token before expiry."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    current_token = auth_header[7:]
    
    result = await db.execute(
        select(UserSession)
        .where(UserSession.token == current_token)
        .where(UserSession.expires_at > datetime.now(timezone.utc))
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session token")
    
    # Generate new token, invalidate old one
    new_token = generate_session_token()
    session.token = new_token
    session.expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    await db.commit()
    
    return {
        "status": "success",
        "session_token": new_token,
    }


@router.post("/logout")
async def auth_logout(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Invalidate current session token."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    current_token = auth_header[7:]
    await db.execute(
        select(UserSession).where(UserSession.token == current_token)
    )
    result = await db.execute(select(UserSession).where(UserSession.token == current_token))
    session = result.scalar_one_or_none()
    
    if session:
        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)  # invalidate
        await db.commit()
    
    return {"status": "success", "message": "Session invalidated"}


@router.get("/me")
async def auth_me(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user profile info."""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return {
        "status": "success",
        "profile": {
            "id": str(profile.id),
            "telegram_id": profile.telegram_id,
            "username": profile.username,
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "language_code": profile.language_code,
            "wallet_connected": profile.wallet_connected if hasattr(profile, 'wallet_connected') else False,
            "wallet_address": profile.wallet_address if hasattr(profile, 'wallet_address') else None,
            "wallet_network": profile.wallet_network if hasattr(profile, 'wallet_network') else None,
            "trading_mode": profile.trading_mode,
            "bot_enabled": profile.bot_enabled,
            "max_allocation_pct": float(profile.max_allocation_pct),
            "max_concurrent_trades": profile.max_concurrent_trades,
        }
    }
