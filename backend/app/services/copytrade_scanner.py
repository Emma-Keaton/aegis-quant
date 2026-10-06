"""Copy-trade scanner — polls watched channels, parses each message with the
parser model, confidence-tests it, and executes + persists trades as Intel cards.

Message sources:
  - Telegram channels via Telethon (when MTProto credentials are configured).
  - Every registered channel is polled, decoded by the Groq "parser model",
    gated by the subscription's confidence threshold, then routed to execution.
"""
import hashlib
import logging
import time
from collections import OrderedDict
from typing import List

from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal, AsyncSession
from app.models import Profile, CopyTradeSubscription
from app.services import channel_feed
from app.services.signal_parser import parse_signal_text
from app.services.trade_executor import execute_parsed_signal

logger = logging.getLogger(__name__)

# The scanner polls the same channel every cycle, so the last N messages are
# seen repeatedly. Without this ledger every qualifying message would be traded
# again on each pass. Keyed by channel + message text (fetch_channel returns
# text only, no message ids) and aged out so a genuinely repeated call signal
# later in the day can still trade.
_PROCESSED_TTL_SECONDS = 6 * 3600
_MAX_PROCESSED = 4096
_processed: "OrderedDict[str, float]" = OrderedDict()


def _fingerprint(channel_id: str, text: str) -> str:
    return hashlib.sha256(f"{channel_id}\n{text}".encode("utf-8")).hexdigest()


def _already_processed(fingerprint: str) -> bool:
    now = time.monotonic()
    for key in [k for k, ts in _processed.items() if now - ts > _PROCESSED_TTL_SECONDS]:
        _processed.pop(key, None)
    return fingerprint in _processed


def _mark_processed(fingerprint: str) -> None:
    _processed[fingerprint] = time.monotonic()
    _processed.move_to_end(fingerprint)
    while len(_processed) > _MAX_PROCESSED:
        _processed.popitem(last=False)


async def fetch_channel_messages(channel_id: str, limit: int = 5) -> List[str]:
    """Fetch recent raw messages from a watched Telegram channel."""
    settings = get_settings()
    if not (settings.TELEGRAM_API_ID and settings.TELEGRAM_API_HASH and settings.TELEGRAM_PHONE):
        return []
    try:
        from telethon import TelegramClient
    except ImportError:
        logger.warning("telethon not installed — cannot poll %s", channel_id)
        return []
    try:
        client = TelegramClient("aegis_scan_session", settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            await client.send_code_request(settings.TELEGRAM_PHONE)
            return []
        entity = await client.get_entity(channel_id)
        texts = []
        async for msg in client.iter_messages(entity, limit=limit):
            if msg.text:
                texts.append(msg.text)
        await client.disconnect()
        return texts
    except Exception as e:
        logger.warning("Telethon poll failed for %s: %s", channel_id, e)
        try:
            await client.disconnect()
        except Exception:
            pass
        return []


async def run_copytrade_scan_once() -> dict:
    """Scan all active copy-trade channels once: parse → confidence → execute."""
    tally = {"scanned": 0, "parsed": 0, "executed": 0, "skipped": 0}
    async with AsyncSessionLocal() as db:
        subs = (await db.execute(
            select(CopyTradeSubscription).where(CopyTradeSubscription.active == True)
        )).scalars().all()
        if not subs:
            return tally

        for sub in subs:
            profile = await db.get(Profile, sub.profile_id)
            if profile is None or not profile.bot_enabled:
                tally["skipped"] += 1
                continue

            messages = await channel_feed.fetch_channel(sub.channel_id, limit=5, profile_id=sub.profile_id)
            if not messages:
                continue

            threshold = sub.confidence_threshold if sub.confidence_threshold is not None else 70
            for text in messages:
                tally["scanned"] += 1
                fingerprint = _fingerprint(sub.channel_id, text)
                if _already_processed(fingerprint):
                    tally["skipped"] += 1
                    continue
                parsed = await parse_signal_text(text)
                if not parsed:
                    continue
                tally["parsed"] += 1
                if int(parsed.get("confidence") or 0) < threshold:
                    tally["skipped"] += 1
                    continue
                # Claim the message before executing so a failing trade is not
                # retried (and re-billed) on every subsequent poll.
                _mark_processed(fingerprint)
                try:
                    res = await execute_parsed_signal(
                        sub.profile_id, parsed, source=f"telegram:{sub.channel_id}"
                    )
                    if res.get("executed"):
                        tally["executed"] += 1
                    else:
                        tally["skipped"] += 1
                except Exception as e:
                    logger.warning("copytrade execute failed for %s: %s", sub.channel_id, e)
                    tally["skipped"] += 1

    logger.info("Copy-trade scan complete: %s", tally)
    return tally