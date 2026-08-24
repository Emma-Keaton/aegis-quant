"""Coin search — lets users find and add coins to their watchlist.

Primary: CoinGecko `/coins/list` (cached symbol→id map). Fallback: CoinMarketCap
(when the API key is set and CoinGecko is rate-limited). Returns matches with
symbol, name + optional price.
"""
import logging
import time
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/coins", tags=["coins"])

COINGECKO_API = "https://api.coingecko.com/api/v3"
CMC_API = "https://pro-api.coinmarketcap.com/v1"

# In-memory symbol map + price cache to avoid hammering rate-limited endpoints.
_coin_map: dict = {}
_coin_map_ts: float = 0
_SYMBOL_MAP_TTL = 3600  # 1h


async def _load_coingecko_map() -> dict:
    """Lazily load the CoinGecko symbol→id map (cached)."""
    global _coin_map, _coin_map_ts
    now = time.time()
    if _coin_map and (now - _coin_map_ts) < _SYMBOL_MAP_TTL:
        return _coin_map
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(f"{COINGECKO_API}/coins/list")
            resp.raise_for_status()
            mapping: dict = {}
            for entry in resp.json():
                sym = (entry.get("symbol") or "").upper()
                cid = entry.get("id")
                if sym and cid:
                    mapping.setdefault(sym, []).append({"name": entry.get("name", ""), "id": cid})
            _coin_map = mapping
            _coin_map_ts = now
            return mapping
    except Exception as e:
        logger.warning("CoinGecko coin-list failed: %s", e)
        return _coin_map if _coin_map else {}


def _cmc_search(query: str, limit: int) -> List[Any]:
    """CoinMarketCap search fallback (requires API key). Returns [{symbol,name,price}]."""
    key = get_settings().CMC_API_KEY
    if not key:
        return []
    try:
        # CoinGecko rate-limited → use CMC listing (top 300) filtered by the query.
        url = f"{CMC_API}/cryptocurrency/listing/latest"
        with httpx.Client(timeout=12) as client:
            resp = client.get(url, params={"limit": 300}, headers={"X-CMC_PRO_API_KEY": key, "Accept": "application/json"})
            resp.raise_for_status()
            data = resp.json().get("data", [])
            q = query.upper()
            out = []
            for c in data:
                sym = (c.get("symbol") or "").upper()
                if q in sym or q in (c.get("name") or "").upper():
                    out.append({"symbol": sym, "name": c.get("name") or sym, "price": c.get("quote", {}).get("USD", {}).get("price")})
                    if len(out) >= limit:
                        break
            return out
    except Exception as e:
        logger.warning("CMC search fallback failed: %s", e)
        return []


@router.get("/search")
async def search_coins(q: str = Query(..., min_length=1, max_length=40), limit: int = Query(10, ge=1, le=50)):
    """Search for coins by symbol or name."""
    q = q.strip().upper()
    if not q:
        raise HTTPException(status_code=400, detail="q is required")

    # CoinGecko first (symbol/name prefix or substring match).
    mapping = await _load_coingecko_map()
    results = []
    def score(match: bool, exact: bool) -> int:
        return 2 if exact else (1 if match else 0)
    for sym, entries in mapping.items():
        sym_match = q in sym
        name_matches = [e for e in entries if q in (e.get("name") or "").upper()]
        if sym_match or name_matches:
            # Prefer exact symbol matches.
            rank = 2 if sym == q else 1
            results.append((rank, {"symbol": sym, "name": (name_matches[0]["name"] if name_matches else sym), "id": (name_matches[0]["id"] if name_matches else entries[0]["id"])}))
            if len(results) >= limit:
                break
    results.sort(key=lambda t: t[0], reverse=True)
    coins = [r[1] for r in results]
    if coins:
        return {"query": q, "coins": coins, "source": "coingecko", "count": len(coins)}

    # Fallback: CoinMarketCap
    cmc = _cmc_search(q, limit)
    if cmc:
        return {"query": q, "coins": cmc, "source": "coinmarketcap", "count": len(cmc)}

    return {"query": q, "coins": [], "source": "coingecko", "count": 0}