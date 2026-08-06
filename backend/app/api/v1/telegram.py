import json
import logging
from typing import Optional, Dict

from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel

from app.core.telegram_auth import get_current_user, verify_telegram_init_data
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Profile
from app.telegram.bot_handler import process_user_message, send_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


class WebhookUpdate(BaseModel):
    update_id: int
    message: Optional[dict] = None
    edited_message: Optional[dict] = None
    channel_post: Optional[dict] = None
    edited_channel_post: Optional[dict] = None
    inline_query: Optional[dict] = None
    chosen_inline_result: Optional[dict] = None
    callback_query: Optional[dict] = None
    shipping_query: Optional[dict] = None
    pre_checkout_query: Optional[dict] = None
    poll: Optional[dict] = None
    poll_answer: Optional[dict] = None
    my_chat_member: Optional[dict] = None
    chat_member: Optional[dict] = None
    chat_join_request: Optional[dict] = None


@router.post("/webhook")
async def telegram_webhook(
    update: WebhookUpdate,
    request: Request
):
    """Telegram bot webhook endpoint"""
    # Verify the request came from Telegram
    # Check X-Telegram-Bot-Api-Secret-Token header
    settings = get_settings()
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    
    if settings.TELEGRAM_WEBHOOK_SECRET and secret_token != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")
    
    # Process update
    if update.message:
        await handle_message(update.message)
    elif update.callback_query:
        await handle_callback_query(update.callback_query)
    
    return {"ok": True}


async def handle_message(message: dict):
    """Process incoming message"""
    from app.telegram.bot_handler import process_user_message
    
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    user = message.get("from", {})
    
    if not chat_id or not text:
        return
    
    # Parse command
    if text.startswith("/"):
        await process_user_message(chat_id, text, user)
    else:
        # Natural language processing via /api/v1/chat
        pass


async def handle_callback_query(callback_query: dict):
    """Process callback query (inline keyboard buttons)"""
    from app.telegram.bot_handler import process_callback
    
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
    data = callback_query.get("data")
    user = callback_query.get("from", {})
    
    if chat_id and data:
        await process_callback(chat_id, data, user)


@router.post("/set-webhook")
async def set_webhook(
    url: str,
    user: dict = Depends(get_current_user)
):
    """Set Telegram bot webhook URL"""
    import httpx
    settings = get_settings()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook",
            json={
                "url": url,
                "secret_token": settings.TELEGRAM_WEBHOOK_SECRET,
                "allowed_updates": ["message", "callback_query", "inline_query"]
            }
        )
    
    return response.json()


@router.delete("/webhook")
async def delete_webhook(
    user: dict = Depends(get_current_user)
):
    """Delete Telegram bot webhook"""
    import httpx
    settings = get_settings()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/deleteWebhook"
        )
    
    return response.json()