"""Telethon MTProto link — phone + OTP -> encrypted session.

Used to read *private* channels the user is a member of (auto-forward of
signals) that cannot be read via RSS or a bot-member role.
"""
import logging
from typing import Dict, Optional

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Profile, TelegramLink
from app.core.encryption import encryption_manager
from app.config import get_settings

logger = logging.getLogger(__name__)

# In-memory pending clients for the OTP step (single-instance; fine for MVP).
_pending: Dict[str, Dict] = {}


def _client(phone: str):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    settings = get_settings()
    if not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH:
        raise RuntimeError("TELEGRAM_API_ID / TELEGRAM_API_HASH not configured")
    return TelegramClient(StringSession(), settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)


async def init_connect(profile_id, phone: str) -> dict:
    phone = (phone or "").strip()
    if not phone:
        return {"ok": False, "error": "phone_required"}
    client = _client(phone)
    await client.connect()
    sent = await client.send_code_request(phone)
    _pending[str(profile_id)] = {"client": client, "phone": phone}
    return {"ok": True, "phone_code_hash": sent.phone_code_hash, "status": "code_sent"}


async def confirm_otp(profile_id, code: str, password: Optional[str] = None) -> dict:
    from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
    entry = _pending.get(str(profile_id))
    if not entry:
        return {"ok": False, "error": "otp_not_started"}
    client = entry["client"]
    phone = entry["phone"]
    try:
        await client.sign_in(phone, code=code)
    except SessionPasswordNeededError:
        if not password:
            return {"ok": False, "error": "2fa_required"}
        await client.sign_in(password=password)
    except PhoneCodeInvalidError:
        return {"ok": False, "error": "invalid_code"}

    raw = client.session.save()
    await client.disconnect()
    enc = encryption_manager.encrypt(raw)

    async with AsyncSessionLocal() as db:
        row = (await db.execute(select(TelegramLink).where(TelegramLink.profile_id == profile_id))).scalar_one_or_none()
        if not row:
            row = TelegramLink(profile_id=profile_id, phone=phone, session_encrypted=enc, status="active")
            db.add(row)
        else:
            row.phone = phone
            row.session_encrypted = enc
            row.status = "active"
        await db.commit()
    _pending.pop(str(profile_id), None)
    return {"ok": True, "status": "active"}


async def _make_session(profile_id):
    from telethon.sessions import StringSession
    async with AsyncSessionLocal() as db:
        row = (await db.execute(select(TelegramLink).where(TelegramLink.profile_id == profile_id))).scalar_one_or_none()
    if not row or not row.session_encrypted or row.status != "active":
        raise RuntimeError("Telegram session not linked")
    return StringSession(encryption_manager.decrypt(row.session_encrypted))


async def read_channel(profile_id, username: str, limit: int = 10) -> list:
    from telethon import TelegramClient
    settings = get_settings()
    sess = await _make_session(profile_id)
    client = TelegramClient(sess, settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
    await client.connect()
    try:
        entity = await client.get_entity(username)
        texts = []
        async for msg in client.iter_messages(entity, limit=limit):
            if msg.text:
                texts.append(msg.text)
        return texts
    finally:
        await client.disconnect()


async def status(profile_id) -> dict:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(select(TelegramLink).where(TelegramLink.profile_id == profile_id))).scalar_one_or_none()
    if not row:
        return {"linked": False, "status": "none"}
    return {"linked": row.status == "active", "status": row.status, "phone": row.phone}


async def logout(profile_id) -> dict:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(select(TelegramLink).where(TelegramLink.profile_id == profile_id))).scalar_one_or_none()
        if row:
            row.status = "logged_out"
            row.session_encrypted = None
            await db.commit()
    _pending.pop(str(profile_id), None)
    return {"ok": True, "status": "logged_out"}