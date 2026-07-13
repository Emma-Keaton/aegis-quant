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
        
        import ccxt
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
        mode: str  # "paper" or "live"
    ) -> ExecutionResult:
        """Execute trade based on profile settings and mode"""
        
        # Default to Bybit
        exchange = "bybit"
        
        if mode == "live":
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
        """Simulate paper trade execution"""
        # In paper mode, just return success
        # Real price would come from CCXT fetch_ticker
        import ccxt
        ex = ccxt.bybit({'enableRateLimit': True})
        try:
            ticker = await ex.fetch_ticker(symbol)
            real_price = ticker['last']
        except:
            real_price = price
        await ex.close()
        
        return ExecutionResult(
            executed=True,
            side=side,
            symbol=symbol,
            size=size,
            price=real_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            route="paper",
            status="filled",
            order_id=f"paper_{symbol}_{side}_{int(price * 1000)}"
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
            return {"USDT": 10000.0}  # Mock paper balance
        
        client = await self._get_cex_client(str(profile.id), exchange)
        balance = await client.fetch_balance()
        return {k: float(v['free']) for k, v in balance.items() if float(v['free']) > 0}
    
    async def close_all(self):
        """Close all CCXT connections"""
        for client in self._cex_clients.values():
            await client.close()
        self._cex_clients.clear()