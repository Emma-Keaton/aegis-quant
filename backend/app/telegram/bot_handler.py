"""Telegram bot handler — processes /start and other commands for Aegis Quant.

Bot integrates with Mini App by generating the tg_initData query parameter
that Mini Apps receive when launched from Telegram.
"""

import asyncio
import logging
import html
from typing import Optional, Dict, Any

from fastapi import HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone

from app.core.telegram_auth import verify_telegram_init_data
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Profile

logger = logging.getLogger(__name__)
settings = get_settings()


class UserProfile(BaseModel):
    id: int
    username: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    language_code: str = "en"


class BotCommandResponse(BaseModel):
    command: str
    text: str


async def process_user_message(chat_id: int, text: str, user: Dict[str, Any]) -> None:
    """Process incoming user message from Telegram webhook."""
    logger.info(f"[Bot] Message from chat={chat_id}, user={user.get('username')}, text={text[:50]}...")

    if text.startswith("/start"):
        # Handle /start command — extract pass-through parameter if present
        parts = text.split()
        if len(parts) > 1:
            pass_through = parts[1].strip()
            if pass_through:
                # Decode base64 pass-through (Telegram Mini App can encode tg_initData)
                await send_message(chat_id, f"/start received: {pass_through}")
            else:
                await send_message(chat_id, "/start without parameters — welcome to Aegis Quant!")
        else:
            await send_message(chat_id, "/start <pass_through> to launch Mini App")
        return

    if text.startswith("/help"):
        help_text = (
            "Aegis Quant Trading Bot\n"
            "• /start [tg_initData] — Launch Mini App with auth\n"
            "• /profile — View your trading profile\n"
            "• /mode paper|live — Set trading mode\n"
            "• /toggle_bot on/off — Enable/disable trading agent\n"
            "• /signals — View current signals\n"
        )
        await send_message(chat_id, help_text)
        return

    if text.startswith("/profile"):
        # Fetch profile from DB (would need auth linkage in production)
        async with AsyncSessionLocal() as db:
            # In production, link via Telegram ID
            telegram_id = chat_id  # Telegram chat_id often equals user ID for private chats
            result = await db.execute(
                f"SELECT * FROM profiles WHERE telegram_id = {telegram_id} LIMIT 1"
            )
            # ... handle profile ...
        await send_message(chat_id, "Profile information would appear here.")
        return

    # Default response
    await send_message(chat_id, "I understand you sent: " + html.escape(text))


async def send_message(chat_id: int, text: str) -> None:
    """Send a message to a chat via Telegram Bot API."""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping message send")
        return

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json=payload)
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")


async def generate_mini_app_init_data(user_id: int, username: Optional[str] = None) -> str:
    """
    Generate a tg_initData query string for launching the Mini App.
    
    In production, this should be called from the backend after verifying
    the user's session, and the Mini App should be launched with:
    https://t.me/{bot_username}/?start={base64_encoded_init_data}
    
    This is a simplified version — actual initData includes HMAC signature
    which requires the bot token and secret. For Mini App launch, Telegram
    generates the init data automatically when the user clicks the "Open App"
    button from the bot.
    """
    data = {
        "user": {
            "id": user_id,
            "username": username or "",
            "first_name": "User",
            "is_bot": False,
        },
        "auth_date": int(timezone.utc.timestamp()),
        "session_data": "",
        "web_app_data": "",
    }
    # In production, you'd generate the hash using Telegram's auth method
    # For now, just return a simple query parameter
    user_str = f"user={json.dumps(data['user'])}"
    auth_str = f"auth_date={str(data['auth_date'])}"
    return f"{user_str}&{auth_str}"


async def handle_callback_query(callback_query: Dict[str, Any]) -> None:
    """Process inline callback queries from the Mini App."""
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
    data = callback_query.get("data", "")
    user = callback_query.get("from", {})

    if chat_id:
        await send_message(chat_id, f"Callback received: {data}")
