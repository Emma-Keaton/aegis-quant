import json
import logging
from typing import Optional, Dict

from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel

from app.core.telegram_auth import get_current_user, verify_telegram_init_data
from sqlalchemy import select
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Profile, CopyTradeSubscription
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
    elif update.channel_post:
        await handle_channel_post(update.channel_post)
    elif update.edited_channel_post:
        await handle_channel_post(update.edited_channel_post)
    elif update.my_chat_member:
        await handle_my_chat_member(update.my_chat_member)
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
    
    # Route all incoming messages through the dispatcher — it handles slash
    # commands AND free-text (AI assistant: trade exec, watch, status, answers).
    await process_user_message(chat_id, text, user)


async def handle_callback_query(callback_query: dict):
    """Process callback query (inline keyboard buttons)"""
    from app.telegram.bot_handler import process_callback
    
    chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
    data = callback_query.get("data")
    user = callback_query.get("from", {})
    
    if chat_id and data:
        await process_callback(chat_id, data, user)


async def handle_channel_post(message: dict) -> None:
    """Process a channel post when the bot is a member/admin — run it through the
    copy-trade pipeline (parse -> confidence -> execute) for matching watchers."""
    text = (message.get("text") or message.get("caption") or "").strip()
    if not text:
        return
    chat = message.get("chat", {}) or {}
    chat_id = chat.get("id")
    username = (chat.get("username") or "").strip()

    from app.services.channel_feed import channel_username
    from app.services.signal_parser import parse_signal_text
    from app.services.trade_executor import execute_parsed_signal

    refs = {str(chat_id) if chat_id is not None else "", username, ("@" + username) if username else "",
            channel_username(username)}

    async with AsyncSessionLocal() as db:
        subs = (await db.execute(
            select(CopyTradeSubscription).where(CopyTradeSubscription.active == True)
        )).scalars().all()

    matched = [s for s in subs
               if (s.channel_id or "").strip() in refs
               or (s.channel_id or "").lstrip("@") == username]
    for sub in matched:
        try:
            parsed = await parse_signal_text(text)
            if not parsed:
                continue
            if int(parsed.get("confidence") or 0) < (sub.confidence_threshold if sub.confidence_threshold is not None else 70):
                continue
            await execute_parsed_signal(sub.profile_id, parsed, source=f"telegram:{sub.channel_id}")
        except Exception as e:
            logger.warning("channel_post pipeline failed for %s: %s", sub.channel_id, e)


async def handle_my_chat_member(update: dict) -> None:
    """Bot added/promoted/kicked in a chat — log it (used to confirm joins)."""
    chat = update.get("chat", {}) or {}
    new = update.get("new_chat_member", {}) or {}
    status = new.get("status")
    logger.info("[Bot] my_chat_member in %s (%s): %s", chat.get("id"), chat.get("type"), status)


# ── Telegram account linking (phone + OTP -> encrypted Telethon session) ──

@router.post("/link/connect")
async def telegram_link_connect(payload: dict, user: dict = Depends(get_current_user)):
    from app.services import telegram_link
    res = await telegram_link.init_connect(user["id"], payload.get("phone", ""))
    return {"status": "success" if res.get("ok") else "error", **res}


@router.post("/link/otp")
async def telegram_link_otp(payload: dict, user: dict = Depends(get_current_user)):
    from app.services import telegram_link
    res = await telegram_link.confirm_otp(user["id"], payload.get("code", ""), payload.get("password"))
    return {"status": "success" if res.get("ok") else "error", **res}


@router.get("/link/status")
async def telegram_link_status(user: dict = Depends(get_current_user)):
    from app.services import telegram_link
    return await telegram_link.status(user["id"])


@router.post("/link/logout")
async def telegram_link_logout(user: dict = Depends(get_current_user)):
    from app.services import telegram_link
    res = await telegram_link.logout(user["id"])
    return {"status": "success", **res}


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