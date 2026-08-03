# Adding Sources to Engine B — Watch Crypto Callers

## Quick Add via API

### 1. Twitter/X Account
```bash
curl -X POST http://localhost:8000/api/sources/my \
  -H "Content-Type: application/json" \
  -H "x-telegram-init-data: your_init_data" \
  -d '{
    "name": "CryptoCaller",
    "source_type": "twitter",
    "url_or_handle": "cryptoanalyst",
    "priority": 9,
    "tags": ["altcoins", "calls"]
  }'
```

### 2. Telegram Channel
```bash
curl -X POST http://localhost:8000/api/sources/my \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Solana Whales",
    "source_type": "telegram",
    "url_or_handle": "@solwhales",
    "priority": 8,
    "tags": ["solana", "whale"]
  }'
```

### 3. RSS Feed
```bash
curl -X POST http://localhost:8000/api/sources/my \
  -H "Content-Type: application/json" \
  -d '{
    "name": "CoinDesk",
    "source_type": "rss",
    "url_or_handle": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "priority": 7,
    "tags": ["news", "major"]
  }'
```

### 4. Reddit Community
```bash
curl -X POST http://localhost:8000/api/sources/my \
  -H "Content-Type: application/json" \
  -d '{
    "name": "r/solana",
    "source_type": "reddit",
    "url_or_handle": "solana",
    "priority": 6,
    "tags": ["reddit", "solana"]
  }'
```

---

## Via Frontend (Recommended)

1. Open the app in Telegram
2. Go to **Intel** tab
3. Click **Add Source** button
4. Select type: Twitter / Telegram / RSS / Reddit
5. Enter handle/URL
6. Set priority (1-10)
7. Add tags for categorization

---

## Format by Source Type

| Source Type | Format | Example |
|-------------|--------|---------|
| Twitter | Handle (no @) | `VitalikButerin`, `cz_binance` |
| Telegram | @channel | `@CryptoCurrency`, `@solwhales` |
| RSS | Full URL | `https://cointelegraph.com/rss` |
| Reddit | Subreddit | `solana`, `ethereum`, `CryptoCurrency` |

---

## Pre-configured Sources (Already Active)

### Twitter
- `VitalikButerin` — Ethereum founder
- `cz_binance` — Binance CEO
- `solana` — Official Solana
- `WHAlerts` — Whale alerts
- `lookchain` — On-chain data

### Telegram
- `@CryptoCurrency` — General discussion
- `@SolanaScamAlert` — Security alerts
- `@CryptoWhale` — Whale movements
- `@BitcoinWhale` — BTC whale tracking

### RSS
- CoinTelegraph
- Bitcoin Magazine
- Decrypt
- CoinDesk
- The Block

---

## How to Find Handles

### Twitter/X
1. Go to profile page
2. Copy handle (no @ symbol)
3. Example: `https://twitter.com/elonmusk` → handle is `elonmusk`

### Telegram
1. Search for channel
2. Click channel info
3. Copy @username

### RSS Feeds
1. Find website
2. Look for RSS icon or `/feed` endpoint
3. Common pattern: `https://site.com/rss` or `https://site.com/feed`

---

## Testing Your Source

```bash
# View all your sources
curl http://localhost:8000/api/sources/my

# View combined sources (what Engine B uses)
curl http://localhost:8000/api/sources/combined

# Remove a source
curl -X DELETE http://localhost:8000/api/sources/my/{source_id}
```

---

## Engine B Monitoring

Engine B scans sources every 30 minutes:
- Twitter: Checks for new tweets from followed accounts
- Telegram: Polls channels for new messages
- RSS: Fetches latest posts
- Reddit: Monitors subreddit posts

Signals are sent to Gemini for sentiment analysis, then to Kronos for forecasting.
