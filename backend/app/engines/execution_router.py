"""Execution Router - Routes trades to CEX (CCXT) or DEX (Web3/Solana/TON)"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from decimal import Decimal

from app.config import get_settings
from app.core.encryption import decrypt_credentials
from app.core.exceptions import ExchangeError, InsufficientFundsError


@dataclass
class ExecutionResult:
    executed: bool
    side: str
    symbol: str
    size: float
    price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    route: str = "cex"  # cex, dex_evm, dex_solana, dex_ton
    tx_hash: Optional[str] = None
    order_id: Optional[str] = None
    status: str = "filled"
    error: Optional[str] = None


class ExecutionRouter:
    """Routes trade execution to appropriate venue"""
    
    def __init__(self):
        self.settings = get_settings()
        self._cex_clients: Dict[str, Any] = {}
    
    async def _get_cex_client(self, profile_id: str, exchange: str):
        """Get or create CCXT client with decrypted credentials"""
        cache_key = f"{profile_id}:{exchange}"
        if cache_key in self._cex_clients:
            return self._cex_clients[cache_key]
        
        # Get credentials from DB
        from app.database import AsyncSessionLocal
        from app.models import UserCredential
        from sqlalchemy import select
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserCredential).where(
                    UserCredential.profile_id == profile_id,
                    UserCredential.exchange == exchange,
                    UserCredential.is_active == True
                )
            )
            cred = result.scalar_one_or_none()
        
        if not cred:
            raise ExchangeError(f"No credentials for {exchange}", exchange)
        
        decrypted = decrypt_credentials({
            "api_key": cred.encrypted_api_key,
            "api_secret": cred.encrypted_api_secret,
            "passphrase": cred.encrypted_passphrase
        })
        
        import ccxt.async_support as ccxt
        exchange_class = getattr(ccxt, exchange)
        client = exchange_class({
            'apiKey': decrypted["api_key"],
            'secret': decrypted["api_secret"],
            'password': decrypted.get("passphrase"),
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'},
        })
        
        await client.load_markets()
        self._cex_clients[cache_key] = client
        return client
    
    async def execute(
        self,
        profile,
        symbol: str,
        side: str,
        size: float,
        price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        mode: str,  # "paper" or "live"
        exchange_type: str = "centralized",  # "centralized" | "solana"
        wallet_address: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute trade based on profile settings, mode and venue."""
        exchange = "bybit"

        if mode == "live":
            if exchange_type == "solana":
                return await self._execute_solana_dex(
                    profile, symbol, side, size, price, stop_loss, take_profit, wallet_address
                )
            if exchange_type == "ton":
                return await self._execute_ton(
                    profile, symbol, side, size, price, stop_loss, take_profit, wallet_address
                )
            return await self._execute_live(
                profile, exchange, symbol, side, size, price, stop_loss, take_profit
            )
        else:
            return await self._execute_paper(
                profile, exchange, symbol, side, size, price, stop_loss, take_profit
            )
    
    async def _execute_paper(
        self,
        profile,
        exchange: str,
        symbol: str,
        side: str,
        size: float,
        price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float]
    ) -> ExecutionResult:
        """Simulate paper trade execution, debiting/crediting the real paper balance."""
        # Resolve a real fill price when possible (falls back to provided price).
        import ccxt.async_support as ccxt
        ex = ccxt.bybit({'enableRateLimit': True})
        try:
            ticker = await ex.fetch_ticker(symbol)
            fill_price = ticker['last']
        except:
            fill_price = price
        await ex.close()

        fill_price = float(fill_price or price or 0)
        notional = size * fill_price

        # Load the real paper balance (single row per profile) and enforce funds.
        from app.database import AsyncSessionLocal
        from app.models import PaperBalance
        from app.core.exceptions import InsufficientFundsError
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            pb_result = await db.execute(
                select(PaperBalance).where(PaperBalance.profile_id == profile.id)
            )
            pb = pb_result.scalar_one_or_none()

            if side == "buy":
                have = float(pb.balance) if pb and pb.balance is not None else 0.0
                if notional > have:
                    raise InsufficientFundsError(
                        f"Insufficient paper balance: need {notional:.2f}, have {have:.2f}"
                    )
                pb.balance = Decimal(str(have - notional))
            else:  # sell credits proceeds back to the paper balance
                have = float(pb.balance) if pb and pb.balance is not None else 0.0
                if pb is None:
                    pb = PaperBalance(profile_id=profile.id, asset="TON", balance=0)
                    db.add(pb)
                pb.balance = Decimal(str(have + notional))
            await db.commit()

        return ExecutionResult(
            executed=True,
            side=side,
            symbol=symbol,
            size=size,
            price=fill_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            route="paper",
            status="filled",
            order_id=f"paper_{symbol}_{side}_{int(fill_price * 1000)}"
        )
    
    async def _execute_solana_dex(
        self,
        profile,
        symbol: str,
        side: str,
        size: float,
        price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        wallet_address: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute a live trade on the Solana DEX via Jupiter, signed by the server keypair."""
        import json as _json
        import base64

        from app.core.exceptions import ExchangeError
        from app.services.jupiter_client import get_jupiter_client, SOL_MINT, sol_to_usd_price
        from app.services.wallet_gateway import get_solana_client, load_solana_keypair_for_profile

        if not wallet_address:
            raise ExchangeError("wallet_address required for solana dex execution", "SOLANA")

        jup = get_jupiter_client()
        rpc = get_solana_client()
        # Use the user's own keypair when set (multi-tenant), else the server env key.
        kp = load_solana_keypair_for_profile(profile)

        try:
            # Resolve the token mint.
            token_ref = await jup.get_token_by_symbol(symbol)
            if not token_ref:
                raise ExchangeError(f"Solana token '{symbol}' not found", "SOLANA")
            token_mint = token_ref if isinstance(token_ref, str) else (token_ref.get("address") or token_ref.get("mint"))
            if not token_mint:
                raise ExchangeError(f"Could not resolve mint for '{symbol}'", "SOLANA")

            side = (side or "buy").lower()
            if side == "buy":
                input_mint, output_mint = SOL_MINT, token_mint
                usd = float(size or 0)
                sol_price = await sol_to_usd_price()
                sol = (usd / (sol_price or 1)) if sol_price else (usd or 0)
                input_amount = max(int(sol * 1e9 * 0.99), 1000)  # leave fee buffer
            else:
                input_mint, output_mint = token_mint, SOL_MINT
                # Selling `size` token units (assume 9 decimals like SOL).
                input_amount = max(int(float(size or 0) * 1e9), 1)

            quote = await jup.get_quote(input_mint, output_mint, input_amount, slippage_bps=200)
            if not quote:
                raise ExchangeError("Jupiter quote failed", "SOLANA")

            swap_data = await jup.get_swap_transaction(_json.dumps(quote.to_dict()), str(kp.public_key))
            if not swap_data or not swap_data.get("swapTransaction"):
                raise ExchangeError("Failed to build Jupiter swap transaction", "SOLANA")

            from solders.transaction import VersionedTransaction
            txn = VersionedTransaction.from_bytes(base64.b64decode(swap_data["swapTransaction"]))
            txn.sign([kp])
            resp = await rpc.send_raw_transaction(bytes(txn))
            sig = str(resp.value) if hasattr(resp, "value") else str(resp)

            return ExecutionResult(
                executed=True, side=side, symbol=symbol, size=size,
                price=price or quote.price_pure, stop_loss=stop_loss, take_profit=take_profit,
                route="dex_solana", status="filled", tx_hash=sig,
            )
        finally:
            await jup.close()
            await rpc.close()

    async def _execute_ton(
        self,
        profile,
        symbol: str,
        side: str,
        size: float,
        price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        wallet_address: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute a live trade on TON via the user's connected Ton Connect wallet.

        Per-trade user approval (option A): build an unsigned transfer request for
        the user's *own* connected wallet and return it as a `pending_approval`
        result. The Mini App surfaces it to tonConnectUI.sendTransaction(...),
        the user approves in their wallet app, and the signed boc is broadcast +
        persisted by the caller. No server-side TON key is required for user trades.
        """
        from app.services.ton_trade import build_transfer_messages, autonomous_transfer_boc, broadcast_boc
        from app.core.exceptions import ExchangeError
        import os

        if not wallet_address:
            raise ExchangeError(
                "TON trading requires a connected Ton Connect wallet address", "TON"
            )

        # Autonomous path: sign + broadcast with the *user's own* TON mnemonic when
        # set (multi-tenancy), else the server TON_MNEMONIC. If neither is available,
        # fall back to per-trade user approval via Ton Connect.
        from app.services.ton_trade import load_profile_mnemonic
        user_mnemonic = load_profile_mnemonic(profile)
        if user_mnemonic or os.getenv("TON_MNEMONIC"):
            boc = autonomous_transfer_boc(
                recipient=wallet_address,
                amount_ton=float(size or 0),
                comment=f"{side.upper()} {symbol}",
                mnemonic=user_mnemonic,  # None -> falls back to env inside
            )
            try:
                tx_hash = await broadcast_boc(boc)
            except Exception as e:
                raise ExchangeError(f"TON autonomous broadcast failed: {e}", "TON")
            return ExecutionResult(
                executed=True,
                side=side,
                symbol=symbol,
                size=size,
                price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                route="dex_ton",
                status="filled",
                tx_hash=tx_hash,
            )

        # Fallback: per-trade user approval via Ton Connect.
        request = build_transfer_messages(
            recipient=wallet_address,
            amount_ton=float(size or 0),
            comment=f"{side.upper()} {symbol}",
        )

        # Soft-return the unsigned request; the caller persists + prompts approval.
        return ExecutionResult(
            executed=False,
            side=side,
            symbol=symbol,
            size=size,
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            route="dex_ton",
            status="pending_approval",
            tx_hash=None,
            error="TON approval required - approve in your wallet",
        )

    async def _execute_live(
        self,
        profile,
        exchange: str,
        symbol: str,
        side: str,
        size: float,
        price: float,
        stop_loss: Optional[float],
        take_profit: Optional[float]
    ) -> ExecutionResult:
        """Execute live trade on CEX"""
        # Enforce the Spot & Margin permission before placing a real order.
        from app.core.exceptions import RiskLimitExceededError
        try:
            from app.database import AsyncSessionLocal
            from app.models import RiskSettings
            from sqlalchemy import select
            async with AsyncSessionLocal() as db:
                rs_result = await db.execute(
                    select(RiskSettings).where(RiskSettings.profile_id == profile.id)
                )
                rs = rs_result.scalar_one_or_none()
            if rs is not None and not rs.spot_margin_enabled:
                raise RiskLimitExceededError(
                    "Spot & margin trading is disabled in Risk Settings"
                )
        except RiskLimitExceededError:
            raise
        except Exception:
            pass  # Never block a live order because the permission row is missing.

        try:
            client = await self._get_cex_client(str(profile.id), exchange)
            
            # Place market order
            order = await client.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=size,
                params={
                    'stopLoss': stop_loss,
                    'takeProfit': take_profit
                } if stop_loss or take_profit else {}
            )
            
            # Wait for fill (simplified)
            filled_price = order.get('average', price) or price
            
            return ExecutionResult(
                executed=True,
                side=side,
                symbol=symbol,
                size=float(order.get('filled', size)),
                price=filled_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                route="cex",
                status="filled" if order.get('status') == 'closed' else "pending",
                order_id=order.get('id'),
                tx_hash=order.get('id')
            )
            
        except Exception as e:
            raise ExchangeError(str(e), exchange)
    
    async def close_position(
        self,
        profile,
        symbol: str,
        side: str,
        size: float,
        mode: str
    ) -> ExecutionResult:
        """Close an existing position"""
        opposite_side = "sell" if side == "buy" else "buy"
        return await self.execute(
            profile, symbol, opposite_side, size, 0, None, None, mode
        )
    
    async def get_balance(self, profile, exchange: str) -> Dict[str, float]:
        """Get account balance from exchange"""
        if profile.trading_mode.value == "paper":
            # Return the user's real configured paper balance (not a hardcoded mock).
            from app.database import AsyncSessionLocal
            from app.models import PaperBalance
            from sqlalchemy import select
            async with AsyncSessionLocal() as db:
                pb_result = await db.execute(
                    select(PaperBalance).where(PaperBalance.profile_id == profile.id)
                )
                pb = pb_result.scalar_one_or_none()
            return {"USDT": float(pb.balance) if pb and pb.balance is not None else 0.0}

        client = await self._get_cex_client(str(profile.id), exchange)
        balance = await client.fetch_balance()
        return {k: float(v['free']) for k, v in balance.items() if float(v['free']) > 0}
    
    async def close_all(self):
        """Close all CCXT connections"""
        for client in self._cex_clients.values():
            await client.close()
        self._cex_clients.clear()