"""Telegram bot registration — sets bot commands and the webhook URL.

Called at API startup (web role) or manually via `python -m app.telegram.registration`.
"""

import asyncio
import logging
import os
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def _api_url(path: str) -> str:
    settings = get_settings()
    return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}{path}"


def public_base_url(settings=None) -> str:
    """Resolve the canonical public API base URL and force HTTPS.

    Priority: RENDER_EXTERNAL_URL (Render provides this) → PUBLIC_URL →
    API_PUBLIC_URL. Telegram only accepts HTTPS webhooks (except localhost), so
    we rewrite an ``http://`` URL to ``https://`` unless the host is localhost.
    """
    settings = settings or get_settings()
    base = (
        os.getenv("RENDER_EXTERNAL_URL") or settings.PUBLIC_URL or settings.API_PUBLIC_URL or ""
    ).strip().rstrip("/")
    if not base:
        return ""
    if base.startswith("http://"):
        base = "https://" + base[len("http://"):]
    return base


def webhook_url() -> Optional[str]:
    """Build the HTTPS webhook URL for the bot, or None if it can't be HTTPS."""
    base = public_base_url()
    if not base:
        return None
    url = f"{base}/api/telegram/webhook"
    # Telegram allows plain HTTP only for localhost/loopback.
    if url.startswith("http://") and "localhost" not in base and "127.0.0.1" not in base:
        url = "https://" + url[len("http://"):]
    if not url.startswith("https://"):
        return None
    return url


async def register_bot_commands() -> dict:
    """Set the bot's command list (shown in the Telegram menu)."""
    settings = get_settings()
    commands = [
        {"command": c["command"], "description": c["description"]}
        for c in settings.BOT_COMMANDS
    ]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(_api_url("/setMyCommands"), json={"commands": commands})
    data = resp.json()
    if not data.get("ok"):
        logger.warning(f"setMyCommands failed: {data}")
    return data


async def register_webhook() -> dict:
    """Point Telegram's webhook at the API service (HTTPS enforced)."""
    settings = get_settings()
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping webhook registration")
        return {"ok": False, "description": "TELEGRAM_BOT_TOKEN not set"}

    url = webhook_url()
    if not url:
        base = public_base_url(settings)
        if not base:
            logger.warning("No public base URL configured (PUBLIC_URL / API_PUBLIC_URL / RENDER_EXTERNAL_URL) — not registering webhook")
            return {"ok": False, "description": "No public base URL configured"}
        logger.warning(f"Refusing to register non-HTTPS webhook for base '{base}' (Telegram requires HTTPS)")
        return {"ok": False, "description": f"Webhook URL must be HTTPS (got {base})"}

    payload = {
        "url": url,
        "secret_token": settings.TELEGRAM_WEBHOOK_SECRET or None,
        "allowed_updates": ["message", "callback_query", "inline_query", "channel_post"],
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(_api_url("/setWebhook"), json=payload)
    data = resp.json()
    if not data.get("ok"):
        logger.warning(f"setWebhook failed: {data}")
    else:
        logger.info(f"Telegram webhook registered → {url}")
    return data


async def register_bot() -> None:
    """Idempotent full registration (commands + webhook)."""
    try:
        await register_bot_commands()
    except Exception as e:
        logger.error(f"register_bot_commands failed: {e}")
    try:
        await register_webhook()
    except Exception as e:
        logger.error(f"register_webhook failed: {e}")


_KEEPALIVE_INTERVAL_SECONDS = 3600  # re-register webhook every hour
_keepalive_task: Optional["asyncio.Task"] = None


async def _keepalive_loop() -> None:
    """Periodically re-register bot commands + webhook.

    This makes the bot self-heal on Render, where the public URL can change
    (preview deploys get ephemeral onrender.com URLs, free-tier services get
    spun down/up) and where Telegram may be briefly unreachable at boot.
    """
    while True:
        await asyncio.sleep(_KEEPALIVE_INTERVAL_SECONDS)
        try:
            await register_bot_commands()
            await register_webhook()
            logger.info("Telegram webhook keepalive: commands + webhook re-registered")
        except Exception as e:
            logger.warning(f"Telegram webhook keepalive pass failed: {e}")


def start_webhook_keepalive() -> None:
    """Start the background keepalive task (idempotent)."""
    global _keepalive_task
    if _keepalive_task and not _keepalive_task.done():
        return
    _keepalive_task = asyncio.create_task(_keepalive_loop())


def stop_webhook_keepalive() -> None:
    """Cancel the background keepalive task."""
    global _keepalive_task
    if _keepalive_task and not _keepalive_task.done():
        _keepalive_task.cancel()
        _keepalive_task = None


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    commands = await register_bot_commands()
    print("setMyCommands:", commands)
    webhook = await register_webhook()
    print("setWebhook:", webhook)


if __name__ == "__main__":
    import asyncio

    asyncio.run(_main())
