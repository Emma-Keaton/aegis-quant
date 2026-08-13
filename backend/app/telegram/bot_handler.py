"""Telegram bot handler — processes /start and other commands for Aegis Quant.

The bot launches the Mini App via a Telegram WebApp inline keyboard button
(t.me/<bot_username>/app), which passes a signed initData to the frontend.
"""

import asyncio
import logging
import html
import json
import re
from typing import Optional, Dict, Any

from fastapi import HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone
from sqlalchemy import select

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
    """Process incoming user message from the Telegram webhook.

    Routes slash-commands to dedicated handlers and sends free-text to the
    assistant (which can execute trades, watch tokens, show status, or answer).
    """
    logger.info(f"[Bot] Message from chat={chat_id}, user={user.get('username')}, text={text[:50]}...")
    txt = (text or "").strip()
    low = txt.lower()

    if low.startswith("/start"):
        await _cmd_start(chat_id, user)
    elif low.startswith("/help"):
        await send_message(chat_id, _help_text())
    elif low.startswith("/profile"):
        await _cmd_profile(chat_id)
    elif low.startswith("/mode"):
        await _cmd_mode(chat_id, txt)
    elif low.startswith("/toggle_bot") or low.startswith("/toggle "):
        await _cmd_toggle_bot(chat_id, txt)
    elif low.startswith("/signals"):
        await _cmd_signals(chat_id)
    elif low.startswith("/balance"):
        await _cmd_balance(chat_id)
    elif low.startswith("/watch"):
        await _cmd_watch(chat_id, txt)
    elif low.startswith("/trade"):
        await _cmd_trade(chat_id, txt, user)
    elif low.startswith("/scan"):
        await _cmd_scan(chat_id, user)
    elif low.startswith("/connect"):
        await _cmd_connect(chat_id, user)
    elif low.startswith("/sources"):
        await _cmd_sources(chat_id, user)
    else:
        await _chat_reply(chat_id, txt, user)


def _help_text() -> str:
    return (
        "Aegis Quant Trading Bot\n"
        "• /start — Launch the Mini App\n"
        "• /profile — View your trading profile\n"
        "• /mode paper|live — Set trading mode\n"
        "• /toggle_bot on|off — Enable/disable trading agent\n"
        "• /signals — View recent signals\n"
        "• /balance — View paper balance & positions\n"
        "• /watch SOL — Add a token to the watchlist\n"
        "• /trade buy 500 SOL — Take a trade\n"
        "• /scan — Run a copy-trade channel scan\n"
        "• /connect — Link your Telegram account to read private channels\n"
        "• /sources — List your watched channels/sources\n"
        "\nYou can also just chat: ask questions, or say "
        "'buy $200 of SOL', 'show my balance', or 'watch TON'."
    )


async def _cmd_start(chat_id: int, user: Dict[str, Any]) -> None:
    welcome = (
        f"Welcome to Aegis Quant, {user.get('first_name', 'trader')}! 🛡️\n\n"
        "Your AI-powered crypto trading copilot. Tap the button below to open the "
        "app, connect wallets, set risk limits, and activate the trading agents."
    )
    await send_message(chat_id, welcome, reply_markup=_webapp_keyboard())


async def _profile(telegram_id: int):
    async with AsyncSessionLocal() as db:
        return (await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))).scalar_one_or_none()


async def _cmd_profile(chat_id: int) -> None:
    p = await _profile(chat_id)
    if not p:
        await send_message(chat_id, "No profile found yet. Send /start to create one.", reply_markup=_webapp_keyboard())
        return
    mode = p.trading_mode.value if hasattr(p.trading_mode, "value") else p.trading_mode
    risk = p.risk_level.value if hasattr(p.risk_level, "value") else p.risk_level
    await send_message(
        chat_id,
        f"📊 Profile\n• Mode: `{mode}`\n• Bot: {'enabled' if p.bot_enabled else 'disabled'}\n• Risk: `{risk}`",
    )


async def _cmd_mode(chat_id: int, txt: str) -> None:
    parts = txt.split()
    mode = (parts[1] if len(parts) > 1 else "").lower()
    if mode not in ("paper", "live"):
        await send_message(chat_id, "Usage: /mode paper|live")
        return
    from app.models import TradeMode
    async with AsyncSessionLocal() as db:
        p = (await db.execute(select(Profile).where(Profile.telegram_id == chat_id))).scalar_one_or_none()
        if not p:
            p = Profile(telegram_id=chat_id, trading_mode=TradeMode.PAPER if mode == "paper" else TradeMode.LIVE)
            db.add(p)
        else:
            p.trading_mode = TradeMode.PAPER if mode == "paper" else TradeMode.LIVE
        await db.commit()
    await send_message(chat_id, f"✅ Trading mode set to _{mode.upper()}_.")


async def _cmd_toggle_bot(chat_id: int, txt: str) -> None:
    parts = txt.split()
    arg = (parts[1] if len(parts) > 1 else "on").lower()
    val = arg not in ("off", "0", "false", "disable", "down")
    async with AsyncSessionLocal() as db:
        p = (await db.execute(select(Profile).where(Profile.telegram_id == chat_id))).scalar_one_or_none()
        if not p:
            p = Profile(telegram_id=chat_id, bot_enabled=val)
            db.add(p)
        else:
            p.bot_enabled = val
        await db.commit()
    await send_message(chat_id, f"🤖 Trading agent {'enabled' if val else 'disabled'}.")


async def _cmd_signals(chat_id: int) -> None:
    from app.models import Signal
    async with AsyncSessionLocal() as db:
        sigs = (await db.execute(select(Signal).order_by(Signal.created_at.desc()).limit(5))).scalars().all()
    if not sigs:
        await send_message(chat_id, "No signals yet. Run /scan or wait for the agent to scan.")
        return
    lines = [f"• {s.ticker or ''} — {s.badge or ''} ({s.source or ''})" for s in sigs]
    await send_message(chat_id, "📶 Recent signals:\n" + "\n".join(lines))


async def _cmd_balance(chat_id: int) -> None:
    from app.models import PaperBalance, Position, UserCredential
    async with AsyncSessionLocal() as db:
        p = (await db.execute(select(Profile).where(Profile.telegram_id == chat_id))).scalar_one_or_none()
        if not p:
            await send_message(chat_id, "No profile yet. Send /start.")
            return
        pb = (await db.execute(select(PaperBalance).where(PaperBalance.profile_id == p.id))).scalar_one_or_none()
        pos = (await db.execute(
            select(Position).where(Position.profile_id == p.id, Position.is_closed == False)
        )).scalars().all()
        cexs = (await db.execute(
            select(UserCredential).where(UserCredential.profile_id == p.id, UserCredential.is_active == True)
        )).scalars().all()
        paper = float(pb.balance) if pb and pb.balance is not None else 0.0
        wallet_connected = p.wallet_connected
        wallet_net = p.wallet_network
        wallet_addr = p.wallet_address
        mode = p.trading_mode.value if hasattr(p.trading_mode, "value") else p.trading_mode

    lines = []
    if mode == "live":
        # 1) On-chain wallet balance (TON / EVM / Solana).
        if wallet_connected and wallet_addr:
            from app.services.chain_balance import chain_balance, map_wallet_network
            res = await chain_balance(map_wallet_network(wallet_net), wallet_addr)
            if res.get("status") == "success" and res.get("balance") is not None:
                sym = res.get("symbol") or ""
                lines.append(f"🪙 Wallet ({res['network'].upper()}): {res['balance']:,.4f} {sym}")
        # 2) Every connected CEX (Bybit, OKX, Binance, ...).
        from app.engines.execution_router import ExecutionRouter
        router = ExecutionRouter()
        for cex in cexs:
            try:
                bal = await router.get_balance(p, cex.exchange)
                if bal:
                    lines.append(f"🏦 {cex.exchange.title()}: " + ", ".join(f"{k} {v:,.4f}" for k, v in bal.items()))
                else:
                    lines.append(f"🏦 {cex.exchange.title()}: 0")
            except Exception:
                lines.append(f"🏦 {cex.exchange.title()}: unavailable")
        if not lines:
            lines.append("💰 No live balances available. Link a wallet or exchange keys.")
    else:
        lines.append(f"💰 Paper balance: `${paper:,.2f}`")

    await send_message(chat_id, "\n".join(lines) + f"\n📈 Open positions: {len(pos)}\n🛡️ Mode: {mode}")


async def _cmd_watch(chat_id: int, txt: str) -> None:
    from app.models import UserWhitelist
    parts = txt.split()
    symbol = (parts[1].upper() if len(parts) > 1 else "").lstrip("$")
    if not symbol:
        await send_message(chat_id, "Usage: /watch SOL")
        return
    async with AsyncSessionLocal() as db:
        p = (await db.execute(select(Profile).where(Profile.telegram_id == chat_id))).scalar_one_or_none()
        if not p:
            await send_message(chat_id, "No profile yet. Send /start.")
            return
        ex = (await db.execute(select(UserWhitelist).where(
            UserWhitelist.profile_id == p.id, UserWhitelist.symbol == symbol
        ))).scalar_one_or_none()
        if ex:
            ex.active = True
        else:
            db.add(UserWhitelist(profile_id=p.id, symbol=symbol, exchange="bybit", active=True))
        await db.commit()
    await send_message(chat_id, f"✅ Added `{symbol}` to your watchlist.")


async def _cmd_trade(chat_id: int, txt: str, user: Dict[str, Any]) -> None:
    parts = txt.split()
    if len(parts) < 3:
        await send_message(chat_id, "Usage: /trade buy 100 SOL")
        return
    side = parts[1].lower()
    size_raw = parts[2].replace(",", "")
    size = float(size_raw) if size_raw.replace(".", "").isdigit() else None
    symbol = parts[3].upper().lstrip("$") if len(parts) > 3 else None
    if side not in ("buy", "sell") or not symbol or size is None:
        await send_message(chat_id, "Usage: /trade buy 100 SOL (side, amount, symbol)")
        return
    p = await _profile(chat_id)
    if not p:
        await send_message(chat_id, "No profile yet. Send /start.", reply_markup=_webapp_keyboard())
        return
    from app.services.trade_executor import execute_parsed_signal
    parsed = {"symbol": symbol, "side": side, "size": size, "confidence": 90,
              "reason": f"User instructed {side} {size} {symbol}"}
    res = await execute_parsed_signal(p.id, parsed, source="telegram-bot")
    if res.get("executed"):
        await send_message(chat_id, f"✅ Executed {side.upper()} {symbol} (${size:,.0f} notional).")
    else:
        await send_message(chat_id, f"⚠️ Not executed: {res.get('reason', 'unknown reason')}")


async def _cmd_scan(chat_id: int, user: Dict[str, Any]) -> None:
    from app.services.copytrade_scanner import run_copytrade_scan_once
    await send_message(chat_id, "🔄 Scanning copy-trade channels...")
    tally = await run_copytrade_scan_once()
    await send_message(
        chat_id,
        f"Scan complete — parsed {tally.get('parsed', 0)}, executed {tally.get('executed', 0)}, "
        f"scanned {tally.get('scanned', 0)} message(s).",
    )


async def _profile_id(chat_id: int):
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Profile).where(Profile.telegram_id == chat_id))
        return res.scalar_one_or_none()


async def _cmd_connect(chat_id: int, user: Dict[str, Any]) -> None:
    """Link the user's Telegram account to read private channels (phone + OTP)."""
    from app.services import telegram_link
    profile = await _profile_id(chat_id)
    if profile is None:
        await send_message(
            chat_id,
            "No profile found — launch the Mini App from /start first, "
            "then run /connect to link your Telegram account.",
        )
        return
    st = await telegram_link.status(profile.id)
    if st.get("linked"):
        await send_message(
            chat_id,
            f"🔗 Telegram account already linked: {st.get('phone','')}. "
            "Use the Intel page in the Mini App to watch private channels.",
        )
        return
    await send_message(
        chat_id,
        "🔐 To read private Telegram channels, link your Telegram account.\n\n"
        "1. Open the Mini App (/start → Launch Aegis Quant)\n"
        "2. Go to the Intel page → Source Linker → TELEGRAM ACCOUNT\n"
        "3. Enter your phone number, then the one-time code Telegram sends.\n\n"
        "This lets Aegis follow channels you belong to and parse them into signals.",
    )


async def _cmd_sources(chat_id: int, user: Dict[str, Any]) -> None:
    """List the user's watched channels/sources and their status."""
    from app.models.sources import UserSource
    profile = await _profile_id(chat_id)
    if profile is None:
        await send_message(chat_id, "No profile found — launch the app from /start first.")
        return
    try:
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                select(UserSource).where(UserSource.profile_id == profile.id)
            )
            sources = res.scalars().all()
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"[Bot] sources listing failed: {e}")
        sources = []
    if not sources:
        await send_message(
            chat_id,
            "📡 No watched sources yet. Add channels in the Mini App "
            "(Intel → Source Linker), or /watch SOL to track a token.",
        )
        return
    lines = ["📡 Watched sources:"]
    for s in sources[:15]:
        flag = "✅" if getattr(s, "enabled", False) else "⛔"
        lines.append(f"{flag} {getattr(s,'name','?')} ({getattr(s,'source_type','?')})")
    lines.append(f"\n{len(sources)} tracked total.")
    await send_message(chat_id, "\n".join(lines))


def _pick_token(text: str) -> str:
    m = re.search(r"\b(SOL|TON|ETH|BTC|PEPE|BONK|WIF|AVAX|DOT|DOGE)\b", text.upper())
    return m.group(1) if m else ""


async def _free_trade(chat_id: int, text: str) -> None:
    side = "buy" if re.search(r"\b(buy|long)\b", text.lower()) else "sell"
    m = re.search(r"\$?\s*([\d,]+(?:\.\d+)?)", text)
    size = float(m.group(1).replace(",", "")) if m else None
    sym = _pick_token(text).lstrip("$")
    if size is None or not sym:
        await send_message(chat_id, "Got it — tell me the amount and token, e.g. 'buy $200 of SOL'.")
        return
    await _cmd_trade(chat_id, f"/trade {side} {size} {sym}", {})


async def _chat_reply(chat_id: int, text: str, user: Dict[str, Any]) -> None:
    low = " " + text.lower() + " "

    if any(w in low for w in (" buy ", " sell ", " long ", " short ")):
        await _free_trade(chat_id, text)
        return
    if any(w in low for w in ("watch ", "track ", "add ")):
        sym = _pick_token(text)
        if sym:
            await _cmd_watch(chat_id, "watch " + sym)
            return
    if any(w in low for w in ("balance", "portfolio", "position", "pnl", "holdings", "profit", "loss", "how much")):
        await _cmd_balance(chat_id)
        return
    if any(w in low for w in ("signal", "opportunit", "scan", "watchlist", "trending")):
        await _cmd_signals(chat_id)
        return
    if any(w in low for w in ("help", "commands", "what can", "how do")):
        await send_message(chat_id, _help_text())
        return
    await send_message(
        chat_id,
        "I'm your Aegis Quant copilot. I can **execute trades** ('buy $200 of SOL'), "
        "**watch tokens** ('watch TON'), show **signals** or your **balance**, or run "
        "a **/scan**. Send /help for commands.",
    )


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
