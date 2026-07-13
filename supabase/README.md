# Aegis Quant - Database Setup (Supabase)

## Quick Start

### 1. Create Supabase Project
1. Go to [supabase.com](https://supabase.com) → New Project
2. Choose region close to your users
3. Save the **Database Password** (you'll need it for connection string)

### 2. Enable Extensions
Go to **SQL Editor** → New Query and run:
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "timescaledb";
CREATE EXTENSION IF NOT EXISTS "pgvector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
```

### 3. Run Migrations
In **SQL Editor** → New Query, copy-paste and run:
1. `supabase/migrations/0001_initial_schema.sql`
2. `supabase/migrations/0002_seed_data.sql`

### 4. Get Connection String
**Settings** → **Database** → **Connection String** → **Transaction Pooler (IPv4)**
```
postgresql://postgres:[YOUR_PASSWORD]@db.[REF].supabase.co:5432/postgres?sslmode=require
```

### 5. Configure Backend `.env`
```env
DATABASE_URL=postgresql://postgres:xxx@db.xxx.supabase.co:5432/postgres?sslmode=require
```

---

## Tables Overview

| Table | Purpose | RLS |
|-------|---------|-----|
| `profiles` | One per Telegram user (PK = `telegram_id`) | ✅ |
| `user_credentials` | Encrypted CeFi API keys (Bybit/OKX/Binance) | ✅ |
| `user_whitelist` | Engine A symbols (CRUD from frontend) | ✅ |
| `risk_settings` | SL/TP, allocation, drawdown limits | ✅ |
| `paper_balances` | Paper trading balances per asset | ✅ |
| `positions` | Open positions (paper + live) | ✅ |
| `trade_logs` | Unified execution history | ✅ |
| `signals` | Engine A (Kronos) + Engine B (Social) | ✅ |
| `alert_rules` | Custom user alerts | ✅ |
| `execution_audit` | Immutable audit trail | ✅ |
| `market_ticks` | Raw trades (TimescaleDB hypertable) | - |
| `market_candles` | OHLCV (TimescaleDB hypertable) | - |
| `social_signals` | Social sentiment (TimescaleDB hypertable) | - |

---

## Key Design Decisions

### 1. **Telegram `chat_id` as Primary Auth**
- `profiles.telegram_id` = Telegram user ID (extracted from `initData`)
- No separate auth system needed
- Frontend sends `X-Telegram-Init-Data` header on every request

### 2. **CeFi Keys Encrypted at Rest**
- AES-256-GCM via `app/core/encryption.py`
- Keys never leave backend decrypted
- Frontend only sees `connected: true/false`

### 3. **Whitelist CRUD from Frontend**
```
GET    /api/v1/whitelist           → List user's symbols
POST   /api/v1/whitelist           → Add symbol(s)
DELETE /api/v1/whitelist/{symbol}  → Remove symbol
PATCH  /api/v1/whitelist/{symbol}/toggle → Enable/disable
```
Engine A picks up changes instantly (no restart needed).

### 4. **Paper vs Live Mode**
- `profiles.trading_mode` = `'paper'` | `'live'`
- `trade_logs.execution_type` tracks which mode
- Paper uses simulated fills; Live uses CCXT/Web3

### 5. **TimescaleDB for Time-Series**
- `market_ticks` - raw trades (retention: 7 days)
- `market_candles` - OHLCV (retention: 1 year)
- `social_signals` - sentiment (retention: 30 days)
- Automatic partitioning + compression

---

## Development Workflow

### Local Development
```bash
# Start local Postgres + Redis
docker-compose up -d postgres redis

# Run migrations
psql $DATABASE_URL -f supabase/migrations/0001_initial_schema.sql
psql $DATABASE_URL -f supabase/migrations/0002_seed_data.sql

# Start backend
cd backend && uvicorn app.main:app --reload
```

### Test User
Seed data creates test user `telegram_id = 123456789`
- Whitelist: BTC, ETH, SOL, TON (Bybit, 1m)
- Risk: 3% SL, 6% TP, 10% max alloc, 3 concurrent
- Paper balance: 10,000 USDT

---

## Production Checklist

- [ ] Enable **Point-in-Time Recovery** (PITR) in Supabase
- [ ] Set up **Daily Backups** to S3/GCS
- [ ] Configure **Connection Pooling** (PgBouncer) for high traffic
- [ ] Enable **Read Replicas** for analytics queries
- [ ] Set **RLS policies** reviewed by security team
- [ ] Add **audit logging** for sensitive operations
- [ ] Configure **pg_stat_statements** for query monitoring

---

## Useful Queries

```sql
-- Active users with bot enabled
SELECT telegram_id, username, trading_mode, bot_enabled 
FROM profiles WHERE bot_enabled = true;

-- Recent signals for user
SELECT * FROM recent_signals WHERE telegram_id = 123456789;

-- User's open positions
SELECT symbol, side, size, entry_price, current_price, unrealized_pnl
FROM positions WHERE profile_id = (SELECT id FROM profiles WHERE telegram_id = 123456789);

-- Daily trade volume
SELECT DATE(executed_at), COUNT(*), SUM(total_value_usd)
FROM trade_logs 
WHERE executed_at > NOW() - INTERVAL '30 days'
GROUP BY DATE(executed_at)
ORDER BY DATE(executed_at) DESC;

-- Engine A trigger analysis
SELECT trigger_type, COUNT(*), AVG(kronos_confidence)
FROM execution_audit 
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY trigger_type;
```