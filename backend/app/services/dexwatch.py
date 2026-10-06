"""DEX snapshot collector + spike pings (port of beast-trader's dexwatch).

Rules carried over from the reference:

1. Observations only — snapshots feed features and alerts; they never place
   or size a trade.
2. Quota-bounded, degrading rather than failing — an exhausted budget returns
   what has been collected so far; a failed fetch skips the symbol.
3. Spike detection is additive: a liquidity-floored 1h move above the
   configured threshold pings Telegram once per symbol per cooldown, then
   goes back to storing rows.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence

import httpx

from app.config import get_settings
from app.services import quota

logger = logging.getLogger(__name__)

DEX_BASE = "https://api.dexscreener.com"
DEFAULT_TIMEOUT_MS = 8000

WATCH_CHAINS = ("solana", "ethereum", "base", "arbitrum", "bsc", "polygon", "avalanche")

MIN_POOL_LIQUIDITY_USD: Dict[str, float] = {
    "solana": 100_000.0,
    "ethereum": 500_000.0,
    "base": 100_000.0,
    "arbitrum": 100_000.0,
    "bsc": 100_000.0,
    "polygon": 100_000.0,
    "avalanche": 100_000.0,
}
FALLBACK_MIN_LIQUIDITY_USD = 20_000.0

DEFAULT_QUERIES: Dict[str, List[str]] = {
    "solana": ["SOL/USDC", "SOL/USDT", "BTC/USDC"],
    "ethereum": ["ETH/USDC", "ETH/USDT", "WBTC/USDC"],
    "base": ["ETH/USDC", "WETH/USDC"],
    "arbitrum": ["ETH/USDC", "ARB/USDC"],
    "bsc": ["BNB/USDT", "CAKE/USDT"],
    "polygon": ["MATIC/USDC", "WETH/USDC"],
    "avalanche": ["AVAX/USDC", "WAVAX/USDC"],
}

# symbol -> monotonic time of the last spike ping (cooldown ledger)
_spike_cooldown: Dict[str, float] = {}
_logged_budget = False


# ── pure parsing ────────────────────────────────────────────────────────────

def parse_pair(pair: dict) -> Optional[dict]:
    """One DexScreener pair → snapshot dict, or None when unusable."""
    if not isinstance(pair, dict):
        return None
    token = pair.get("baseToken") or {}
    address = token.get("address")
    if not address:
        return None
    try:
        price = float(pair.get("priceUsd"))
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None

    liq = (pair.get("liquidity") or {}).get("usd")
    vol = (pair.get("volume") or {}).get("h24")

    def _pc(key: str) -> Optional[float]:
        try:
            return float(pair.get(key))
        except (TypeError, ValueError):
            return None

    txns = pair.get("txns") or {}
    h24 = txns.get("h24") or {}

    def _tx(key: str) -> Optional[int]:
        try:
            return int(h24.get(key)) if h24.get(key) is not None else None
        except (TypeError, ValueError):
            return None

    return {
        "symbol": str(token.get("symbol") or "").upper(),
        "address": address,
        "chain": str(pair.get("chainId") or "solana"),
        "dex_id": pair.get("dexId"),
        "pair_address": pair.get("pairAddress"),
        "price_usd": price,
        "liquidity_usd": float(liq) if liq not in (None, "") else None,
        "volume_usd": float(vol) if vol not in (None, "") else None,
        # One window only — summing overlapping windows (h24+h1+m5, as the
        # reference did) inflates counts and makes them non-monotonic.
        "buys": _tx("buys"),
        "sells": _tx("sells"),
        "price_change_5m": _pc("priceChange5m"),
        "price_change_1h": _pc("priceChange1h"),
        "price_change_24h": _pc("priceChange24h"),
        "source": "dexscreener",
    }


def parse_pairs_response(payload: dict, chains: Optional[Sequence[str]] = None) -> List[dict]:
    pairs = (payload or {}).get("pairs") or []
    out = []
    for pair in pairs:
        row = parse_pair(pair)
        if row is None:
            continue
        if chains and row["chain"] not in chains:
            continue
        if not row["symbol"]:
            continue
        out.append(row)
    return out


def _rank_pref(row: dict) -> tuple:
    """Completeness first, then depth — the reference's ordering rule."""
    return (row.get("price_change_1h") is not None, row.get("liquidity_usd") or 0.0)


def rank_and_filter(rows: Iterable[dict], limit: int = 30,
                    min_liquidity_usd: float = FALLBACK_MIN_LIQUIDITY_USD) -> List[dict]:
    """One row per token address; prefer price-change completeness, then depth."""
    best: Dict[str, dict] = {}
    for row in rows:
        liq = row.get("liquidity_usd") or 0.0
        if liq < min_liquidity_usd:
            continue
        addr = row.get("address") or row.get("pair_address") or row.get("symbol")
        current = best.get(addr)
        if current is None or _rank_pref(row) > _rank_pref(current):
            best[addr] = row
    ranked = sorted(best.values(), key=_rank_pref, reverse=True)
    return ranked[:limit]


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


async def fetch_top_pairs(chain: str, queries: Optional[Sequence[str]] = None,
                          limit: int = 30) -> List[dict]:
    queries = list(queries or DEFAULT_QUERIES.get(chain, []))
    out: List[dict] = []
    for query in queries:
        if not quota.dexscreener_pairs.take():
            break
        payload = await _fetch_json(f"{DEX_BASE}/latest/dex/search?q={query}&chainId={chain}")
        if payload is None:
            continue
        out.extend(parse_pairs_response(payload, chains=[chain]))
    return rank_and_filter(out, limit=limit,
                           min_liquidity_usd=MIN_POOL_LIQUIDITY_USD.get(chain, FALLBACK_MIN_LIQUIDITY_USD))


# ── spike detection (pure) ──────────────────────────────────────────────────

def detect_spikes(rows: Sequence[dict], *, pct_1h: float, min_liquidity_usd: float,
                  history_map: Optional[Dict[str, List[float]]] = None,
                  z_min: float = 3.0) -> List[dict]:
    """Liquidity-floored 1h moves; optionally z-scored vs per-token history.

    History is `symbol -> [recent price_change_1h values]`. When a token has
    ≥8 history points and its move exceeds `z_min` standard deviations, it
    spikes even if below the fixed `pct_1h` threshold; the fixed threshold
    remains the fallback when history is thin.
    """
    spikes = []
    for row in rows:
        change = row.get("price_change_1h")
        liq = row.get("liquidity_usd") or 0.0
        if change is None or liq < min_liquidity_usd:
            continue
        change = float(change)
        hit = abs(change) >= pct_1h
        z_score = None
        if not hit and history_map is not None:
            hist = history_map.get(row.get("symbol")) or []
            if len(hist) >= 8:
                mean = sum(hist) / len(hist)
                var = sum((h - mean) ** 2 for h in hist) / len(hist)
                std = var ** 0.5
                if std > 0:
                    z_score = (change - mean) / std
                    hit = abs(z_score) >= z_min
        if hit:
            spikes.append({**row, "spike_pct": change, "z_score": z_score})
    return spikes


def _cooldown_ok(symbol: str) -> bool:
    settings = get_settings()
    last = _spike_cooldown.get(symbol)
    return last is None or (time.monotonic() - last) >= settings.DEX_SPIKE_COOLDOWN_SECONDS


def _mark_cooldown(symbol: str) -> None:
    _spike_cooldown[symbol] = time.monotonic()


async def _notify_spike(spikes: Sequence[dict]) -> None:
    from sqlalchemy import select

    from app.database import AsyncSessionLocal
    from app.models import Profile
    from app.services.notifier import notifier

    if not notifier.enabled or not spikes:
        return
    async with AsyncSessionLocal() as db:
        profiles = (await db.execute(
            select(Profile).where(Profile.bot_enabled.is_(True))
        )).scalars().all()
        chat_ids = [p.telegram_id for p in profiles if p.telegram_id]
    for chat_id in dict.fromkeys(chat_ids):
        for spike in spikes:
            notifier.notify_soon(
                chat_id,
                f"⚡ <b>{spike['symbol']}</b> spike {spike['spike_pct']:+.1f}% (1h)\n"
                f"Liquidity: ${(spike.get('liquidity_usd') or 0):,.0f}\n"
                f"Source: dexscreener {spike.get('chain', '')}",
            )


# ── persistence + tick ──────────────────────────────────────────────────────

async def persist_snapshots(rows: Sequence[dict]) -> int:
    if not rows:
        return 0
    from app.database import AsyncSessionLocal
    from app.models import DexSnapshot

    try:
        async with AsyncSessionLocal() as db:
            for row in rows:
                db.add(DexSnapshot(
                    symbol=row["symbol"],
                    address=row.get("address"),
                    chain=row.get("chain", "solana"),
                    dex_id=row.get("dex_id"),
                    pair_address=row.get("pair_address"),
                    price_usd=row.get("price_usd"),
                    liquidity_usd=row.get("liquidity_usd"),
                    volume_usd=row.get("volume_usd"),
                    price_change_5m=row.get("price_change_5m"),
                    price_change_1h=row.get("price_change_1h"),
                    price_change_24h=row.get("price_change_24h"),
                    buys=row.get("buys"),
                    sells=row.get("sells"),
                    source=row.get("source", "dexscreener"),
                    raw=row,
                    ts=datetime.now(timezone.utc),
                ))
            await db.commit()
        return len(rows)
    except Exception as exc:
        logger.warning("dexwatch persist failed: %s", exc)
        return 0


async def collect_once(chains: Optional[Sequence[str]] = None, limit: int = 30) -> dict:
    settings = get_settings()
    chains = list(chains if chains is not None else settings.DEX_WATCH_CHAINS.split(","))
    chains = [c.strip() for c in chains if c.strip()] or ["solana"]

    result = {"fetched": 0, "stored": 0, "budget_denied": 0, "spikes": 0, "rows": []}
    all_rows: List[dict] = []
    for chain in chains:
        if quota.dexscreener_pairs.remaining() <= 0:
            result["budget_denied"] += 1
            continue
        rows = await fetch_top_pairs(chain, limit=limit)
        if not rows and quota.dexscreener_pairs.remaining() <= 0:
            result["budget_denied"] += 1
        all_rows.extend(rows)

    result["fetched"] = len(all_rows)
    if all_rows:
        result["stored"] = await persist_snapshots(all_rows)
        history_map = await _load_price_history(all_rows)
        fresh = []
        for row in all_rows:
            if _cooldown_ok(row["symbol"]):
                fresh.extend(detect_spikes(
                    [row],
                    pct_1h=settings.DEX_SPIKE_PCT_1H,
                    min_liquidity_usd=settings.DEX_SPIKE_MIN_LIQUIDITY_USD,
                    history_map=history_map,
                    z_min=getattr(settings, "DEX_SPIKE_ZSCORE_MIN", 3.0),
                ))
        for spike in fresh:
            _mark_cooldown(spike["symbol"])
        result["spikes"] = len(fresh)
        result["rows"] = all_rows
        if fresh:
            await _notify_spike(fresh)
    return result


async def _load_price_history(rows: Sequence[dict]) -> Dict[str, List[float]]:
    """Recent 1h price changes per symbol from stored snapshots (z-score input)."""
    symbols = list({r.get("symbol") for r in rows if r.get("symbol")})
    if not symbols:
        return {}
    try:
        from sqlalchemy import select
        from app.database import AsyncSessionLocal
        from app.models import DexSnapshot

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(DexSnapshot.symbol, DexSnapshot.price_change_1h)
                .where(DexSnapshot.symbol.in_(symbols))
                .where(DexSnapshot.price_change_1h.is_not(None))
                .order_by(DexSnapshot.ts.desc())
                .limit(500)
            )
            history: Dict[str, List[float]] = {}
            for symbol, change in result.all():
                history.setdefault(symbol, []).append(float(change))
            # Trim to the most recent 48 observations per symbol.
            return {s: hist[:48] for s, hist in history.items()}
    except Exception as exc:
        logger.debug("price history load failed: %s", exc)
        return {}


async def tick() -> dict:
    """One collection pass. Never raises — counters only."""
    global _logged_budget
    settings = get_settings()
    if not settings.DEX_WATCH_ENABLED:
        return {"enabled": False, "fetched": 0, "stored": 0}
    try:
        result = await collect_once()
    except Exception as exc:
        logger.warning("dexwatch tick failed: %s", exc)
        return {"enabled": True, "fetched": 0, "stored": 0, "error": str(exc)}
    if result["budget_denied"] and not _logged_budget:
        logger.info("dexwatch: provider budget exhausted — skipping this tick")
        _logged_budget = True
    elif not result["budget_denied"]:
        _logged_budget = False
    if result["stored"] or result["spikes"]:
        logger.info("dexwatch fetched=%s stored=%s spikes=%s",
                    result["fetched"], result["stored"], result["spikes"])
    return result
