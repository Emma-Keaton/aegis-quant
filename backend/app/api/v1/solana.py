"""
Solana DEX Trading API
======================
Endpoints for Jupiter-powered Solana token trading.
"""

import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.database import get_db
from app.core.telegram_auth import get_current_user
from app.models import Profile
from app.services.jupiter_client import (
    get_jupiter_client,
    SOL_MINT,
    USDC_MINT,
    usd_to_sol_amount,
    sol_to_usd_price,
)
from app.services.dexscreener_client import get_dex_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/solana", tags=["solana"])


class SolanaQuoteRequest(BaseModel):
    token_symbol: str
    amount_usd: float = Field(default=10.0, gt=0)
    slippage_bps: int = Field(default=100, ge=1, le=1000)


class SolanaSwapRequest(BaseModel):
    token_symbol: str
    amount_usd: float = Field(default=10.0, gt=0)
    wallet_address: str
    slippage_bps: int = Field(default=100, ge=1, le=1000)


@router.get("/price/{token_symbol}")
async def get_solana_price(token_symbol: str):
    """Get current price of a Solana token in USD."""
    client = get_jupiter_client()
    dex = get_dex_client()
    
    try:
        # Try Jupiter first
        price_data = await client.get_price(token_symbol)
        if price_data:
            return {
                "symbol": token_symbol,
                "price_usd": price_data.price,
                "confidence": price_data.confidence,
                "source": "jupiter",
            }
        
        # Fallback to DexScreener
        pairs = await dex.get_solana_pairs(token_symbol)
        if pairs:
            best = max(pairs, key=lambda p: p.liquidity_usd)
            return {
                "symbol": token_symbol,
                "price_usd": best.price_usd,
                "liquidity": best.liquidity_usd,
                "source": "dexscreener",
            }
        
        raise HTTPException(status_code=404, detail=f"Token {token_symbol} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Price fetch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market/{token_symbol}")
async def get_solana_market_data(token_symbol: str):
    """Get comprehensive market data for a Solana token."""
    dex = get_dex_client()
    
    try:
        pairs = await dex.get_solana_pairs(token_symbol)
        if not pairs:
            raise HTTPException(status_code=404, detail=f"No pairs found for {token_symbol}")
        
        sorted_pairs = sorted(pairs, key=lambda p: p.liquidity_usd, reverse=True)
        best = sorted_pairs[0]
        
        return {
            "symbol": token_symbol,
            "price_usd": best.price_usd,
            "volume_24h": best.volume_24h,
            "liquidity_usd": best.liquidity_usd,
            "fdv": best.fdv,
            "pairs": [p.to_dict() for p in sorted_pairs[:5]],
            "source": "dexscreener",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Market data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quote")
async def get_solana_quote(request: SolanaQuoteRequest):
    """Get a swap quote for Solana token (SOL -> Token)."""
    client = get_jupiter_client()
    
    try:
        token_mint = await client.get_token_by_symbol(request.token_symbol)
        if not token_mint:
            raise HTTPException(status_code=404, detail=f"Token {request.token_symbol} not found")
        
        sol_lamports = await usd_to_sol_amount(request.amount_usd)
        
        quote = await client.get_quote(
            input_mint=SOL_MINT,
            output_mint=token_mint,
            amount=sol_lamports,
            slippage_bps=request.slippage_bps,
        )
        
        if not quote:
            raise HTTPException(status_code=500, detail="Failed to get quote from Jupiter")
        
        sol_price = await sol_to_usd_price()
        
        return {
            "success": True,
            "quote": quote.to_dict(),
            "token_mint": token_mint,
            "input_amount_sol": request.amount_usd / (sol_price or 1),
            "expected_tokens": quote.output_amount / 1e9,
            "price_impact_pct": quote.price_impact_pct,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quote error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/swap")
async def execute_solana_swap(request: SolanaSwapRequest):
    """Get swap transaction data for Solana token."""
    client = get_jupiter_client()
    
    try:
        token_mint = await client.get_token_by_symbol(request.token_symbol)
        if not token_mint:
            raise HTTPException(status_code=404, detail=f"Token {request.token_symbol} not found")
        
        sol_lamports = await usd_to_sol_amount(request.amount_usd)
        quote = await client.get_quote(
            input_mint=SOL_MINT,
            output_mint=token_mint,
            amount=sol_lamports,
            slippage_bps=request.slippage_bps,
        )
        
        if not quote:
            raise HTTPException(status_code=500, detail="Failed to get quote")
        
        swap_data = await client.get_swap_transaction(
            quote_data=json.dumps(quote.to_dict()),
            publicKey=request.wallet_address,
        )
        
        if not swap_data:
            raise HTTPException(status_code=500, detail="Failed to get swap transaction")
        
        return {
            "success": True,
            "swap_transaction": swap_data.get("swapTransaction"),
            "display_transaction": swap_data.get("displayTransaction", {}),
            "quote": quote.to_dict(),
            "message": "Sign this transaction with your wallet",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Swap error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending")
async def get_solana_trending(limit: int = Query(default=10, ge=1, le=20)):
    """Get trending Solana tokens."""
    dex = get_dex_client()
    
    try:
        pairs = await dex.get_top_gainers(limit=limit)
        return {
            "tokens": [p.to_dict() for p in pairs],
            "source": "dexscreener",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Trending error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search/{query}")
async def search_solana_tokens(query: str, limit: int = Query(default=10, ge=1, le=50)):
    """Search for Solana tokens by name."""
    dex = get_dex_client()
    
    try:
        results = await dex.search_tokens(query, limit=limit)
        return {
            "query": query,
            "pairs": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
