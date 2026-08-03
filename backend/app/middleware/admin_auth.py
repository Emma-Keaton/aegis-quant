"""Admin authentication middleware and guards.

Only users whose Telegram chat ID matches ADMIN_CHAT_ID in env vars are granted
admin access. All admin endpoints are guarded by this middleware."""

import hashlib
import hmac
from typing import Dict, Optional

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import get_settings
from app.core.telegram_auth import verify_telegram_init_data

settings = get_settings()
ADMIN_CHAT_ID: Optional[int] = settings.ADMIN_CHAT_ID if hasattr(settings, 'ADMIN_CHAT_ID') else None

class AdminGuard:
    """Guard for admin-only endpoints. Must be used as a dependency on admin routes."""
    
    @staticmethod
    async def verify_admin(request: Request) -> Dict:
        """Verify admin access via Telegram init data."""
        init_data = request.headers.get("X-Telegram-Init-Data")
        if not init_data:
            raise HTTPException(status_code=401, detail="Missing X-Telegram-Init-Data header")
        
        try:
            verified = await verify_telegram_init_data(init_data, settings.TELEGRAM_BOT_TOKEN)
            user = verified["user"]
            telegram_id = user.get("id")
            
            # Check if this is the admin chat ID
            if ADMIN_CHAT_ID is None or telegram_id != ADMIN_CHAT_ID:
                logger.warning(f"Unauthorized admin access attempt from telegram_id={telegram_id}")
                raise HTTPException(status_code=403, detail="Admin access denied")
            
            return user
        except Exception as e:
            logger.error(f"Admin verification failed: {e}")
            raise HTTPException(status_code=401, detail="Invalid admin credentials")


# Simple logger for the guard (import at bottom to avoid circular)
import logging
logger = logging.getLogger(__name__)
