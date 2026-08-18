from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid

from app.database import get_db
from app.core.telegram_auth import get_current_user
from app.models import Profile, UserCredential
from app.core.encryption import encrypt_credentials, decrypt_credentials

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


class WalletConnectRequest(BaseModel):
    network: str = Field(..., pattern="^(ton|evm)$")
    address: str
    public_key: Optional[str] = None


class CeFiKeysRequest(BaseModel):
    exchange: str = Field(..., pattern="^(bybit|okx|binance)$")
    api_key: str
    api_secret: str
    passphrase: Optional[str] = None


class CeFiKeysResponse(BaseModel):
    exchange: str
    connected: bool
    connected_at: Optional[str] = None


@router.post("/connect")
async def connect_wallet(
    request: WalletConnectRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Connect Web3 wallet (TON or EVM)"""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    profile.wallet_address = request.address
    profile.wallet_network = request.network
    profile.wallet_connected = True
    if request.public_key:
        profile.wallet_public_key = request.public_key
    
    await db.commit()
    
    return {
        "wallet_connected": True,
        "address": request.address,
        "network": request.network,
        "message": f"{request.network.upper()} wallet connected"
    }


@router.post("/disconnect")
async def disconnect_wallet(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Disconnect Web3 wallet"""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    profile.wallet_connected = False
    profile.wallet_address = None
    profile.wallet_network = None
    profile.wallet_public_key = None
    
    await db.commit()
    
    return {"wallet_connected": False, "message": "Wallet disconnected"}


@router.post("/cefi-keys", response_model=CeFiKeysResponse)
async def add_cefi_keys(
    request: CeFiKeysRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add/update CeFi API keys (encrypted)"""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Encrypt credentials
    encrypted = encrypt_credentials(
        api_key=request.api_key,
        api_secret=request.api_secret,
        passphrase=request.passphrase
    )
    
    # Check if exists
    cred_result = await db.execute(
        select(UserCredential).where(
            UserCredential.profile_id == profile.id,
            UserCredential.exchange == request.exchange
        )
    )
    cred = cred_result.scalar_one_or_none()
    
    if cred:
        cred.encrypted_api_key = encrypted["api_key"]
        cred.encrypted_api_secret = encrypted["api_secret"]
        if "passphrase" in encrypted:
            cred.encrypted_passphrase = encrypted["passphrase"]
        cred.is_active = True
        cred.updated_at = datetime.utcnow()
    else:
        cred = UserCredential(
            profile_id=profile.id,
            exchange=request.exchange,
            encrypted_api_key=encrypted["api_key"],
            encrypted_api_secret=encrypted["api_secret"],
            encrypted_passphrase=encrypted.get("passphrase"),
            is_active=True
        )
        db.add(cred)
    
    await db.commit()
    await db.refresh(cred)
    
    return CeFiKeysResponse(
        exchange=cred.exchange,
        connected=True,
        connected_at=cred.created_at.isoformat()
    )


@router.get("/cefi-keys", response_model=List[CeFiKeysResponse])
async def get_cefi_keys(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get list of connected CeFi exchanges"""
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    creds_result = await db.execute(
        select(UserCredential).where(
            UserCredential.profile_id == profile.id,
            UserCredential.is_active == True
        )
    )
    creds = creds_result.scalars().all()
    
    return [
        CeFiKeysResponse(
            exchange=c.exchange,
            connected=True,
            connected_at=c.created_at.isoformat()
        )
        for c in creds
    ]


@router.delete("/cefi-keys/{exchange}")
async def remove_cefi_keys(
    exchange: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove CeFi API keys"""
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
    
    if not cred:
        raise HTTPException(status_code=404, detail="Keys not found")
    
    cred.is_active = False
    await db.commit()
    
    return {"message": f"{exchange} keys removed", "exchange": exchange}


@router.post("/cefi-keys/{exchange}/test")
async def test_cefi_connection(
    exchange: str,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Test CeFi exchange connection with stored credentials"""
    import ccxt
    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    cred_result = await db.execute(
        select(UserCredential).where(
            UserCredential.profile_id == profile.id,
            UserCredential.exchange == exchange,
            UserCredential.is_active == True
        )
    )
    cred = cred_result.scalar_one_or_none()
    
    if not cred:
        raise HTTPException(status_code=404, detail=f"{exchange} credentials not found")
    
    # Decrypt and test
    from app.core.encryption import decrypt_credentials
    decrypted = decrypt_credentials({
        "api_key": cred.encrypted_api_key,
        "api_secret": cred.encrypted_api_secret,
        "passphrase": cred.encrypted_passphrase
    })
    
    try:
        exchange_class = getattr(ccxt, exchange)
        ex = exchange_class({
            'apiKey': decrypted["api_key"],
            'secret': decrypted["api_secret"],
            'password': decrypted.get("passphrase"),
            'enableRateLimit': True,
        })
        
        # Test with fetch_balance
        balance = await ex.fetch_balance()
        await ex.close()
        
        return {
            "success": True,
            "message": f"{exchange} connection successful",
            "balances": {k: float(v['free']) for k, v in balance.items() if float(v['free']) > 0}
        }
    except Exception as e:
        return {"success": False, "message": f"Connection failed: {str(e)}"}


@router.get("/balance")
async def wallet_balance(
    network: str,
    address: str,
    symbol: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """Fetch a live on-chain balance for a connected wallet (TON/EVM/Solana).

    For Solana memecoins (BONK/WIF/POPCAT/PEPE) pass ``symbol`` to read the SPL
    token balance via the public RPC instead of the native SOL balance.
    """
    from app.services.chain_balance import chain_balance, solana_meme_balance
    if (network or "").lower() in ("solana", "sol") and symbol:
        res = await solana_meme_balance(address, symbol)
        if res.get("status") == "success":
            return res
        # Fall through to native balance if the meme lookup fails.
    return await chain_balance(network, address)
@router.post("/ton/build")
async def ton_build_transfer(
    payload: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Build an unsigned TON transfer request for the user's connected wallet.

    Returns a TonConnect `sendTransaction`-compatible payload so the Mini App can
    pass it to `tonConnectUI.sendTransaction(...)` for per-trade user approval.
    """
    from app.services.ton_trade import build_transfer_messages

    address = payload.get("address") or (await _get_wallet_address(db, user["id"]))
    if not address:
        raise HTTPException(status_code=400, detail="No TON wallet connected")

    amount_ton = float(payload.get("amount") or 0)
    if amount_ton <= 0:
        raise HTTPException(status_code=400, detail="amount must be > 0")

    recipient = payload.get("recipient") or address
    comment = str(payload.get("comment") or "Aegis Quant")

    request = build_transfer_messages(recipient, amount_ton, comment)
    return {"ok": True, "address": address, "recipient": recipient, "amount": amount_ton, **request}


@router.post("/ton/broadcast")
async def ton_broadcast(
    payload: dict,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Broadcast a user-approved TON boc and persist the resulting trade.

    The Mini App calls this after the user approves the transaction in their
    wallet (TonConnect returns a signed boc). We broadcast it via TonCenter and
    record a Signal + TradeLog + Position so the trade shows on the dashboard.
    """
    from app.services.ton_trade import broadcast_boc
    from app.models import Signal, TradeLog, Position, OrderSide, OrderStatus, ExecutionType, TradeMode
    from decimal import Decimal
    import time as _time

    boc = payload.get("boc")
    if not boc:
        raise HTTPException(status_code=400, detail="boc is required")

    symbol = str(payload.get("symbol") or "TON").upper().lstrip("$")
    side = str(payload.get("side") or "buy").lower()
    if side not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="side must be buy or sell")
    size = float(payload.get("size") or 0)
    price = float(payload.get("price") or 0)

    try:
        tx_hash = await broadcast_boc(boc)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"TON broadcast failed: {e}")

    telegram_id = user["id"]
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    sig = Signal(
        profile_id=profile.id,
        engine="B",
        ticker=f"${symbol}",
        category="onchain",
        badge="TON APPROVED",
        source="ton-connect",
        metric="User-approved transfer",
        analysis=f"Approved {side.upper()} {symbol} in wallet",
        confidence=100,
        action_label=f"AGENT {side.upper()} {symbol}",
        sentiment_score=Decimal("0.0"),
        mentions_per_hour=None,
        liquidity_usd=None,
    )
    db.add(sig)

    trade_log = TradeLog(
        profile_id=profile.id,
        symbol=symbol,
        exchange="ton",
        side=OrderSide(side),
        execution_type=ExecutionType.LIVE,
        size=size,
        price=price,
        total_value_usd=Decimal(str(size * price)),
        status=OrderStatus.FILLED,
        tx_hash=tx_hash,
    )
    db.add(trade_log)

    position = Position(
        profile_id=profile.id,
        symbol=symbol,
        exchange="ton",
        side=OrderSide(side),
        size=size,
        entry_price=price,
        current_price=price,
        mode=TradeMode.LIVE,
    )
    db.add(position)

    await db.commit()

    return {
        "ok": True,
        "tx_hash": tx_hash,
        "symbol": symbol,
        "side": side,
        "size": size,
        "price": price,
        "message": "TON transaction broadcast and recorded",
    }


async def _get_wallet_address(db: AsyncSession, telegram_id) -> Optional[str]:
    result = await db.execute(select(Profile).where(Profile.telegram_id == telegram_id))
    profile = result.scalar_one_or_none()
    if not profile:
        return None
    return profile.wallet_address if getattr(profile, "wallet_connected", False) else None
