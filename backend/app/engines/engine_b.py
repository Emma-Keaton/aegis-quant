"""Engine B v2: Social Scout - Multi-source crypto sentiment aggregator.

Polls from:
- Twitter/X via Twikit (unofficial API)
- RSS feeds via feedparser (Cointelegraph, CoinDesk, etc.)
- Telegram channels via Telethon
- Reddit via pushshift/old Reddit API
- On-chain data via CoinGecko

Supports user-customizable sources via SourceRegistry.
"""

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass

import httpx
from feedparser import parse as parse_rss

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Profile, Signal, UserWhitelist
from app.services.source_registry import get_all_sources, SourceType

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class SocialSignal:
    ticker: str
    source: str
    sentiment: float
    volume: int
    url: str
    timestamp: datetime
    raw_text: str
    source_type: str  # rss, twitter, telegram, reddit, onchain


class TwitterScraper:
    """Scrape Twitter/X using Twikit."""

    def __init__(self):
        self.client = None
        self.connected = False

    async def connect(self):
        try:
            from twikit import Client
            self.client = Client()
            self.connected = True
            logger.info("Twitter scraper initialized")
        except Exception as e:
            logger.warning(f"Twitter init failed: {e}")
            self.connected = False

    async def fetch_signals(self, handles: List[str], limit: int = 15) -> List[SocialSignal]:
        signals = []
        if not self.connected or not self.client:
            return signals

        for handle in handles[:8]:  # Rate limit protection
            try:
                tweets = await self.client.search_tweet(handle, tweet_type="Latest")
                for tweet in tweets[:limit]:
                    text = tweet.text.lower()
                    sentiment = self._analyze_sentiment(text)
                    
                    signals.append(SocialSignal(
                        ticker=self._extract_ticker(text),
                        source="twitter",
                        sentiment=sentiment,
                        volume=1,
                        url=f"https://twitter.com/{handle}/status/{tweet.id}",
                        timestamp=datetime.fromtimestamp(tweet.created_at_timestamp, tz=timezone.utc),
                        raw_text=tweet.text[:200],
                        source_type="twitter"
                    ))
            except Exception as e:
                logger.warning(f"Twitter fetch failed for @{handle}: {e}")
        return signals

    def _analyze_sentiment(self, text: str) -> float:
        positive = ['bullish', 'moon', 'long', 'buy', 'pump', 'gain', 'rocket', 'lambo', 
                    'ath', 'uptrend', 'rally', 'surge', 'explosive', 'strong', 'breakout']
        negative = ['bearish', 'dump', 'sell', 'crash', 'loss', 'danger', 'fud', 'scam',
                    'down', 'below', 'resistance', 'warning', 'risky', 'weak', 'breakdown']
        pos = sum(1 for w in positive if w in text)
        neg = sum(1 for w in negative if w in text)
        total = pos + neg
        if total == 0:
            return 0.0
        return (pos - neg) / total

    def _extract_ticker(self, text: str) -> str:
        """Extract crypto ticker from tweet text."""
        tickers = ['BTC', 'ETH', 'SOL', 'TON', 'WIF', 'BONK', 'PEPE', 'DOGE', 'ADA', 'XRP']
        for t in tickers:
            if t in text.upper() or f'${t}' in text.upper():
                return t
        return 'CRYPTO'

    async def close(self):
        self.client = None
        self.connected = False


class RSSScraper:
    """Scrape RSS feeds for crypto news."""

    async def fetch_signals(self, sources: List) -> List[SocialSignal]:
        signals = []
        rss_sources = [s for s in sources if s.source_type == SourceType.RSS]
        
        async with httpx.AsyncClient(timeout=15) as client:
            for source in rss_sources[:10]:  # Limit concurrent requests
                try:
                    resp = await client.get(source.url_or_handle, timeout=10)
                    if resp.status_code == 200:
                        feed = parse_rss(resp.text)
                        for entry in feed.entries[:15]:
                            title = entry.get('title', '')
                            link = entry.get('link', '')
                            for ticker in ['BTC', 'ETH', 'SOL', 'TON', 'WIF', 'BONK', 'PEPE', 'DOGE']:
                                if ticker in title.upper():
                                    sentiment = self._analyze_sentiment(title)
                                    signals.append(SocialSignal(
                                        ticker=ticker,
                                        source=source.name,
                                        sentiment=sentiment,
                                        volume=1,
                                        url=link,
                                        timestamp=datetime.now(timezone.utc),
                                        raw_text=title[:200],
                                        source_type="rss"
                                    ))
                except Exception as e:
                    logger.warning(f"RSS failed for {source.name}: {e}")
        return signals

    def _analyze_sentiment(self, text: str) -> float:
        positive = ['surge', 'rally', 'gain', 'record', 'high', 'bull', 'moon', 'boost', 'new high']
        negative = ['crash', 'dump', 'fall', 'low', 'bear', 'danger', 'scam', 'hack']
        pos = sum(1 for w in positive if w in text.lower())
        neg = sum(1 for w in negative if w in text.lower())
        total = pos + neg
        if total == 0:
            return 0.0
        return (pos - neg) / total


class TelegramScraper:
    """Scrape Telegram channels using Telethon."""

    def __init__(self):
        self.client = None

    async def connect(self):
        if settings.TELEGRAM_API_ID and settings.TELEGRAM_API_HASH:
            from telethon import TelegramClient
            self.client = TelegramClient('engine_b', settings.TELEGRAM_API_ID, settings.TELEGRAM_API_HASH)
            logger.info("Telegram scraper initialized")
        else:
            logger.warning("Telegram credentials not set")

    async def fetch_signals(self, sources: List) -> List[SocialSignal]:
        signals = []
        if not self.client:
            return signals

        telegram_sources = [s for s in sources if s.source_type == SourceType.TELEGRAM]
        
        try:
            await self.client.start()
            for source in telegram_sources[:5]:  # Limit channels
                try:
                    entity = await self.client.get_entity(source.url_or_handle)
                    messages = await self.client.get_messages(entity, limit=10)
                    for msg in messages:
                        if msg.text:
                            text = msg.text.lower()
                            for ticker in ['BTC', 'ETH', 'SOL', 'TON', 'WIF', 'BONK', 'PEPE', 'DOGE']:
                                if ticker.lower() in text:
                                    sentiment = self._analyze_sentiment(text)
                                    signals.append(SocialSignal(
                                        ticker=ticker,
                                        source=source.name,
                                        sentiment=sentiment,
                                        volume=1,
                                        url=f"https://t.me/{source.url_or_handle}/{msg.id}",
                                        timestamp=msg.date or datetime.now(timezone.utc),
                                        raw_text=msg.text[:200],
                                        source_type="telegram"
                                    ))
                except Exception as e:
                    logger.warning(f"Telegram channel {source.name} failed: {e}")
        except Exception as e:
            logger.error(f"Telegram client error: {e}")
        return signals

    def _analyze_sentiment(self, text: str) -> float:
        positive = ['buy', 'bull', 'moon', 'long', 'pump', 'gain', 'profit', 'record', 'high']
        negative = ['sell', 'bear', 'dump', 'short', 'crash', 'loss', 'danger', 'rug', 'low']
        pos = sum(1 for w in positive if w in text)
        neg = sum(1 for w in negative if w in text)
        total = pos + neg
        if total == 0:
            return 0.0
        return (pos - neg) / total

    async def close(self):
        if self.client:
            await self.client.disconnect()


class RedditScraper:
    """Scrape Reddit for crypto mentions."""

    SUBREDDITS = ['cryptocurrency', 'solana', 'Bitcoin', 'ethereum', 'CryptoCurrency']

    async def fetch_signals(self, sources: List) -> List[SocialSignal]:
        signals = []
        reddit_sources = [s for s in sources if s.source_type == SourceType.REDDIT]
        
        async with httpx.AsyncClient(timeout=15) as client:
            for sub in self.SUBREDDITS:
                try:
                    url = f"https://www.reddit.com/r/{sub}/hot.json?limit=25"
                    headers = {
                        'User-Agent': 'AegisQuant/1.0',
                        'Accept': 'application/json'
                    }
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        for post in data.get('data', {}).get('children', []):
                            p = post['data']
                            title = p['title']
                            score = p['score']
                            for ticker in ['BTC', 'ETH', 'SOL', 'TON', 'WIF', 'BONK', 'PEPE', 'DOGE']:
                                if ticker in title.upper():
                                    sentiment = min(1.0, max(-1.0, (score - 50) / 100))
                                    signals.append(SocialSignal(
                                        ticker=ticker,
                                        source=f"reddit:{sub}",
                                        sentiment=sentiment,
                                        volume=score,
                                        url=p['url'],
                                        timestamp=datetime.fromtimestamp(p['created_utc'], tz=timezone.utc),
                                        raw_text=title[:200],
                                        source_type="reddit"
                                    ))
                except Exception as e:
                    logger.warning(f"Reddit r/{sub} failed: {e}")
        return signals


class OnChainScraper:
    """Fetch on-chain data from CoinGecko."""

    async def fetch_signals(self, sources: List) -> List[SocialSignal]:
        signals = []
        coin_map = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'SOL': 'solana',
            'TON': 'toncoin', 'WIF': 'wif-token', 'BONK': 'bonk',
            'PEPE': 'pepe-token', 'DOGE': 'dogecoin'
        }
        
        async with httpx.AsyncClient(timeout=15) as client:
            for ticker, coin_id in coin_map.items():
                try:
                    resp = await client.get(
                        f"https://api.coingecko.com/api/v3/coins/{coin_id}",
                        params={'localization': False, 'tickers': False}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        market_data = data.get('market_data', {})
                        price_change = market_data.get('price_change_percentage_24h', 0) or 0
                        sentiment = max(-1, min(1, price_change / 100))
                        
                        signals.append(SocialSignal(
                            ticker=ticker,
                            source="coingecko:onchain",
                            sentiment=sentiment,
                            volume=int(market_data.get('total_volume_usd', 0) / 1e6),
                            url=f"https://www.coingecko.com/en/coins/{coin_id}",
                            timestamp=datetime.now(timezone.utc),
                            raw_text=f"24h change: {price_change:.2f}%",
                            source_type="onchain"
                        ))
                except Exception as e:
                    logger.warning(f"On-chain data failed for {ticker}: {e}")
        return signals


class EngineB:
    """Engine B: Social Scout - Multi-source crypto sentiment aggregator."""

    def __init__(self):
        self.twitter = TwitterScraper()
        self.rss = RSSScraper()
        self.telegram = TelegramScraper()
        self.reddit = RedditScraper()
        self.onchain = OnChainScraper()
        # Per-source cooldown to protect rate-limited external APIs (Twitter/
        # Telegram/CoinGecko) when scanning at fast cadence.
        self._cooldown: Dict[str, float] = {}
        self._cooldown_seconds = settings.ENGINE_B_SCRAPE_COOLDOWN_SECONDS

    def _cooldown_ready(self, source_type: str) -> bool:
        """True if enough time has passed since the last fetch of this source."""
        now = time.time()
        if now - self._cooldown.get(source_type, 0.0) >= self._cooldown_seconds:
            self._cooldown[source_type] = now
            return True
        return False
        self.active_users: Dict[int, Profile] = {}

    async def initialize(self):
        """Load active users and connect scrapers."""
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
        
        await self.twitter.connect()
        await self.telegram.connect()

    async def run_social_scan(self):
        """Main social scanning loop."""
        logger.info("Engine B: Starting social scan")
        
        # Get all configured sources
        sources = get_all_sources()
        
        for user_id, profile in self.active_users.items():
            if not profile.bot_enabled or not profile.engine_b_enabled:
                continue
            try:
                await self._scan_user_universe(profile, sources)
            except Exception as e:
                logger.error(f"Engine B error for user {user_id}: {e}")

        logger.info("Engine B: Social scan complete")

    async def _scan_user_universe(self, profile: Profile, sources: List):
        """Scan all sources for a user's universe."""
        # Get watchlist
        async with AsyncSessionLocal() as db:
            wl_result = await db.execute(
                select(UserWhitelist).where(UserWhitelist.profile_id == profile.id)
            )
            watchlist = [w.symbol for w in wl_result.scalars().all()]

        symbols = list(set(watchlist + ["BTC", "ETH", "SOL", "TON", "WIF", "BONK", "PEPE", "DOGE"]))

        # Fetch from all sources in parallel
        twitter_sources = [s for s in sources if s.source_type == SourceType.TWITTER]
        twitter_handles = [s.url_or_handle for s in twitter_sources]
        
        twitter_signals = await self.twitter.fetch_signals(twitter_handles) if self._cooldown_ready("twitter") else []
        rss_signals = await self.rss.fetch_signals(sources) if self._cooldown_ready("rss") else []
        telegram_signals = await self.telegram.fetch_signals(sources) if self._cooldown_ready("telegram") else []
        reddit_signals = await self.reddit.fetch_signals(sources) if self._cooldown_ready("reddit") else []
        onchain_signals = await self.onchain.fetch_signals(sources) if self._cooldown_ready("onchain") else []

        # Combine all signals
        all_signals = (twitter_signals + rss_signals + telegram_signals + 
                      reddit_signals + onchain_signals)

        # Rank and process
        ranked = self._rank_signals(all_signals)
        
        for signal in ranked[:10]:  # Top 10
            if abs(signal.sentiment) >= 0.2:  # Minimum sentiment threshold
                await self._process_signal(profile, signal)

    def _rank_signals(self, signals: List[SocialSignal]) -> List[SocialSignal]:
        """Rank by sentiment strength."""
        return sorted(signals, key=lambda s: abs(s.sentiment), reverse=True)

    async def _process_signal(self, profile: Profile, signal: SocialSignal):
        """Store signal if above threshold."""
        async with AsyncSessionLocal() as db:
            sig = Signal(
                engine="B",
                ticker=signal.ticker,
                category=self._detect_category(signal.ticker),
                badge=f"Social {abs(signal.sentiment)*100:.0f}%",
                source=signal.source,
                metric=f"{signal.volume}/hr",
                analysis=signal.raw_text,
                confidence=int(abs(signal.sentiment) * 100),
                action_label=f"MONITOR {signal.ticker} - {signal.source_type}",
                sentiment_score=signal.sentiment,
                mentions_per_hour=signal.volume,
            )
            db.add(sig)
            await db.commit()
        logger.info(f"Engine B: Signal for {signal.ticker} from {signal.source}")

    def _detect_category(self, ticker: str) -> str:
        if ticker in ['BTC', 'ETH']: return 'Major'
        elif ticker in ['SOL', 'TON']: return 'Layer1'
        elif ticker in ['WIF', 'BONK', 'PEPE', 'DOGE']: return 'Meme'
        return 'Altcoin'

    async def shutdown(self):
        await self.twitter.close()
        await self.telegram.close()
