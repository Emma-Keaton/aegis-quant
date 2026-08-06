from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import logging

from app.config import get_settings
from app.database import get_db
from app.models import UserSession

logger = logging.getLogger(__name__)


async def verify_telegram_init_data(init_data: str, bot_token: str) -> Dict[str, Any]:
    """
    Verify Telegram Web App initData signature.
    Returns parsed user data if valid.
    """
    import hmac
    import hashlib
    import time
    from urllib.parse import parse_qsl, unquote
    import json

    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = parsed.pop("hash", "")
        
        if not received_hash:
            raise ValueError("Missing hash")

        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256
        ).digest()
        
        expected_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_hash, received_hash):
            raise ValueError("Invalid signature")

        # Check auth_date freshness (24 hours default)
        auth_date_str = parsed.get("auth_date", "")
        if auth_date_str:
            auth_date = int(auth_date_str)
            if time.time() - auth_date > 86400:
                raise ValueError("initData expired")

        # Parse user
        user_str = parsed.get("user", "{}")
        user = json.loads(unquote(user_str))

        return {
            "user": user,
            "query_id": parsed.get("query_id", ""),
            "auth_date": auth_date_str,
            "raw": parsed
        }

    except Exception as e:
        logger.warning(f"Telegram initData verification failed: {e}")
        raise HTTPException(status_code=401, detail=f"Invalid Telegram initData: {e}")


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    FastAPI dependency to get authenticated Telegram user.
    
    Supports two auth mechanisms (checked in order):
    1. Header: X-Telegram-Init-Data — HMAC-verified Telegram Web App initData.
    2. Authorization: Bearer <session_token> — server-issued session token (see /api/auth/init).
    """
    settings = get_settings()

    init_data = request.headers.get("X-Telegram-Init-Data")
    if init_data:
        verified = await verify_telegram_init_data(init_data, settings.TELEGRAM_BOT_TOKEN)
        user = verified["user"]

        if not user or "id" not in user:
            raise HTTPException(status_code=401, detail="Invalid user data in initData")

        request.state.telegram_user = user
        request.state.init_data = verified
        request.state.auth_method = "init_data"
        return user

    if credentials and credentials.credentials:
        result = await db.execute(
            select(UserSession)
            .where(UserSession.token == credentials.credentials)
            .where(UserSession.expires_at > datetime.now(timezone.utc))
        )
        sess = result.scalar_one_or_none()
        if not sess:
            raise HTTPException(status_code=401, detail="Invalid or expired session token")

        user = {"id": sess.telegram_id}
        request.state.telegram_user = user
        request.state.auth_method = "session_token"
        return user

    raise HTTPException(
        status_code=401,
        detail="Missing X-Telegram-Init-Data header or Authorization Bearer token"
    )


def require_telegram_auth(user: Dict = Depends(get_current_user)) -> Dict:
    """Alias for clarity in route definitions"""
    return user