"""Whale flow collector (port of beast-trader's whalewatch, Helius).

Observations only: large movements of tracked mints are recorded and surfaced
(discrete Signal card + Telegram ping) but never trigger a trade by
themselves — the promotion gate stays the only path from evidence to orders.

Disabled loudly without a key: no `HELIUS_API_KEY` means zero network calls
and a single log line, not one per tick. Every call spends a rate-window slot
and 10 credits of the monthly allowance; an exhausted budget skips the mint.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

import httpx

from app.config import get_settings
from app.services import quota

logger = logging.getLogger(__name__)

HELIUS_BASE = "https://api.helius.xyz"
DEX_BASE = "https://api.dexscreener.com"
DEFAULT_TIMEOUT_MS = 8000
WHALE_TX_LIMIT = 100

DEFAULT_MINTS: Dict[str, str] = {}
_logged_disabled = False


def tracked_mints() -> Dict[str, str]:
    """symbol -> mint. Defaults to the stables/wrapped SOL the app quotes."""
    from app.services.jupiter_client import SOL_MINT, USDC_MINT, USDT_MINT

    raw = get_settings().WHALE_MINTS if hasattr(get_settings(), "WHALE_MINTS") else ""
    if isinstance(raw, str) and ":" in raw:
        out: Dict[str, str] = {}
        for part in raw.split(","):
            pieces = [s.strip() for s in part.split(":")]
            if len(pieces) == 2 and all(pieces):
                out[pieces[0].upper()] = pieces[1]
        if out:
            return out
    return {"SOL": SOL_MINT, "USDC": USDC_MINT, "USDT": USDT_MINT}


# ── fetching (network, budgeted) ────────────────────────────────────────────

async def _fetch_json(url: str) -> Optional[object]:
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_MS / 1000) as client:
            resp = await client.get(url, headers={"accept": "application/json"})
            if resp.status_code != 200:
                return None
            return resp.json()
    except Exception:
        return None


async def fetch_transactions(address: str, api_key: str) -> Optional[List[dict]]:
    if not api_key:
        return None
    url = (
        f"{HELIUS_BASE}/v0/addresses/{address}/transactions"
        f"?api-key={api_key}&limit={WHALE_TX_LIMIT}&commitment=confirmed"
    )
    payload = await _fetch_json(url)
    return payload if isinstance(payload, list) else None


async def fetch_token_price_usd(mint: str, symbol: str = "") -> Optional[float]:
    if symbol in ("USDC", "USDT", "USD"):
        return 1.0
    if not quota.dexscreener_pairs.take():
        return None
    payload = await _fetch_json(f"{DEX_BASE}/latest/dex/tokens/{mint}")
    pairs = (payload or {}).get("pairs") if isinstance(payload, dict) else None
    best_price, best_liq = None, -1.0
    for pair in pairs or []:
        try:
            price = float(pair.get("priceUsd"))
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        try:
            liq = float((pair.get("liquidity") or {}).get("usd") or 0)
        except (TypeError, ValueError):
            liq = 0.0
        if liq > best_liq:
            best_price, best_liq = price, liq
    return best_price


# ── parsing (pure) ──────────────────────────────────────────────────────────

def _ui_amount(transfer: dict) -> float:
    try:
        ui = float(transfer.get("tokenAmount"))
        if ui > 0:
            return ui
    except (TypeError, ValueError):
        pass
    try:
        raw = float((transfer.get("rawTokenAmount") or {}).get("tokenAmount"))
        decimals = float((transfer.get("rawTokenAmount") or {}).get("decimals"))
        if raw > 0:
            return raw / (10 ** decimals)
    except (TypeError, ValueError):
        pass
    return float("nan")


def parse_whale_flow(tx: dict, *, mint: str, symbol: str, price_usd: float,
                     chain: str = "solana", min_usd: float = 50_000.0) -> List[dict]:
    """One enhanced transaction → zero or more flow rows (pure)."""
    if not isinstance(tx, dict):
        return []
    signature = tx.get("signature")
    if not isinstance(signature, str) or not signature:
        return []
    transfers = tx.get("tokenTransfers")
    if not isinstance(transfers, list) or not mint:
        return []
    try:
        ts_sec = float(tx.get("timestamp"))
    except (TypeError, ValueError):
        return []
    if ts_sec <= 0:
        return []
    ts = datetime.fromtimestamp(ts_sec, tz=timezone.utc)
    try:
        price = float(price_usd)
    except (TypeError, ValueError):
        return []
    if price <= 0:
        return []

    is_swap = tx.get("type") == "SWAP" or bool((tx.get("events") or {}).get("swap"))
    fee_payer = tx.get("feePayer") if isinstance(tx.get("feePayer"), str) else None

    rows: List[dict] = []
    for transfer in transfers:
        if transfer.get("mint") != mint:
            continue
        amount = _ui_amount(transfer)
        if not (amount > 0):
            continue
        usd = amount * price
        if usd < min_usd:
            continue
        sender = transfer.get("fromUserOwner")
        receiver = transfer.get("toUserOwner")
        if is_swap:
            wallet = fee_payer or sender or receiver
            if fee_payer and receiver == fee_payer:
                side = "buy"
            elif fee_payer and sender == fee_payer:
                side = "sell"
            else:
                side = "unknown"
        else:
            wallet = sender or fee_payer or receiver
            side = "unknown"
        if not wallet:
            continue
        rows.append({
            "wallet": wallet,
            "symbol": symbol,
            "chain": chain,
            "ts": ts,
            "side": side,
            "amount_usd": round(usd, 2),
            "token_amount": amount,
            "tx_signature": signature,
            "raw": tx,
        })
    return rows


def flow_key(row: dict) -> str:
    return f"{row['tx_signature']}|{row['symbol']}|{row['wallet']}|{row['side']}"


# ── persistence ─────────────────────────────────────────────────────────────

async def _known_keys() -> set:
    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models import WhaleFlow

    try:
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                select(WhaleFlow.tx_signature, WhaleFlow.symbol,
                       WhaleFlow.wallet, WhaleFlow.side)
                .order_by(WhaleFlow.ts.desc()).limit(3000)
            )).all()
        return {f"{r[0]}|{r[1]}|{r[2]}|{r[3]}" for r in rows}
    except Exception:
        return set()


async def persist_flows(rows: Sequence[dict]) -> int:
    if not rows:
        return 0
    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models import WhaleFlow

    stored = 0
    try:
        async with AsyncSessionLocal() as db:
            for row in rows:
                exists = (await db.execute(
                    select(WhaleFlow.id).where(
                        WhaleFlow.tx_signature == row["tx_signature"],
                        WhaleFlow.symbol == row["symbol"],
                        WhaleFlow.wallet == row["wallet"],
                        WhaleFlow.side == row["side"],
                    )
                )).first()
                if exists:
                    continue
                db.add(WhaleFlow(
                    wallet=row["wallet"],
                    symbol=row["symbol"],
                    chain=row.get("chain", "solana"),
                    ts=row["ts"],
                    side=row["side"],
                    amount_usd=row["amount_usd"],
                    token_amount=row.get("token_amount"),
                    tx_signature=row["tx_signature"],
                    raw=row.get("raw"),
                    created_at=datetime.now(timezone.utc),
                ))
                stored += 1
            await db.commit()
        return stored
    except Exception as exc:
        logger.warning("whalewatch persist failed: %s", exc)
        return 0


async def _surface_flows(rows: Sequence[dict]) -> None:
    """Discrete Signal card + Telegram ping for each newly stored flow."""
    from decimal import Decimal

    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models import Profile, Signal
    from app.services.notifier import notifier

    if not rows:
        return
    async with AsyncSessionLocal() as db:
        for row in rows:
            side_label = row["side"].upper() if row["side"] != "unknown" else "MOVE"
            db.add(Signal(
                engine="B",
                ticker=f"${row['symbol']}"[:20],
                category="whale",
                badge=f"${row['amount_usd']:,.0f}",
                source=f"whale:{row['chain']}",
                metric="Whale flow",
                analysis=(
                    f"{side_label} of ${row['amount_usd']:,.0f} "
                    f"({row.get('token_amount') or 0:,.2f} {row['symbol']}) "
                    f"by {row['wallet'][:8]}…{row['wallet'][-4:]}"
                ),
                confidence=80,
                action_label=f"WHALE {side_label}",
                liquidity_usd=Decimal(str(round(row["amount_usd"], 2))),
            ))
        profiles = (await db.execute(
            select(Profile).where(Profile.bot_enabled.is_(True))
        )).scalars().all()
        chat_ids = [p.telegram_id for p in profiles if p.telegram_id]
        await db.commit()

    if notifier.enabled:
        for chat_id in dict.fromkeys(chat_ids):
            for row in rows:
                side_label = row["side"].upper() if row["side"] != "unknown" else "MOVE"
                notifier.notify_soon(
                    chat_id,
                    f"🐋 Whale {side_label}: <b>{row['symbol']}</b> "
                    f"${row['amount_usd']:,.0f}\n"
                    f"Wallet: <code>{row['wallet'][:12]}…</code>",
                )


# ── collection ──────────────────────────────────────────────────────────────

async def collect_once(mints: Optional[Dict[str, str]] = None) -> dict:
    settings = get_settings()
    api_key = settings.HELIUS_API_KEY
    if not api_key:
        return {"enabled": False, "reason": "HELIUS_API_KEY not set", "fetched": 0, "stored": 0}

    mints = mints or tracked_mints()
    known = await _known_keys()
    seen: set = set()
    result = {"enabled": True, "fetched": 0, "parsed": 0, "stored": 0,
              "duplicates": 0, "budget_denied": 0, "prices_unavailable": 0}
    fresh: List[dict] = []

    for symbol, mint in mints.items():
        if not (quota.helius_standard.take()
                and quota.credits.spend(quota.CREDITS_PER_HELIUS_CALL)):
            result["budget_denied"] += 1
            continue
        txs = await fetch_transactions(mint, api_key)
        if txs is None:
            result["budget_denied"] += 1
            continue
        result["fetched"] += len(txs)
        price = await fetch_token_price_usd(mint, symbol)
        if price is None:
            result["prices_unavailable"] += 1
            continue
        for tx in txs:
            rows = parse_whale_flow(tx, mint=mint, symbol=symbol, price_usd=price,
                                    min_usd=settings.MIN_WHALE_USD)
            result["parsed"] += len(rows)
            for row in rows:
                key = flow_key(row)
                if key in known or key in seen:
                    result["duplicates"] += 1
                    continue
                seen.add(key)
                fresh.append(row)

    if fresh:
        result["stored"] = await persist_flows(fresh)
        if result["stored"]:
            await _surface_flows(fresh[: result["stored"]])
    return result


async def tick() -> dict:
    global _logged_disabled
    settings = get_settings()
    if not settings.WHALE_WATCH_ENABLED:
        return {"enabled": False, "fetched": 0, "stored": 0}
    try:
        result = await collect_once()
    except Exception as exc:
        logger.warning("whalewatch tick failed: %s", exc)
        return {"enabled": True, "fetched": 0, "stored": 0, "error": str(exc)}
    if not result.get("enabled"):
        if not _logged_disabled:
            logger.info("whalewatch: HELIUS_API_KEY not set — collection disabled")
            _logged_disabled = True
        return result
    _logged_disabled = False
    if result["stored"] or result["budget_denied"] or result["prices_unavailable"]:
        logger.info("whalewatch fetched=%s stored=%s dup=%s denied=%s no_price=%s",
                    result["fetched"], result["stored"], result["duplicates"],
                    result["budget_denied"], result["prices_unavailable"])
    return result
