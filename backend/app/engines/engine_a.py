"""
Engine A: Technical Core (Event-Driven Blue-Chip Autopilot)

Architecture:
- CCXT WebSocket connections for real-time market data
- Trigger-based analysis (not fixed polling)
- Kronos AI for trajectory forecasting
- Risk validation before execution
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from decimal import Decimal

import ccxt.async_support as ccxt
import ccxt.pro as ccxtpro
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Profile, UserWhitelist, Position, TradeLog, Signal, ExecutionAudit
from app.core.encryption import decrypt_credentials
from app.engines.kronos_client import KronosClient
from app.engines.risk_validator import RiskValidator
from app.engines.execution_router import ExecutionRouter
from app.core.exceptions import EngineError, ExchangeError, InsufficientFundsError, RiskLimitExceededError

logger = logging.getLogger(__name__)


@dataclass
class TriggerEvent:
    """Market trigger event from WebSocket"""
    symbol: str
    exchange: str
    trigger_type: str  # price_change, volume_spike, spread_tight, funding_flip
    current_price: float
    change_pct: float
    volume_ratio: float
    spread_bps: float
    timestamp: datetime


class CCXTWebSocketManager:
    """Manages CCXT Pro WebSocket connections for multiple exchanges"""
    
    def __init__(self):
        self.exchanges: Dict[str, ccxtpro.Exchange] = {}
        self.subscriptions: Dict[str, Set[str]] = {}  # exchange -> set of symbols
        self.trigger_callbacks: List[callable] = []
        self.running = False
    
    async def add_exchange(self, exchange_id: str, api_key: str = "", secret: str = "", password: str = ""):
        """Initialize exchange with credentials"""
        exchange_class = getattr(ccxtpro, exchange_id)
        config = {
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'},
        }
        if api_key:
            config['apiKey'] = api_key
            config['secret'] = secret
            if password:
                config['password'] = password
        
        exchange = exchange_class(config)
        await exchange.load_markets()
        self.exchanges[exchange_id] = exchange
        self.subscriptions[exchange_id] = set()
        logger.info(f"Initialized {exchange_id} WebSocket")
        return exchange
    
    async def subscribe_ticker(self, exchange_id: str, symbols: List[str]):
        """Subscribe to ticker updates for symbols"""
        exchange = self.exchanges.get(exchange_id)
        if not exchange:
            raise ValueError(f"Exchange {exchange_id} not initialized")
        
        for symbol in symbols:
            if symbol not in self.subscriptions[exchange_id]:
                self.subscriptions[exchange_id].add(symbol)
        
        # Start watchers
        for symbol in symbols:
            asyncio.create_task(self._watch_ticker(exchange_id, symbol))
    
    async def _watch_ticker(self, exchange_id: str, symbol: str):
        """Watch ticker and emit triggers"""
        exchange = self.exchanges[exchange_id]
        last_price = 0
        last_volume = 0
        volume_ma = 0  # Simple moving average for volume
        volume_samples = []
        
        while self.running and symbol in self.subscriptions.get(exchange_id, set()):
            try:
                ticker = await exchange.watch_ticker(symbol)
                
                current_price = ticker['last']
                current_volume = ticker['baseVolume'] or 0
                spread = (ticker['ask'] - ticker['bid']) / ticker['last'] * 10000 if ticker['last'] else 0
                
                # Calculate volume ratio (vs 20-sample MA)
                volume_samples.append(current_volume)
                if len(volume_samples) > 20:
                    volume_samples.pop(0)
                volume_ma = sum(volume_samples) / len(volume_samples) if volume_samples else current_volume
                volume_ratio = current_volume / volume_ma if volume_ma > 0 else 1
                
                # Check triggers
                triggers = []
                settings = get_settings()
                
                # Price change trigger
                if last_price > 0:
                    change_pct = abs(current_price - last_price) / last_price
                    if change_pct >= settings.ENGINE_A_PRICE_CHANGE_THRESHOLD:
                        triggers.append(("price_change", change_pct))
                
                # Volume spike trigger
                if volume_ratio >= settings.ENGINE_A_VOLUME_SPIKE_THRESHOLD:
                    triggers.append(("volume_spike", volume_ratio))
                
                # Spread tight trigger
                if spread <= settings.ENGINE_A_SPREAD_BPS_THRESHOLD:
                    triggers.append(("spread_tight", spread))
                
                # Emit triggers
                for trigger_type, value in triggers:
                    event = TriggerEvent(
                        symbol=symbol,
                        exchange=exchange_id,
                        trigger_type=trigger_type,
                        current_price=current_price,
                        change_pct=value if trigger_type == "price_change" else 0,
                        volume_ratio=value if trigger_type == "volume_spike" else 0,
                        spread_bps=value if trigger_type == "spread_tight" else spread,
                        timestamp=datetime.utcnow()
                    )
                    for callback in self.trigger_callbacks:
                        try:
                            await callback(event)
                        except Exception as e:
                            logger.error(f"Trigger callback error: {e}")
                
                last_price = current_price
                last_volume = current_volume
                
            except Exception as e:
                logger.error(f"Watch ticker error for {exchange_id}:{symbol}: {e}")
                await asyncio.sleep(5)
    
    def register_trigger_callback(self, callback: callable):
        self.trigger_callbacks.append(callback)
    
    async def start(self):
        self.running = True
        logger.info("WebSocket manager started")
    
    async def stop(self):
        self.running = False
        for exchange in self.exchanges.values():
            await exchange.close()
        logger.info("WebSocket manager stopped")


class EngineA:
    """Engine A: Technical Core - Event-driven blue-chip autopilot"""
    
    def __init__(self):
        self.settings = get_settings()
        self.ws_manager = CCXTWebSocketManager()
        self.kronos = KronosClient()
        self.risk_validator = RiskValidator()
        self.execution_router = ExecutionRouter()
        self.active_symbols: Dict[str, Dict] = {}  # user_id -> {symbol: config}
        self.user_profiles: Dict[int, Profile] = {}
        
        # Register trigger handler
        self.ws_manager.register_trigger_callback(self._on_trigger)
    
    async def initialize(self):
        """Initialize exchange connections and load user configs"""
        # Load active users with bot enabled
        await self._load_user_configs()
        
        # Initialize exchange connections
        for user_id, profile in self.user_profiles.items():
            if not profile.bot_enabled or not profile.engine_a_enabled:
                continue
            
            # Get Bybit credentials
            cred_result = await self._get_credentials(profile.id, "bybit")
            if cred_result:
                await self.ws_manager.add_exchange(
                    "bybit",
                    cred_result["api_key"],
                    cred_result["api_secret"]
                )
            
            # Subscribe to whitelist symbols
            symbols = [w.symbol for w in profile.whitelist if w.active]
            if symbols:
                await self.ws_manager.subscribe_ticker("bybit", symbols)
        
        await self.ws_manager.start()
        logger.info(f"Engine A initialized with {len(self.user_profiles)} users")
    
    async def _load_user_configs(self):
        """Load all active user profiles with whitelists"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Profile)
                .where(Profile.bot_enabled == True)
                .where(Profile.engine_a_enabled == True)
            )
            profiles = result.scalars().all()
            
            for profile in profiles:
                # Load whitelist
                wl_result = await db.execute(
                    select(UserWhitelist)
                    .where(UserWhitelist.profile_id == profile.id)
                    .where(UserWhitelist.active == True)
                )
                profile.whitelist = wl_result.scalars().all()
                self.user_profiles[profile.telegram_id] = profile
    
    async def _get_credentials(self, profile_id: uuid.UUID, exchange: str) -> Optional[dict]:
        async with AsyncSessionLocal() as db:
            from app.models import UserCredential
            result = await db.execute(
                select(UserCredential)
                .where(UserCredential.profile_id == profile_id)
                .where(UserCredential.exchange == exchange)
                .where(UserCredential.is_active == True)
            )
            cred = result.scalar_one_or_none()
            if cred:
                return decrypt_credentials({
                    "api_key": cred.encrypted_api_key,
                    "api_secret": cred.encrypted_api_secret,
                    "passphrase": cred.encrypted_passphrase
                })
        return None
    
    async def _on_trigger(self, event: TriggerEvent):
        """Handle market trigger event"""
        logger.info(f"Engine A trigger: {event.trigger_type} for {event.symbol} on {event.exchange}")
        
        # Find users watching this symbol
        for user_id, profile in self.user_profiles.items():
            if not profile.bot_enabled:
                continue
            
            # Check if symbol in whitelist
            symbol_match = any(w.symbol == event.symbol and w.active for w in profile.whitelist)
            if not symbol_match:
                continue
            
            # Process signal
            await self._process_signal(profile, event)
    
    async def _process_signal(self, profile: Profile, event: TriggerEvent):
        """Fetch candles, call Kronos, validate risk, execute"""
        try:
            # 1. Fetch latest candles (128 for Kronos)
            candles = await self._fetch_candles(event.exchange, event.symbol, "1m", 128)
            if len(candles) < 64:
                logger.warning(f"Insufficient candles for {event.symbol}: {len(candles)}")
                return
            
            # 2. Call Kronos for forecast
            forecast = await self.kronos.forecast(candles)
            if not forecast:
                return
            
            confidence = forecast.get("confidence", 0)
            if confidence < profile.engine_a_min_confidence:
                logger.info(f"Confidence {confidence} below threshold {profile.engine_a_min_confidence}")
                return
            
            # 3. Risk validation
            risk_check = await self.risk_validator.validate(
                profile=profile,
                symbol=event.symbol,
                signal_confidence=confidence,
                current_price=event.current_price
            )
            
            if not risk_check.approved:
                logger.info(f"Risk check failed: {risk_check.reason}")
                return
            
            # 4. Execute trade
            execution = await self.execution_router.execute(
                profile=profile,
                symbol=event.symbol,
                side=risk_check.side,
                size=risk_check.size,
                price=event.current_price,
                stop_loss=risk_check.stop_loss,
                take_profit=risk_check.take_profit,
                mode=profile.trading_mode
            )
            
            # 5. Log execution audit
            await self._log_execution_audit(profile, event, forecast, execution)
            
        except Exception as e:
            logger.error(f"Signal processing error: {e}")
    
    async def _fetch_candles(self, exchange_id: str, symbol: str, timeframe: str, limit: int) -> List:
        """Fetch OHLCV candles"""
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({'enableRateLimit': True})
        try:
            ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return [
                {
                    "timestamp": c[0],
                    "open": c[1],
                    "high": c[2],
                    "low": c[3],
                    "close": c[4],
                    "volume": c[5]
                }
                for c in ohlcv
            ]
        finally:
            await exchange.close()
    
    async def _log_execution_audit(self, profile: Profile, event: TriggerEvent, forecast: dict, execution: dict):
        """Log immutable execution audit trail"""
        async with AsyncSessionLocal() as db:
            audit = ExecutionAudit(
                profile_id=profile.id,
                mode=profile.trading_mode,
                symbol=event.symbol,
                side=execution.get("side", "buy"),
                size=Decimal(str(execution.get("size", 0))),
                price=Decimal(str(execution.get("price", 0))),
                sl=Decimal(str(execution.get("stop_loss", 0))) if execution.get("stop_loss") else None,
                tp=Decimal(str(execution.get("take_profit", 0))) if execution.get("take_profit") else None,
                kronos_confidence=forecast.get("confidence"),
                trigger_type=event.trigger_type,
                status=execution.get("status", "filled"),
                tx_hash=execution.get("tx_hash"),
                error=execution.get("error")
            )
            db.add(audit)
            await db.commit()
    
    async def scheduled_scan(self):
        """Fallback: Full scan every 5 minutes"""
        logger.info("Engine A: Running scheduled full scan")
        for user_id, profile in self.user_profiles.items():
            if not profile.bot_enabled or not profile.engine_a_enabled:
                continue
            
            for whitelist_item in profile.whitelist:
                if not whitelist_item.active:
                    continue
                
                # Create synthetic trigger for scheduled scan
                event = TriggerEvent(
                    symbol=whitelist_item.symbol,
                    exchange=whitelist_item.exchange,
                    trigger_type="scheduled",
                    current_price=0,  # Will be fetched
                    change_pct=0,
                    volume_ratio=0,
                    spread_bps=0,
                    timestamp=datetime.utcnow()
                )
                await self._process_signal(profile, event)
    
    async def shutdown(self):
        await self.ws_manager.stop()