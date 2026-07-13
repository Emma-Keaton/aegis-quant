"""Engine B: Social Scout (Momentum & Hype Discovery)"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Profile, Signal, UserWhitelist
from app.engines.kronos_client import KronosClient
from app.engines.gemini_client import gemini_client
from app.engines.risk_validator import RiskValidator
from app.engines.execution_router import ExecutionRouter
from app.core.exceptions import EngineError

logger = logging.getLogger(__name__)


@dataclass
class SocialSignal:
    """Signal from social media scraping"""
    ticker: str
    source: str  # twitter, reddit, telegram, rss
    sentiment: float  # -1 to 1
    volume: int  # mentions per hour
    url: str
    timestamp: datetime
    raw_text: str


class EngineB:
    """Engine B: Social Scout - Momentum & Hype Discovery"""
    
    def __init__(self):
        self.settings = get_settings()
        self.kronos = KronosClient()
        self.risk_validator = RiskValidator()
        self.execution_router = ExecutionRouter()
        self.active_users: Dict[int, Profile] = {}
    
    async def initialize(self):
        """Load active users with bot enabled"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Profile)
                .where(Profile.bot_enabled == True)
                .where(Profile.engine_b_enabled == True)
            )
            profiles = result.scalars().all()
            for p in profiles:
                self.active_users[p.telegram_id] = p
        logger.info(f"Engine B initialized with {len(self.active_users)} users")
    
    async def run_social_scan(self):
        """Main social scanning loop - runs every 30 minutes"""
        logger.info("Engine B: Starting social scan")
        
        for user_id, profile in self.active_users.items():
            if not profile.bot_enabled or not profile.engine_b_enabled:
                continue
            
            try:
                await self._scan_user_universe(profile)
            except Exception as e:
                logger.error(f"Engine B error for user {user_id}: {e}")
        
        logger.info("Engine B: Social scan complete")
    
    async def _scan_user_universe(self, profile: Profile):
        """Scan social sources for a user's universe"""
        # Get watchlist from whitelist
        whitelist_result = await db.execute(
            select(UserWhitelist).where(UserWhitelist.profile_id == profile.id)
        )
        watchlist = [w.symbol for w in whitelist_result.scalars().all()]
        
        # Also add default crypto symbols
        default_symbols = ["BTC", "ETH", "SOL", "TON", "WIF", "BONK", "PEPE", "DOGE"]
        universe = list(set(watchlist + default_symbols))
        
        # Scrape all sources (TODO: implement actual scrapers)
        social_signals = await self._scrape_all_sources(universe)
        
        # Filter and rank signals
        ranked = self._rank_signals(social_signals)
        
        # Process top signals through Kronos
        for signal in ranked[:5]:  # Top 5 per scan
            await self._process_social_signal(profile, signal)
    
    async def _scrape_all_sources(self, symbols: List[str]) -> List[SocialSignal]:
        """Scrape Twitter, Reddit, Telegram, RSS"""
        signals = []
        
        # Twitter (twscrape) - TODO
        # twitter_signals = await self._scrape_twitter(symbols)
        # signals.extend(twitter_signals)
        
        # Reddit (URS) - TODO
        # reddit_signals = await self._scrape_reddit(symbols)
        # signals.extend(reddit_signals)
        
        # Telegram (Telethon) - TODO
        # tg_signals = await self._scrape_telegram(symbols)
        # signals.extend(tg_signals)
        
        # RSS (Scrapy) - TODO
        # rss_signals = await self._scrape_rss(symbols)
        # signals.extend(rss_signals)
        
        # For now, return mock signals for testing
        import random
        for sym in symbols[:10]:
            signals.append(SocialSignal(
                ticker=sym,
                source="mock",
                sentiment=random.uniform(-0.5, 0.8),
                volume=random.randint(10, 500),
                url="",
                timestamp=datetime.utcnow(),
                raw_text=f"Mock signal for {sym}"
            ))
        
        return signals
    
    def _rank_signals(self, signals: List[SocialSignal]) -> List[SocialSignal]:
        """Rank signals by sentiment * volume"""
        def score(s: SocialSignal) -> float:
            return s.sentiment * (1 + s.volume / 100)
        
        return sorted(signals, key=score, reverse=True)
    
    async def _process_social_signal(self, profile: Profile, signal: SocialSignal):
        """Process a social signal through Kronos and execute if valid"""
        try:
            # Get candles for symbol
            candles = await self._fetch_candles(signal.ticker)
            if not candles or len(candles) < 64:
                return
            
            # Get Kronos forecast
            forecast = await self.kronos.forecast(candles)
            if not forecast:
                return
            
            confidence = forecast.get("confidence", 0)
            if confidence < profile.engine_b_min_confidence:
                return
            
            # Risk validation
            risk_check = await self.risk_validator.validate(
                profile=profile,
                symbol=signal.ticker,
                signal_confidence=confidence,
                current_price=candles[-1]["close"]
            )
            
            if not risk_check.approved:
                return
            
            # Execute
            execution = await self.execution_router.execute(
                profile=profile,
                symbol=signal.ticker,
                side=risk_check.side,
                size=risk_check.size,
                price=candles[-1]["close"],
                stop_loss=risk_check.stop_loss,
                take_profit=risk_check.take_profit,
                mode=profile.trading_mode
            )
            
            # Store signal
            await self._store_signal(profile, signal, forecast, execution)
            
        except Exception as e:
            logger.error(f"Signal processing error: {e}")
    
    async def _fetch_candles(self, symbol: str) -> List[Dict]:
        """Fetch OHLCV candles (placeholder)"""
        # TODO: Implement via CCXT
        return []
    
    async def _store_signal(self, profile: Profile, signal: SocialSignal, forecast: Dict, execution: Dict):
        """Store signal in database"""
        async with AsyncSessionLocal() as db:
            sig = Signal(
                profile_id=profile.id,
                engine="B",
                ticker=f"${signal.ticker}",
                source=signal.source,
                metric=f"{signal.volume}/hr",
                analysis=f"Social sentiment: {signal.sentiment:.2f}",
                confidence=forecast.get("confidence", 0),
                action_label=f"{'EXECUTED' if execution.get('executed') else 'MONITOR'} ${signal.ticker}",
                sentiment_score=signal.sentiment,
                mentions_per_hour=signal.volume,
                kronos_trajectories=forecast.get("trajectories"),
                kronos_mean_path=forecast.get("mean_path"),
                kronos_confidence_90=forecast.get("confidence_90")
            )
            db.add(sig)
            await db.commit()
    
    async def shutdown(self):
        pass


# Import at bottom to avoid circular
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import UserWhitelist