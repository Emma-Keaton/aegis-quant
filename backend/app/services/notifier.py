"""Outbound Telegram notifications.

The bot in `app.telegram.bot_handler` already handles inbound commands. Nothing
was wired to notify on *outbound* events, so a trade could execute with no trace
in the user's chat.

Design constraints:

- **Never block a trade.** `_send` is fire-and-forget off the caller's path, and
  a Telegram outage must not roll back or delay an execution.
- **Never raise into the caller.** Failures are logged and counted.
- **Bounded.** Messages are rate limited per chat so a runaway scan loop cannot
  exhaust the bot's quota or spam a user.
- **Degrades to a no-op** when `TELEGRAM_BOT_TOKEN` is unset, so local and test
  environments need no configuration.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, Iterable, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

TELEGRAM_SEND_LIMIT = "https://api.telegram.org/bot{token}/sendMessage"

#: Per-chat sliding window. Telegram allows ~30 msg/s globally and ~1 msg/s per
#: chat; 20 per minute keeps a burst of trades readable as well as within quota.
WINDOW_SECONDS = 60.0
MAX_PER_WINDOW = 20

#: Telegram's hard message ceiling.
MAX_MESSAGE_CHARS = 4096


class Notifier:
    """Rate-limited, non-blocking Telegram sender."""

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._sent: Dict[int, Deque[float]] = defaultdict(deque)
        self._dropped = 0
        self._failed = 0
        self._sent_count = 0

    # -- plumbing ------------------------------------------------------------

    def _settings(self):
        return get_settings()

    def _http(self) -> Optional[httpx.AsyncClient]:
        if self._client is None:
            token = self._settings().TELEGRAM_BOT_TOKEN
            if not token:
                return None
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def enabled(self) -> bool:
        return bool(self._settings().TELEGRAM_BOT_TOKEN)

    def stats(self) -> Dict[str, int]:
        return {
            "sent": self._sent_count,
            "dropped_rate_limited": self._dropped,
            "failed": self._failed,
        }

    # -- rate limiting -------------------------------------------------------

    def _allow(self, chat_id: int) -> bool:
        now = time.monotonic()
        window = self._sent[chat_id]
        while window and now - window[0] > WINDOW_SECONDS:
            window.popleft()
        if len(window) >= MAX_PER_WINDOW:
            return False
        window.append(now)
        return True

    # -- sending -------------------------------------------------------------

    async def _send(
        self,
        chat_id: int,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send one message. Returns whether it was delivered."""
        if not chat_id:
            return False
        client = self._http()
        if client is None:
            return False
        if not self._allow(chat_id):
            self._dropped += 1
            logger.debug("Telegram rate limit hit for chat %s", chat_id)
            return False

        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text[:MAX_MESSAGE_CHARS],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            response = await client.post(
                TELEGRAM_SEND_LIMIT.format(token=self._settings().TELEGRAM_BOT_TOKEN),
                json=payload,
            )
            response.raise_for_status()
            self._sent_count += 1
            return True
        except Exception as exc:  # noqa: BLE001
            self._failed += 1
            logger.warning("Telegram send to %s failed: %s", chat_id, exc)
            return False

    async def notify(self, chat_id: int, text: str, **kwargs: Any) -> bool:
        """Public, never-raising send."""
        try:
            return await self._send(chat_id, text, **kwargs)
        except Exception as exc:  # noqa: BLE001
            self._failed += 1
            logger.warning("Telegram notify failed: %s", exc)
            return False

    def notify_soon(self, chat_id: int, text: str, **kwargs: Any) -> None:
        """Fire-and-forget send.

        This is what trade paths use. The task is scheduled and its exception
        swallowed, so a Telegram problem cannot delay or fail an execution.
        """
        if not self.enabled or not chat_id:
            return
        try:
            task = asyncio.create_task(self.notify(chat_id, text, **kwargs))
            task.add_done_callback(_swallow)
        except RuntimeError:
            # No running loop (sync context, e.g. a script). Drop rather than
            # block: an execution must never wait on Telegram.
            logger.debug("No event loop; skipping Telegram notification")

    # -- domain events -------------------------------------------------------

    async def trade_executed(
        self,
        chat_id: int,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        *,
        mode: str = "paper",
        confidence: Optional[int] = None,
        tx_hash: Optional[str] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Announce an executed or failed order."""
        if error:
            text = (
                f"❌ <b>{symbol}</b> {side.upper()} failed\n"
                f"Mode: {mode}\n"
                f"Reason: {html_escape(error)}"
            )
        else:
            conf = f"\nConfidence: {confidence}%" if confidence is not None else ""
            tx = f"\nTx: <code>{tx_hash}</code>" if tx_hash else ""
            # Omit the price line when it is unknown. Paper fills in aegis-quant
            # persist price=0, and reporting "Price: 0" reads as a data bug.
            price_line = f"\nPrice: {price:g}" if price else ""
            text = (
                f"✅ <b>{symbol}</b> {side.upper()} {amount:g}"
                f"{price_line}\nMode: {mode}{conf}{tx}"
            )
        return await self.notify(chat_id, text)

    async def signal(self, chat_id: int, symbol: str, direction: str, confidence: float, **extra: Any) -> bool:
        """Announce a signal the engines produced."""
        arrow = "📈" if direction.upper() == "UP" else "📉"
        detail = ""
        if extra.get("predicted_change") is not None:
            detail = f"\nChange: {float(extra['predicted_change']):+.2%}"
        band = ""
        low, high = extra.get("terminal_low"), extra.get("terminal_high")
        if low and high:
            band = f"\n90% band: {float(low):g} - {float(high):g}"
        text = (
            f"{arrow} <b>{html_escape(symbol)}</b> {direction.upper()}\n"
            f"Confidence: {float(confidence):.0%}{detail}{band}"
        )
        return await self.notify(chat_id, text)

    async def watch_added(self, chat_id: int, symbol: str) -> bool:
        return await self.notify(chat_id, f"👁 Watching <b>{html_escape(symbol)}</b>")

    async def watch_removed(self, chat_id: int, symbol: str) -> bool:
        return await self.notify(chat_id, f"👁 Stopped watching <b>{html_escape(symbol)}</b>")

    async def engine_status(self, chat_id: int, enabled: bool, symbols: Iterable[str] = ()) -> bool:
        state = "enabled" if enabled else "disabled"
        watched = ", ".join(symbols) if symbols else "none"
        return await self.notify(
            chat_id, f"🤖 Agent {state}\nWatching: {html_escape(watched)}"
        )

    async def calibration(self, chat_id: int, summary: Dict[str, Any]) -> bool:
        """Report observed Kronos accuracy.

        Sent because `confidence` is uncalibrated until enough scored forecasts
        exist; this is the number that says whether it can be trusted yet.
        """
        scored = summary.get("scored", 0)
        if not scored:
            return await self.notify(
                chat_id, "📊 Kronos calibration: not enough scored forecasts yet."
            )
        hit = summary.get("hit_rate")
        band = summary.get("within_90_band")
        hit_line = f"Hit rate: {hit:.0%}" if hit is not None else "Hit rate: n/a"
        text = f"📊 <b>Kronos calibration</b>\nScored: {scored}\n{hit_line}"
        if band is not None:
            text += f"\nWithin 90% band: {band:.0%}"
        return await self.notify(chat_id, text)


def _swallow(task: asyncio.Task) -> None:
    """Retrieve a task's exception so asyncio does not log it as unhandled."""
    try:
        task.exception()
    except asyncio.CancelledError:
        pass


def html_escape(value: Any) -> str:
    """Escape untrusted text for Telegram's HTML parse mode."""
    import html as _html

    return _html.escape(str(value), quote=False)



# Global notifier
notifier = Notifier()


def notify_trade_soon(chat_id: int, **kwargs: Any) -> None:
    """Fire-and-forget trade announcement.

    This is what the engines call. Scheduling the coroutine keeps a Telegram round
    trip off the execution path, so a slow or unreachable Telegram API can neither
    delay nor fail a trade.
    """
    if not notifier.enabled or not chat_id:
        return
    try:
        task = asyncio.create_task(notifier.trade_executed(chat_id, **kwargs))
        task.add_done_callback(_swallow)
    except RuntimeError:
        logger.debug("No event loop; skipping trade notification")