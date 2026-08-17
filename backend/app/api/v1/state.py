"""State endpoint — merged from Express server.ts into FastAPI with proper DB persistence."""

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.telegram_auth import get_current_user
from app.database import get_db
from app.models import Profile, UserCredential, Position, TradeLog, RiskSettings as RS, PaperBalance, OrderSide, OrderStatus, TradeMode, UserWhitelist

logger = logging.getLogger(__name__)
router = APIRouter(tags=["state"])


# ── Pydantic schemas ──────────────────────────────────────────────

class PositionItem(BaseModel):
    id: str
    pair: str
    size: float
    pnl: float
    buyPrice: float
    currentPrice: float
    logo: str


class CeFiConnection(BaseModel):
    connected: bool
    encryptedKeys: Optional[str] = None


class UserStateOut(BaseModel):
    walletConnected: bool
    walletAddress: Optional[str] = None
    network: Optional[str] = None
    balance: float
    portfolioValue: float
    dailyProfitLoss: float
    pnlPercentage: float
    agentActive: bool
    agentTarget: str = "Trend Scrape + Kronos"
    riskLimit: float
    tradeMode: str
    currency: str = "USD"
    nairaRate: Optional[float] = None
    positions: List[PositionItem] = []
    connectedCeFi: dict = {"bybit": {"connected": False, "encryptedKeys": None}, "okx": {"connected": False, "encryptedKeys": None}, "binance": {"connected": False, "encryptedKeys": None}}
    onboardingCompleted: bool = False
    onboardingPages: List[str] = []


class RiskSettingsOut(BaseModel):
    maxAllocation: float
    maxConcurrentTrades: int
    riskLevel: str
    stopLoss: float
    takeProfit: float
    trailingStop: float
    baseTradeUsd: float
    whitelist: List[str]


# ── Helpers ───────────────────────────────────────────────────────

# Upstream USD/NGN rate cache (avoids hammering the exchange API on every request).
# There is deliberately NO hardcoded default rate — the live value is fetched
# upstream, cached here, and refreshed when the cache expires.
_NAIRA_CACHE: dict = {"rate": None, "fetched_at": 0.0}
_NAIRA_CACHE_TTL = 3600  # 1 hour


def _parse_onboarding_pages(raw) -> List[str]:
    """Parse the Profile.onboarding_pages JSON list safely."""
    import json
    try:
        data = json.loads(raw) if raw else []
        return [p for p in data if isinstance(p, str)]
    except Exception:
        return []


async def _get_or_create_profile(telegram_id: int, db: AsyncSession) -> Profile:
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = Profile(
            telegram_id=telegram_id,
            risk_level="medium",
            max_allocation_pct=10.0,
            max_concurrent_trades=3,
            trading_mode="paper",
            bot_enabled=False,
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


async def _fetch_naira_rate() -> Optional[float]:
    """Fetch live USD/NGN rate, cached for 1 hour.

    Returns the previously cached rate if we already have one (even when the
    upstream call fails), so the UI never snaps back to a hardcoded value.
    Returns None only when no rate has ever been fetched and upstream is down.
    """
    now = time.time()
    # Serve from cache when fresh.
    if _NAIRA_CACHE["rate"] is not None and now - _NAIRA_CACHE["fetched_at"] < _NAIRA_CACHE_TTL:
        return _NAIRA_CACHE["rate"]

    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            res = await client.get("https://open.er-api.com/v6/latest/USD")
            if res.status_code == 200:
                data = res.json()
                rate = data.get("rates", {}).get("NGN")
                if rate and isinstance(rate, (int, float)):
                    rate = round(rate, 2)
                    _NAIRA_CACHE.update({"rate": rate, "fetched_at": now})
                    return rate
    except Exception:
        pass

    # Upstream unreachable — reuse the last known rate if we have one.
    if _NAIRA_CACHE["rate"] is not None:
        return _NAIRA_CACHE["rate"]
    return None


async def _map_positions(profile_id, db: AsyncSession) -> List[PositionItem]:
    result = await db.execute(
        select(Position)
        .where(Position.profile_id == profile_id)
        .where(Position.is_closed == False)
    )
    positions = result.scalars().all()
    items = []
    for p in positions:
        symbol = str(p.symbol)
        items.append(PositionItem(
            id=str(p.id),
            pair=symbol,
            size=float(p.size),
            pnl=float(p.unrealized_pnl),
            buyPrice=float(p.entry_price),
            currentPrice=float(p.current_price),
            logo=symbol.split("/")[0][:1] or symbol[:1],
        ))
    return items


async def _map_cefi_keys(profile_id, db: AsyncSession) -> dict:
    result = await db.execute(
        select(UserCredential)
        .where(UserCredential.profile_id == profile_id)
        .where(UserCredential.is_active == True)
    )
    creds = result.scalars().all()
    ceFi = {}
    for c in creds:
        exchange = c.exchange.lower()
        ceFi[exchange] = {
            "connected": True,
            "encryptedKeys": f"aes-256:{c.encrypted_api_key[:16]}...",
        }
    # Ensure bybit, okx, and binance keys exist
    for exch in ("bybit", "okx", "binance"):
        if exch not in ceFi:
            ceFi[exch] = {"connected": False, "encryptedKeys": None}
    return {
        "bybit": ceFi.get("bybit", {"connected": False, "encryptedKeys": None}),
        "okx": ceFi.get("okx", {"connected": False, "encryptedKeys": None}),
        "binance": ceFi.get("binance", {"connected": False, "encryptedKeys": None}),
    }


async def _map_whitelist(profile_id, db: AsyncSession) -> List[str]:
    result = await db.execute(
        select(UserWhitelist.symbol)
        .where(UserWhitelist.profile_id == profile_id)
        .where(UserWhitelist.active == True)
    )
    return [row[0] for row in result.all()]


async def _map_risk_settings(profile, db: AsyncSession) -> RiskSettingsOut:
    rr = await db.execute(select(RS).where(RS.profile_id == profile.id))
    rs = rr.scalar_one_or_none()
    whitelist = await _map_whitelist(profile.id, db)
    if rs:
        return RiskSettingsOut(
            maxAllocation=float(rs.max_allocation_pct),
            maxConcurrentTrades=rs.max_concurrent_trades,
            riskLevel=profile.risk_level.value if hasattr(profile.risk_level, 'value') else str(profile.risk_level),
            stopLoss=float(rs.stop_loss_pct),
            takeProfit=float(rs.take_profit_pct),
            trailingStop=float(rs.trailing_stop_pct),
            baseTradeUsd=float(rs.base_trade_usd),
            whitelist=whitelist,
        )
    return RiskSettingsOut(
        maxAllocation=float(profile.max_allocation_pct),
        maxConcurrentTrades=profile.max_concurrent_trades,
        riskLevel=profile.risk_level.value if hasattr(profile.risk_level, 'value') else str(profile.risk_level),
        stopLoss=3.0,
        takeProfit=6.0,
        trailingStop=1.0,
        baseTradeUsd=10.0,
        whitelist=whitelist,
    )


# ── Endpoints ─────────────────────────────────────────────────────

@router.get("/api/state")
async def get_state(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get complete dashboard state from PostgreSQL."""
    telegram_id = user["id"]
    profile = await _get_or_create_profile(telegram_id, db)
    
    positions = await _map_positions(profile.id, db)
    ceFi = await _map_cefi_keys(profile.id, db)
    risk = await _map_risk_settings(profile, db)
    
    # Paper balance
    bal_result = await db.execute(
        select(PaperBalance).where(PaperBalance.profile_id == profile.id)
    )
    paper_bal = bal_result.scalar_one_or_none()
    balance = float(paper_bal.balance) if paper_bal else 124.50
    
    # Calculate unrealized PnL from open positions
    pos_result = await db.execute(
        select(Position).where(Position.profile_id == profile.id).where(Position.is_closed == False)
    )
    open_positions = pos_result.scalars().all()
    total_unrealized = sum(float(p.unrealized_pnl or 0) for p in open_positions)
    portfolioValue = balance + total_unrealized
    
    # Today's PnL from trade logs
    from datetime import timedelta
    today_start = datetime.now(timezone.utc) - timedelta(days=1)
    trades_result = await db.execute(
        select(func.sum(TradeLog.total_value_usd)).where(
            TradeLog.profile_id == profile.id,
            TradeLog.executed_at >= today_start
        )
    )
    dailyProfitLoss = float(trades_result.scalar() or 0)
    pnlPercentage = (dailyProfitLoss / balance * 100) if balance > 0 else 0
    
    naira_rate = await _fetch_naira_rate()
    
    return {
        "status": "success",
        "data": UserStateOut(
            walletConnected=bool(profile.wallet_connected if hasattr(profile, 'wallet_connected') else False),
            walletAddress=profile.wallet_address if hasattr(profile, 'wallet_address') else None,
            network=profile.wallet_network if hasattr(profile, 'wallet_network') else "TON",
            balance=balance,
            portfolioValue=portfolioValue,
            dailyProfitLoss=dailyProfitLoss,
            pnlPercentage=round(pnlPercentage, 2),
            agentActive=profile.bot_enabled,
            riskLimit=float(profile.max_allocation_pct),
            tradeMode=profile.trading_mode.value if hasattr(profile.trading_mode, 'value') else str(profile.trading_mode),
            currency="USD",
            nairaRate=naira_rate,
            positions=positions,
            connectedCeFi=ceFi,
            onboardingCompleted=bool(getattr(profile, "onboarding_completed", False)),
            onboardingPages=_parse_onboarding_pages(getattr(profile, "onboarding_pages", "[]")),
        ),
        "riskSettings": risk.model_dump(),
    }


@router.post("/api/toggle-agent")
async def toggle_agent(
    request: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    active = request.get("active", False)
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.bot_enabled = active
    await db.commit()
    return {"status": "success", "agentActive": active}


@router.post("/api/toggle-mode")
async def toggle_mode(
    request: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    mode = request.get("mode", "").upper()
    if mode not in ("PAPER", "LIVE"):
        raise HTTPException(status_code=400, detail="Invalid mode")
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    profile.trading_mode = TradeMode.PAPER if mode == "PAPER" else TradeMode.LIVE
    await db.commit()
    return {"status": "success", "tradeMode": mode}


@router.post("/api/update-paper-balance")
async def update_paper_balance(
    request: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    balance_val = request.get("balance", 0)
    num = float(balance_val)
    if num < 0:
        raise HTTPException(status_code=400, detail="Balance must be >= 0")
    
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    bal_result = await db.execute(
        select(PaperBalance).where(PaperBalance.profile_id == profile.id)
    )
    paper_bal = bal_result.scalar_one_or_none()
    if paper_bal:
        paper_bal.balance = num
    else:
        paper_bal = PaperBalance(profile_id=profile.id, asset="TON", balance=num)
        db.add(paper_bal)
    await db.commit()
    return {"status": "success", "balance": num}


@router.post("/api/toggle-currency")
async def toggle_currency(
    request: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    currency = request.get("currency", "USD")
    if currency not in ("USD", "NGN"):
        raise HTTPException(status_code=400, detail="Invalid currency")
    naira_rate = await _fetch_naira_rate() if currency == "NGN" else 1.0
    return {"status": "success", "currency": currency, "nairaRate": naira_rate}


@router.get("/api/exchange-rate")
async def get_exchange_rate(
    user: dict = Depends(get_current_user),
):
    """Return the current live USD/NGN rate (cached for 1h upstream)."""
    naira_rate = await _fetch_naira_rate()
    return {"status": "success", "currency": "USD", "nairaRate": naira_rate}


@router.post("/api/reset-settings")
async def reset_settings(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    profile.max_allocation_pct = 15.0
    profile.max_concurrent_trades = 3
    profile.risk_level = "aggressive"
    
    # Upsert risk settings
    rr = await db.execute(select(RS).where(RS.profile_id == profile.id))
    rs = rr.scalar_one_or_none()
    if rs:
        rs.stop_loss_pct = 3.0
        rs.take_profit_pct = 6.5
        rs.trailing_stop_pct = 1.0
        rs.max_allocation_pct = 15.0
        rs.max_concurrent_trades = 3
        rs.base_trade_usd = 10.0
    else:
        rs = RS(
            profile_id=profile.id,
            stop_loss_pct=3.0,
            take_profit_pct=6.5,
            trailing_stop_pct=1.0,
            max_allocation_pct=15.0,
            max_concurrent_trades=3,
        )
        db.add(rs)
    await db.commit()
    
    return {"status": "success", "data": {
        "maxAllocation": 15,
        "maxConcurrentTrades": 3,
        "riskLevel": "AGGRESSIVE",
        "stopLoss": 3.0,
        "takeProfit": 6.5,
        "trailingStop": 1.0,
        "whitelist": ["SOL", "TON", "ETH", "BTC", "PEPE", "BONK", "WIF"],
    }}


@router.post("/api/risk-profile")
async def update_risk_profile(
    request: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Core risk fields live on the profile
    if "maxAllocation" in request:
        profile.max_allocation_pct = Decimal(str(request["maxAllocation"]))
    if "maxConcurrentTrades" in request:
        profile.max_concurrent_trades = int(request["maxConcurrentTrades"])
    if "riskLevel" in request:
        profile.risk_level = request["riskLevel"]

    # SL/TP/trailing/base trade live on risk_settings
    risk_fields = {}
    if "stopLoss" in request:
        risk_fields["stop_loss_pct"] = Decimal(str(request["stopLoss"]))
    if "takeProfit" in request:
        risk_fields["take_profit_pct"] = Decimal(str(request["takeProfit"]))
    if "trailingStop" in request:
        risk_fields["trailing_stop_pct"] = Decimal(str(request["trailingStop"]))
    if "baseTradeUsd" in request:
        risk_fields["base_trade_usd"] = Decimal(str(request["baseTradeUsd"]))

    if risk_fields:
        rs_res = await db.execute(select(RS).where(RS.profile_id == profile.id))
        rs = rs_res.scalar_one_or_none()
        if rs:
            for k, v in risk_fields.items():
                setattr(rs, k, v)
        else:
            defaults = dict(
                stop_loss_pct=Decimal("3.0"),
                take_profit_pct=Decimal("6.0"),
                trailing_stop_pct=Decimal("1.0"),
                max_allocation_pct=profile.max_allocation_pct,
                max_concurrent_trades=profile.max_concurrent_trades,
            )
            defaults.update(risk_fields)
            rs = RS(profile_id=profile.id, **defaults)
            db.add(rs)

    await db.commit()
    return {"status": "success", "data": {
        "maxAllocation": float(profile.max_allocation_pct),
        "maxConcurrentTrades": profile.max_concurrent_trades,
        "riskLevel": profile.risk_level.value if hasattr(profile.risk_level, 'value') else str(profile.risk_level),
        "stopLoss": float(risk_fields.get("stop_loss_pct", 3.0)),
        "takeProfit": float(risk_fields.get("take_profit_pct", 6.5)),
        "trailingStop": float(risk_fields.get("trailing_stop_pct", 1.0)),
    }}


@router.post("/api/panic")
async def panic_close(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Close all positions
    pos_result = await db.execute(select(Position).where(Position.profile_id == profile.id))
    positions = pos_result.scalars().all()
    for p in positions:
        p.is_closed = True
    profile.bot_enabled = False
    await db.commit()
    
    return {"status": "success", "message": "All positions liquidated, trading system halted."}


@router.post("/api/wallet-connect")
async def wallet_connect(
    request: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    network = request.get("network", "TON")
    address = request.get("address", "")
    if not address:
        raise HTTPException(status_code=400, detail="Address is required")
    
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    profile.wallet_connected = True
    profile.wallet_address = address
    profile.wallet_network = network
    await db.commit()
    
    return {"status": "success", "data": {
        "walletConnected": True,
        "walletAddress": address,
        "network": network,
    }}


@router.post("/api/exchange-manual")
async def exchange_manual(
    request: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    exchange = request.get("exchange", "")
    api_key = request.get("apiKey", "")
    api_secret = request.get("apiSecret", "")
    passphrase = request.get("passphrase")
    
    if not api_key or not api_secret:
        raise HTTPException(status_code=400, detail="API Key and Secret required")
    
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    from app.core.encryption import encrypt_credentials
    encrypted = encrypt_credentials(api_key, api_secret, passphrase)
    
    cred_result = await db.execute(
        select(UserCredential).where(
            UserCredential.profile_id == profile.id,
            UserCredential.exchange == exchange
        )
    )
    cred = cred_result.scalar_one_or_none()
    
    if cred:
        cred.encrypted_api_key = encrypted["api_key"]
        cred.encrypted_api_secret = encrypted["api_secret"]
        if "passphrase" in encrypted:
            cred.encrypted_passphrase = encrypted["passphrase"]
        cred.is_active = True
    else:
        cred = UserCredential(
            profile_id=profile.id,
            exchange=exchange,
            encrypted_api_key=encrypted["api_key"],
            encrypted_api_secret=encrypted["api_secret"],
            encrypted_passphrase=encrypted.get("passphrase"),
            is_active=True,
        )
        db.add(cred)
    
    await db.commit()
    return {"status": "success", "connectedCeFi": {exchange: {"connected": True, "encryptedKeys": f"encrypted:{encrypted['api_key'][:16]}..."}}}


@router.post("/api/exchange-disconnect")
async def exchange_disconnect(
    request: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    exchange = request.get("exchange", "")
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    cred_result = await db.execute(
        select(UserCredential).where(
            UserCredential.profile_id == profile.id,
            UserCredential.exchange == exchange
        )
    )
    cred = cred_result.scalar_one_or_none()
    if cred:
        cred.is_active = False
        await db.commit()
    
    return {"status": "success", "connectedCeFi": {exchange: {"connected": False, "encryptedKeys": None}}}


@router.get("/api/risk-profile")
async def get_risk_profile(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    rr = await db.execute(select(RS).where(RS.profile_id == profile.id))
    rs = rr.scalar_one_or_none()
    whitelist = await _map_whitelist(profile.id, db)

    return {"status": "success", "data": {
        "maxAllocation": float(profile.max_allocation_pct),
        "maxConcurrentTrades": profile.max_concurrent_trades,
        "riskLevel": profile.risk_level.value if hasattr(profile.risk_level, 'value') else str(profile.risk_level),
        "stopLoss": float(rs.stop_loss_pct) if rs else 3.0,
        "takeProfit": float(rs.take_profit_pct) if rs else 6.0,
        "trailingStop": float(rs.trailing_stop_pct) if rs else 1.0,
        "whitelist": whitelist,
    }}


@router.get("/api/exchange")
async def get_exchange(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    ceFi = await _map_cefi_keys(profile.id, db)
    return {"status": "success", "connectedCeFi": ceFi}
