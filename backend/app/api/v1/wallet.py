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
    user: dict = Depends(get_current_user),
):
    """Fetch a live on-chain balance for a connected wallet (TON/EVM/Solana)."""
    from app.services.chain_balance import chain_balance
    return await chain_balance(network, address)