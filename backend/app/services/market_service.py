"""Market data service - fetches OHLCV from multiple sources.

Sources:
- CCXT: Binance, Kraken, Coinbase Pro (with optional API keys)
- CoinGecko: free crypto price API (fallback)
- Coinlore: simple ticker API (fallback)
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import ccxt.async_support as ccxt
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MarketDataError(Exception):
    """Exception raised for market data fetching errors."""
    pass


class MarketDataService:
    """Service for fetching market data from multiple exchange APIs."""

    def __init__(self):
        # Exchange clients (lazy-loaded, cached)
        self._exchanges: Dict[str, ccxt.Exchange] = {}
        # Cache for API responses
        self._cache: Dict[str, Tuple[datetime, any]] = {}
        self._cache_ttl = 30  # seconds
        # Httpx session for CoinGecko/Coinlore
        self._http_client = httpx.AsyncClient()

    async def _get_exchange(self, exchange_id: str, api_key: str = None, secret: str = None) -> ccxt.Exchange:
        """Get or create an exchange client."""
        cache_key = f"exchange:{exchange_id}"
        if cache_key in self._exchanges:
            return self._exchanges[cache_key]

        exchange_class = getattr(ccxt, exchange_id, None)
        if not exchange_class:
            raise MarketDataError(f"Exchange {exchange_id} not supported via CCXT")

        config = {'enableRateLimit': True, 'options': {'defaultType': 'spot'}}
        if api_key and secret:
            config['apiKey'] = api_key
            config['secret'] = secret

        exchange = exchange_class(config)
        try:
            await exchange.load_markets()
            self._exchanges[cache_key] = exchange
            logger.info(f"Initialized exchange: {exchange_id}")
            return exchange
        except Exception as e:
            raise MarketDataError(f"Failed to initialize {exchange_id}: {e}")

    async def fetch_ohlcv(
        self,
        symbol: str,
        exchange_id: str = 'binance',
        timeframe: str = '1m',
        limit: int = 64,
        api_key: str = None,
        secret: str = None,
    ) -> List[Dict]:
        """
        Fetch OHLCV data from multiple sources in order of preference.

        Args:
            symbol: Trading symbol (e.g., 'BTC/USDT', 'BTCUSD', 'BTC-USD')
            exchange_id: Source identifier ('binance', 'kraken', 'coinbase', 'coingecko', 'coinlore')
            timeframe: Candlestick timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            limit: Number of candles to fetch
            api_key: Exchange API key (optional)
            secret: Exchange API secret (optional)

        Returns:
            List of OHLCV dicts with keys: timestamp, open, high, low, close, volume
        """
        # Normalize symbol for different exchanges
        normalized_symbol = self._normalize_symbol(symbol, exchange_id)
        cache_key = f"ohlcv:{exchange_id}:{normalized_symbol}:{timeframe}:{limit}"
        now = datetime.now(timezone.utc)

        # Check cache
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (now - cached_time).total_seconds() < self._cache_ttl:
                return cached_data

        try:
            # Try CCXT first (Binance, Kraken, Coinbase)
            if exchange_id in ('binance', 'kraken', 'coinbase'):
                exchange = await self._get_exchange(exchange_id, api_key, secret)
                ohlcv = await exchange.fetch_ohlcv(normalized_symbol, timeframe, limit=limit)
                result = [{
                    'timestamp': c[0],
                    'open': c[1],
                    'high': c[2],
                    'low': c[3],
                    'close': c[4],
                    'volume': c[5]
                } for c in ohlcv]

            # Try CoinGecko
            elif exchange_id == 'coingecko':
                result = await self._fetch_ohlcv_coingecko(normalized_symbol, timeframe, limit)

            # Try Coinlore
            elif exchange_id == 'coinlore':
                result = await self._fetch_ohlcv_coinlore(normalized_symbol, timeframe, limit)

            else:
                # Default to Binance
                exchange = await self._get_exchange('binance', api_key, secret)
                ohlcv = await exchange.fetch_ohlcv(normalized_symbol, timeframe, limit=limit)
                result = [{
                    'timestamp': c[0],
                    'open': c[1],
                    'high': c[2],
                    'low': c[3],
                    'close': c[4],
                    'volume': c[5]
                } for c in ohlcv]

            # Cache the result
            self._cache[cache_key] = (now, result)
            return result

        except Exception as e:
            logger.warning(f"Market fetch for {normalized_symbol} on {exchange_id} failed: {e}")
            # Fallback chain (mirrors market_fetcher): Binance → CoinGecko → Coinlore.
            if exchange_id != 'binance':
                try:
                    binance_sym = self._normalize_symbol(symbol, 'binance')
                    exchange = await self._get_exchange('binance', api_key, secret)
                    ohlcv = await exchange.fetch_ohlcv(binance_sym, timeframe, limit=limit)
                    result = [{
                        'timestamp': c[0],
                        'open': c[1],
                        'high': c[2],
                        'low': c[3],
                        'close': c[4],
                        'volume': c[5]
                    } for c in ohlcv]
                    self._cache[cache_key] = (now, result)
                    return result
                except Exception as be:
                    logger.warning(f"Binance fallback failed for {normalized_symbol}: {be}")
            # Then CoinGecko
            try:
                return await self._fetch_ohlcv_coingecko(normalized_symbol, timeframe, limit)
            except Exception:
                # Finally Coinlore
                try:
                    return await self._fetch_ohlcv_coinlore(normalized_symbol, timeframe, limit)
                except Exception:
                    raise MarketDataError(f"Failed to fetch market data for {normalized_symbol}: {e}")

    def _normalize_symbol(self, symbol: str, exchange_id: str) -> str:
        """Normalize symbol format for different exchanges."""
        if exchange_id == 'coinbase':
            # Coinbase uses format like "BTC-USD"
            return symbol.replace('/', '-').upper().replace('USDT', 'USD')
        elif exchange_id == 'kraken':
            # Kraken uses format like "XBT/USD" or "XBTUSD"
            if symbol.startswith('XBT'):
                return symbol
            return 'XBT/' + symbol.split('/')[-1].replace('USDT', 'USD') if '/' in symbol else symbol.replace('/', '-').upper()
        else:
            # Binance uses format like "BTC/USDT"
            return symbol

    async def _fetch_ohlcv_coingecko(self, symbol: str, timeframe: str, limit: int) -> List[Dict]:
        """Fetch OHLCV from CoinGecko API."""
        # Map symbol to CoinGecko coin ID (simplified)
        coin_map = {
            'BTC/USDT': 'bitcoin',
            'BTCUSD': 'bitcoin',
            'BTC-USD': 'bitcoin',
            'ETH/USDT': 'ethereum',
            'ETHUSD': 'ethereum',
            'ETH-USD': 'ethereum',
            'SOL/USDT': 'solana',
            'TON/USDT': 'toncoin',
        }
        coin_id = coin_map.get(symbol, symbol.split('/')[-1].lower().replace('usdt', '').replace('usd', ''))

        # Map timeframe to CoinGecko interval
        interval_map = {
            '1m': '1',
            '5m': '5',
            '15m': '15',
            '1h': '60',
            '4h': '240',
            '1d': '1d',
        }
        interval = interval_map.get(timeframe, '1h')

        # CoinGecko limits to ~7 days for free tier
        days = 7 if interval == '1d' else 1

        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/ohlc"
        params = {
            'vs_currency': 'usd',
            'days': days,
            'interval': interval,
        }

        try:
            res = await self._http_client.get(url, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()

            # Convert to OHLCV format
            result = []
            for entry in data:
                # entry: [timestamp_ms, open, high, low, close, volume]
                result.append({
                    'timestamp': entry[0],
                    'open': entry[1],
                    'high': entry[2],
                    'low': entry[3],
                    'close': entry[4],
                    'volume': entry[5]
                })

            # Return limited number of entries
            result = result[-limit:] if len(result) > limit else result

            # Cache
            now = datetime.now(timezone.utc)
            cache_key = f"ohlcv:coingecko:{symbol}:{timeframe}:{limit}"
            self._cache[cache_key] = (now, result)

            return result
        except Exception as e:
            logger.warning(f"CoinGecko fetch failed: {e}")
            raise

    async def _fetch_ohlcv_coinlore(self, symbol: str, timeframe: str, limit: int) -> List[Dict]:
        """Fetch OHLCV from Coinlore API (simple ticker data).

        Coinlore does not provide OHLCV candlesticks; fabricating synthetic
        candles is misleading. Return a single real price point, or [] if the
        upstream call fails (never invent candle data).
        """
        try:
            coin = symbol.split('/')[0].upper()
            pair = 'USD' if 'USD' in symbol or 'USDT' in symbol else 'USDT'
            url = f"https://www.coinlore.com/api/marketdata/{coin}/{pair}"
            res = await self._http_client.get(url, timeout=5)
            res.raise_for_status()
            data = res.json()
            current_price = float(data.get('price', 0))
            if current_price <= 0:
                return []
            now_ts = int(time.time() * 1000)
            return [{
                'timestamp': now_ts,
                'open': current_price,
                'high': current_price,
                'low': current_price,
                'close': current_price,
                'volume': 0,
            }]
        except Exception as e:
            logger.warning(f"Coinlore fetch failed: {e}")
            return []

    async def get_ticker(self, symbol: str, exchange_id: str = 'binance') -> Dict:
        """Get the latest ticker info from an exchange."""
        cache_key = f"ticker:{exchange_id}:{symbol}"
        now = datetime.now(timezone.utc)

        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (now - cached_time).total_seconds() < self._cache_ttl * 5:  # longer TTL for ticker
                return cached_data

        try:
            exchange = await self._get_exchange(exchange_id)
            normalized_symbol = self._normalize_symbol(symbol, exchange_id)
            ticker = await exchange.ticker(normalized_symbol)
            result = {
                'last': ticker['last'],
                'high': ticker['high'],
                'low': ticker['low'],
                'volume': ticker['volume']['base'],
                'timestamp': ticker['timestamp'],
            }

            self._cache[cache_key] = (now, result)
            return result
        except Exception as e:
            raise MarketDataError(f"Ticker fetch failed: {e}")

    async def close(self):
        """Close all exchange connections and HTTP clients."""
        for exchange in self._exchanges.values():
            try:
                await exchange.close()
            except:
                pass
        self._exchanges.clear()
        if hasattr(self._http_client, 'aclose'):
            await self._http_client.aclose()


# Global service instance
_market_service: Optional[MarketDataService] = None


def get_market_service() -> MarketDataService:
    """Get the global market data service instance."""
    global _market_service
    if _market_service is None:
        _market_service = MarketDataService()
    return _market_service
