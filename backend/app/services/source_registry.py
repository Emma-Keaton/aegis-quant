"""Pre-configured crypto news sources for Engine B social scraping.

Users can add their own via the Intel/Audit page (tenant-isolated).
This module provides the curated baseline + management APIs.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum


class SourceType(str, Enum):
    RSS = "rss"
    TWITTER = "twitter"
    TELEGRAM = "telegram"
    REDDIT = "reddit"
    ONCHAIN = "onchain"


@dataclass
class SourceConfig:
    """Configuration for a single data source."""
    name: str
    source_type: SourceType
    url_or_handle: str  # RSS URL, Twitter handle, Telegram @channel, etc.
    enabled: bool = True
    priority: int = 5  # 1-10, higher = more important
    tags: List[str] = field(default_factory=list)  # e.g., ["major", "meme", "layer1"]
    description: str = ""


# ── Curated Baseline Sources ──────────────────────────────────────────

BASELINE_SOURCES: List[SourceConfig] = [
    # ── RSS Feeds ──────────────────────────────────────────────────
    SourceConfig(
        name="CoinTelegraph",
        source_type=SourceType.RSS,
        url_or_handle="https://cointelegraph.com/rss",
        priority=8,
        tags=["general", "major"],
        description="Leading crypto news outlet"
    ),
    SourceConfig(
        name="Bitcoin Magazine",
        source_type=SourceType.RSS,
        url_or_handle="https://bitcoinmagazine.com/.rss/full/",
        priority=7,
        tags=["btc", "major"],
        description="Bitcoin-focused news and analysis"
    ),
    SourceConfig(
        name="Decrypt",
        source_type=SourceType.RSS,
        url_or_handle="https://decrypt.co/feed",
        priority=6,
        tags=["general", "altcoins"],
        description="Crypto and blockchain news"
    ),
    SourceConfig(
        name="The Block",
        source_type=SourceType.RSS,
        url_or_handle="https://www.theblock.co/feed",
        priority=6,
        tags=["general", "institutional"],
        description="Institutional crypto news"
    ),
    SourceConfig(
        name="CoinDesk",
        source_type=SourceType.RSS,
        url_or_handle="https://www.coindesk.com/arc/outboundfeeds/rss/",
        priority=7,
        tags=["general", "major"],
        description="Established crypto journalism"
    ),
    
    # ── Twitter/X Accounts ─────────────────────────────────────────
    SourceConfig(
        name="VitalikButerin",
        source_type=SourceType.TWITTER,
        url_or_handle="VitalikButerin",
        priority=9,
        tags=["ethereum", "major"],
        description="Ethereum founder's insights"
    ),
    SourceConfig(
        name="cz_binance",
        source_type=SourceType.TWITTER,
        url_or_handle="cz_binance",
        priority=7,
        tags=["exchange", "major"],
        description="Binance CEO updates"
    ),
    SourceConfig(
        name="solana",
        source_type=SourceType.TWITTER,
        url_or_handle="solana",
        priority=8,
        tags=["solana", "layer1"],
        description="Official Solana account"
    ),
    SourceConfig(
        name="TONBlockchain",
        source_type=SourceType.TWITTER,
        url_or_handle="TONBlockchain",
        priority=7,
        tags=["ton", "layer1"],
        description="Official TON blockchain"
    ),
    SourceConfig(
        name="WHAlerts",
        source_type=SourceType.TWITTER,
        url_or_handle="WHAlerts",
        priority=9,
        tags=["whale", "alerts"],
        description="Whale movement alerts"
    ),
    SourceConfig(
        name="lookchain",
        source_type=SourceType.TWITTER,
        url_or_handle="lookchain",
        priority=7,
        tags=["onchain", "data"],
        description="On-chain data and analytics"
    ),
    
    # ── Telegram Channels ──────────────────────────────────────────
    SourceConfig(
        name="CryptoCurrency",
        source_type=SourceType.TELEGRAM,
        url_or_handle="@CryptoCurrency",
        priority=6,
        tags=["general", "discussion"],
        description="General crypto discussion"
    ),
    SourceConfig(
        name="SolanaScamAlert",
        source_type=SourceType.TELEGRAM,
        url_or_handle="@SolanaScamAlert",
        priority=8,
        tags=["solana", "security"],
        description="Solana scam alerts and security"
    ),
    SourceConfig(
        name="WIFcoinnews",
        source_type=SourceType.TELEGRAM,
        url_or_handle="@WIFcoinnews",
        priority=6,
        tags=["meme", "wif"],
        description="WIF coin news and updates"
    ),
    SourceConfig(
        name="pepe_ton",
        source_type=SourceType.TELEGRAM,
        url_or_handle="@pepe_ton",
        priority=5,
        tags=["meme", "pepe"],
        description="Pepe/Ton meme coin community"
    ),
    SourceConfig(
        name="CryptoWhale",
        source_type=SourceType.TELEGRAM,
        url_or_handle="@CryptoWhale",
        priority=9,
        tags=["whale", "alerts"],
        description="Major whale transaction alerts"
    ),
    SourceConfig(
        name="BitcoinWhale",
        source_type=SourceType.TELEGRAM,
        url_or_handle="@BitcoinWhale",
        priority=8,
        tags=["bitcoin", "whale"],
        description="Bitcoin whale movement tracking"
    ),
    
    # ── Reddit Subreddits ──────────────────────────────────────────
    SourceConfig(
        name="cryptocurrency",
        source_type=SourceType.REDDIT,
        url_or_handle="cryptocurrency",
        priority=7,
        tags=["reddit", "discussion"],
        description="Main crypto subreddit"
    ),
    SourceConfig(
        name="solana",
        source_type=SourceType.REDDIT,
        url_or_handle="solana",
        priority=7,
        tags=["reddit", "solana"],
        description="Solana community subreddit"
    ),
    SourceConfig(
        name="Bitcoin",
        source_type=SourceType.REDDIT,
        url_or_handle="Bitcoin",
        priority=6,
        tags=["reddit", "bitcoin"],
        description="Bitcoin community subreddit"
    ),
    SourceConfig(
        name="ethereum",
        source_type=SourceType.REDDIT,
        url_or_handle="ethereum",
        priority=6,
        tags=["reddit", "ethereum"],
        description="Ethereum community subreddit"
    ),
    
    # ── On-Chain Data ──────────────────────────────────────────────
    SourceConfig(
        name="Etherscan Whales",
        source_type=SourceType.ONCHAIN,
        url_or_handle="ETH",
        priority=8,
        tags=["onchain", "ethereum", "whale"],
        description="Ethereum whale movements"
    ),
    SourceConfig(
        name="Solana Whales",
        source_type=SourceType.ONCHAIN,
        url_or_handle="SOL",
        priority=8,
        tags=["onchain", "solana", "whale"],
        description="Solana whale movements"
    ),
]


def get_baseline_sources() -> List[SourceConfig]:
    """Return all baseline sources."""
    return BASELINE_SOURCES.copy()


def get_sources_by_type(source_type: SourceType) -> List[SourceConfig]:
    """Filter sources by type."""
    return [s for s in BASELINE_SOURCES if s.source_type == source_type]


def get_sources_by_tags(*tags: str) -> List[SourceConfig]:
    """Filter sources by tags."""
    return [s for s in BASELINE_SOURCES if any(tag in s.tags for tag in tags)]


def add_user_source(user_id: int, source: SourceConfig) -> None:
    """Add a user-specific source (stored in user_sources dict)."""
    # In production, this would go to the database
    if not hasattr(add_user_source, 'user_sources'):
        add_user_source.user_sources = {}
    
    if user_id not in add_user_source.user_sources:
        add_user_source.user_sources[user_id] = []
    
    add_user_source.user_sources[user_id].append(source)


def get_user_sources(user_id: int) -> List[SourceConfig]:
    """Get user-specific sources."""
    if not hasattr(add_user_source, 'user_sources'):
        add_user_source.user_sources = {}
    return add_user_source.user_sources.get(user_id, [])


def remove_user_source(user_id: int, source_name: str) -> bool:
    """Remove a user-specific source."""
    if not hasattr(add_user_source, 'user_sources'):
        return False
    
    if user_id not in add_user_source.user_sources:
        return False
    
    before = len(add_user_source.user_sources[user_id])
    add_user_source.user_sources[user_id] = [
        s for s in add_user_source.user_sources[user_id] if s.name != source_name
    ]
    return len(add_user_source.user_sources[user_id]) < before


def get_all_sources(user_id: Optional[int] = None) -> List[SourceConfig]:
    """Get combined baseline + user sources."""
    sources = get_baseline_sources().copy()
    
    if user_id:
        user_sources = get_user_sources(user_id)
        sources.extend(user_sources)
    
    # Sort by priority (highest first)
    return sorted(sources, key=lambda s: s.priority, reverse=True)
