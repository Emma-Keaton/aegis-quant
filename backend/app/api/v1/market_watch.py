"""Watch + model-ops endpoints: token-watch, scoreboard, promotion, breaker."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.config import get_settings
from app.core.telegram_auth import get_current_user
from app.database import AsyncSessionLocal, get_db
from app.middleware.admin_auth import AdminGuard
from app.models import DexSnapshot, Profile, WhaleFlow
from app.services import circuit_breaker, promotion, scoreboard
from app.services.quota import status as quota_status

router = APIRouter(prefix="/api", tags=["market-watch"])


class EvaluateResponse(BaseModel):
    status: str
    reasons: list
    changed: bool
    decision_id: str


@router.get("/token-watch")
async def token_watch(limit: int = 30, user: dict = Depends(get_current_user)):
    """Latest DEX snapshots + whale flows + spike candidates (the watcher's view)."""
    settings = get_settings()
    since = datetime.now(timezone.utc) - timedelta(hours=2)
    async with AsyncSessionLocal() as db:
        snapshots = (await db.execute(
            select(DexSnapshot)
            .order_by(DexSnapshot.ts.desc())
            .limit(max(1, min(limit, 200)))
        )).scalars().all()
        flows = (await db.execute(
            select(WhaleFlow)
            .where(WhaleFlow.ts >= since)
            .order_by(WhaleFlow.ts.desc())
            .limit(max(1, min(limit, 100)))
        )).scalars().all()

    rows = []
    spikes = []
    for s in snapshots:
        row = {
            "symbol": s.symbol,
            "chain": s.chain,
            "price_usd": s.price_usd,
            "liquidity_usd": s.liquidity_usd,
            "volume_usd": s.volume_usd,
            "price_change_5m": s.price_change_5m,
            "price_change_1h": s.price_change_1h,
            "price_change_24h": s.price_change_24h,
            "ts": s.ts.isoformat() if s.ts else None,
        }
        rows.append(row)
        change = s.price_change_1h
        if (change is not None and (s.liquidity_usd or 0) >= settings.DEX_SPIKE_MIN_LIQUIDITY_USD
                and abs(float(change)) >= settings.DEX_SPIKE_PCT_1H):
            spikes.append({**row, "spike_pct": float(change)})

    return {
        "enabled": settings.DEX_WATCH_ENABLED,
        "interval_seconds": settings.DEX_WATCH_INTERVAL_SECONDS,
        "spike_threshold_pct": settings.DEX_SPIKE_PCT_1H,
        "snapshots": rows,
        "spikes": spikes,
        "whale_flows": [
            {
                "symbol": f.symbol,
                "wallet": f.wallet,
                "side": f.side,
                "amount_usd": f.amount_usd,
                "ts": f.ts.isoformat() if f.ts else None,
            }
            for f in flows
        ],
        "whale_enabled": bool(settings.HELIUS_API_KEY),
        "quota": quota_status(),
        "breaker": circuit_breaker.status(),
    }


@router.get("/model/scoreboard")
async def model_scoreboard(user: dict = Depends(get_current_user)):
    return await scoreboard.scoreboard()


@router.get("/model/promotion")
async def promotion_status(user: dict = Depends(get_current_user), db=Depends(get_db)):
    telegram_id = user["id"]
    profile = (await db.execute(
        select(Profile).where(Profile.telegram_id == telegram_id)
    )).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    decision = await promotion.latest_decision(profile.id)
    readiness = await promotion.live_readiness(profile)
    return {
        "trading_mode": profile.trading_mode.value,
        "decision": {
            "status": decision.status if decision else "untested",
            "reason": decision.reason if decision else None,
            "evidence": decision.evidence if decision else None,
            "decided_at": decision.decided_at.isoformat() if decision and decision.decided_at else None,
        },
        "readiness": readiness,
        "require_promotion_for_live": get_settings().REQUIRE_PROMOTION_FOR_LIVE,
        "live_trading_enabled": get_settings().LIVE_TRADING_ENABLED,
    }


@router.post("/model/promotion/evaluate", response_model=EvaluateResponse)
async def promotion_evaluate(user: dict = Depends(get_current_user), db=Depends(get_db)):
    telegram_id = user["id"]
    profile = (await db.execute(
        select(Profile).where(Profile.telegram_id == telegram_id)
    )).scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    outcome = await promotion.run_evaluation(profile)
    return EvaluateResponse(
        status=outcome["status"],
        reasons=outcome["reasons"],
        changed=outcome["changed"],
        decision_id=outcome["decision_id"],
    )


@router.get("/circuit/status")
async def circuit_status(user: dict = Depends(get_current_user)):
    return circuit_breaker.status()


class ResumeResponse(BaseModel):
    state: str
    reason: Optional[str] = None


@router.post("/circuit/resume", response_model=ResumeResponse,
             dependencies=[Depends(AdminGuard.verify_admin)])
async def circuit_resume():
    """Manual resume — the only way out of `open` (breakers never self-clear)."""
    state = await circuit_breaker.resume()
    return ResumeResponse(state=state.get("state", "closed"), reason=state.get("reason"))
