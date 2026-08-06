"""Telegram bot handler — processes /start and other commands for Aegis Quant.

The bot launches the Mini App via a Telegram WebApp inline keyboard button
(t.me/<bot_username>/app), which passes a signed initData to the frontend.
"""

import asyncio
import logging
import html
import json
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


def _webapp_url() -> str:
    """Frontend URL that the WebApp button launches."""
    return settings.APP_URL.rstrip("/")


def _webapp_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "🚀 Launch Aegis Quant",
                    "web_app": {"url": _webapp_url()},
                }
            ]
        ]
    }


async def process_user_message(chat_id: int, text: str, user: Dict[str, Any]) -> None:
    """Process incoming user message from Telegram webhook."""
    logger.info(f"[Bot] Message from chat={chat_id}, user={user.get('username')}, text={text[:50]}...")

    if text.startswith("/start"):
        welcome = (
            f"Welcome to Aegis Quant, {user.get('first_name', 'trader')}! 🛡️\n\n"
            "Your AI-powered crypto trading copilot. Tap the button below to "
            "open the app and connect your wallet, set risk limits, and "
            "activate the trading agents."
        )
        await send_message(chat_id, welcome, reply_markup=_webapp_keyboard())
        return

    if text.startswith("/help"):
        help_text = (
            "Aegis Quant Trading Bot\n"
            "• /start — Launch the Mini App\n"
            "• /profile — View your trading profile\n"
            "• /mode paper|live — Set trading mode\n"
            "• /toggle_bot on/off — Enable/disable trading agent\n"
            "• /signals — View current signals\n"
        )
        await send_message(chat_id, help_text)
        return

    if text.startswith("/profile"):
        async with AsyncSessionLocal() as db:
            telegram_id = chat_id
            result = await db.execute(
                Profile.__table__.select().where(Profile.telegram_id == telegram_id).limit(1)
            )
            row = result.mappings().first()
        if row:
            mode = row.get("trading_mode") or "paper"
            enabled = bool(row.get("bot_enabled"))
            await send_message(
                chat_id,
                f"📊 Profile\n"
                f"• Mode: `{mode}`\n"
                f"• Bot: {'enabled' if enabled else 'disabled'}\n"
                f"• Risk: `{row.get('risk_level', 'medium')}`",
            )
        else:
            await send_message(
                chat_id,
                "No profile found yet. Open the app once via /start to create your profile.",
                reply_markup=_webapp_keyboard(),
            )
        return

    # Default response
    await send_message(chat_id, "I understand you sent: " + html.escape(text))


async def process_callback(chat_id: int, data: str, user: Dict[str, Any]) -> None:
    """Process inline callback button presses (e.g. WebApp inline buttons)."""
    logger.info(f"[Bot] Callback chat={chat_id}, data={data}")
    if data == "open_app":
        await send_message(chat_id, "Opening Aegis Quant…", reply_markup=_webapp_keyboard())
        return
    await send_message(chat_id, f"Callback received: {html.escape(data[:100])}")


async def send_message(chat_id: int, text: str, reply_markup: Optional[dict] = None) -> None:
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
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code >= 400:
                logger.warning(f"Telegram sendMessage failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")


async def handle_callback_query(callback_query: Dict[str, Any]) -> None:
    """Process inline callback queries from the Mini App."""
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
    data = callback_query.get("data", "")
    user = callback_query.get("from", {})
    if chat_id:
        await process_callback(chat_id, data, user)
