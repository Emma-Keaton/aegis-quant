"""Channel feed fetcher.

Resolves a watched channel into recent message texts:
  - Public channels  -> RSS (RSSHub) or the t.me/s web preview (no login needed).
  - Private channels -> Telethon user-session read (see telegram_link).
"""
import html
import logging
import re
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

_USERNAME_RE = re.compile(r"(?:t\.me/|@)([A-Za-z0-9_]+)")
_TEXT_BLOCK_RE = re.compile(
    r"tgme_widget_message_text[^>]*>(.*?)</div>",
    re.S,
)


def channel_username(channel: str) -> str:
    """Extract a raw username/handle from a Telegram channel reference."""
    if not channel:
        return ""
    m = _USERNAME_RE.search(channel)
    if m:
        return m.group(1)
    cleaned = channel.strip().strip("@").strip("/")
    if "/" in cleaned:
        cleaned = cleaned.split("/")[-1]
    return cleaned


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(text).strip()


async def fetch_public(channel: str, limit: int = 10) -> List[str]:
    """Fetch message texts from a public channel via RSS or its web preview."""
    user = channel_username(channel)
    if not user:
        return []

    # 1) RSSHub (best structured source for public channels).
    texts = await _rsshub(user, limit)
    if texts:
        return texts

    # 2) Fallback: the public t.me/s web preview.
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as c:
            r = await c.get(f"https://t.me/s/{user}")
            if r.status_code == 200:
                blocks = _TEXT_BLOCK_RE.findall(r.text)
                cleaned = [_strip_html(b) for b in blocks]
                return [t for t in cleaned if t][:limit]
    except Exception as e:
        logger.debug("t.me/s fetch failed for %s: %s", user, e)
    return []


async def _rsshub(user: str, limit: int) -> List[str]:
    try:
        import feedparser
        urls = [
            f"https://rsshub.app/telegram/channel/{user}",
            f"https://rsshub.rssforever.com/telegram/channel/{user}",
        ]
        for url in urls:
            try:
                async with httpx.AsyncClient(timeout=12, follow_redirects=True) as c:
                    r = await c.get(url)
                if r.status_code != 200:
                    continue
                feed = feedparser.parse(r.text)
                entries = feed.entries[:limit]
                cleaned = []
                for e in entries:
                    body = e.get("summary") or ""
                    if not body and isinstance(e.get("content"), list):
                        body = e["content"][0].get("value", "")
                    if body:
                        cleaned.append(_strip_html(body))
                cleaned = [t for t in cleaned if t]
                if cleaned:
                    return cleaned
            except Exception as e:
                logger.debug("RSSHub %s failed: %s", url, e)
    except Exception as e:
        logger.debug("feedparser unavailable: %s", e)
    return []


async def fetch_channel(channel: str, limit: int = 10,
                        profile_id: Optional[str] = None) -> List[str]:
    """Fetch a channel, using the user's Telethon session for private ones."""
    user = channel_username(channel)
    texts = await fetch_public(channel, limit)
    if texts or not user:
        return texts
    # Not public -> try the user's private session if linked.
    if profile_id:
        from app.services import telegram_link
        try:
            return await telegram_link.read_channel(profile_id, user, limit)
        except Exception as e:
            logger.warning("private read failed for %s: %s", user, e)
            return []
    return []