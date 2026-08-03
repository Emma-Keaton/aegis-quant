# Pre-Deployment Checklist — Aegis Quant

## Database & Environment

- [ ] Create Supabase project at https://supabase.com/dashboard
- [ ] Copy connection string (pooler recommended for production)
- [ ] Generate encryption key: `openssl rand -base64 32`
- [ ] Create Telegram bot via @BotFather
- [ ] Get Telegram chat ID via @userinfobot
- [ ] Get Gemini API key from https://aistudio.google.com/apikey
- [ ] Get WalletConnect project ID from https://cloud.walletconnect.com

## Required Environment Variables

```bash
# ── SUPABASE ─────────────────────────────────────────────────────
DATABASE_URL="postgresql://postgres.[REF]:[PASS]@db.[REF].supabase.co:5432/postgres"
SUPABASE_URL="https://[REF].supabase.co"
SUPABASE_ANON_KEY="eyJ..."
SUPABASE_SERVICE_ROLE_KEY="eyJ..."

# ── TELEGRAM ─────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
TELEGRAM_BOT_USERNAME="aegisquantbot"
ADMIN_CHAT_ID=123456789

# ── SECURITY ─────────────────────────────────────────────────────
ENCRYPTION_KEY="your_32_byte_key"
SESSION_SECRET="your_random_secret"

# ── AI SERVICES ──────────────────────────────────────────────────
GEMINI_API_KEY_1="AIza..."
GEMINI_API_KEY_2=""
GEMINI_API_KEY_3=""

# ── WALLETCONNECT ────────────────────────────────────────────────
WALLET_CONNECT_PROJECT_ID="your_project_id"

# ── SOLANA (optional) ────────────────────────────────────────────
SOLANA_RPC_URL="https://api.mainnet-beta.solana.com"
```

## Migration & Database

- [ ] Run `alembic upgrade head` after deployment
- [ ] Verify tables created: profiles, signals, trade_logs, positions, user_credentials, user_sources, admin_sources
- [ ] (Optional) Enable TimescaleDB: `CREATE EXTENSION IF NOT EXISTS timescaledb;`

## Backend Verification

- [ ] Health check: `GET /health` returns 200
- [ ] Auth test: `POST /api/auth/init` with valid Telegram initData
- [ ] Sources test: `GET /api/sources/combined` returns baseline sources
- [ ] Solana price test: `GET /api/solana/price/SOL` returns price
- [ ] Solana quote test: `POST /api/solana/quote` with token symbol
- [ ] Dashboard state test: `GET /api/state` returns user state

## Frontend Verification

- [ ] Build passes: `npm run build`
- [ ] Dist folder has index.html and assets/
- [ ] Telegram Mini App loads in Telegram
- [ ] Auth works (connects to backend)
- [ ] Wallet connect works (MetaMask, Phantom)
- [ ] Source management works (add/remove sources)
- [ ] Admin dashboard accessible (with correct ADMIN_CHAT_ID)

## Security Checklist

- [ ] All API keys stored as env vars (not in code)
- [ ] .env file added to .gitignore
- [ ] ENCRYPTION_KEY is 32 bytes, randomly generated
- [ ] ADMIN_CHAT_ID matches your Telegram ID
- [ ] HTTPS enabled (required for Telegram Mini App)
- [ ] CORS configured for your domain

## Known Issues / Limitations

| Item | Status | Notes |
|------|--------|-------|
| signals.py mock fallback | OK | Uses real Kronos when available, mock as fallback |
| PnLChart mock data | OK | Demo data, replace with real trades post-deploy |
| Engine B Twitter | Needs credentials | Twikit requires browser automation setup |
| Engine B Telegram | Needs credentials | Requires TELEGRAM_API_ID + TELEGRAM_API_HASH |
| Kronos local model | Optional | Uses placeholder if not deployed |
| Paper trading | ✅ Ready | Default mode, no exchange keys needed |
| Live trading | Needs API keys | Set via frontend Wallet page |

## Deployment Steps

### Option 1: Render (Recommended)

1. Connect GitHub repo to Render
2. Create two services:
   - **Backend**: Python, `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Frontend**: Static, publish dir `dist`
3. Set all env vars in Render dashboard
4. Deploy
5. Run migrations: `curl POST /api/admin/migrate` (or manual alembic)

### Option 2: Docker

```bash
# Build and run
docker-compose up -d

# Run migrations
docker exec aegis-backend alembic upgrade head
```

### Option 3: VPS

```bash
# Install dependencies
cd backend && pip install -r requirements.txt
cd .. && npm install --legacy-peer-deps && npm run build

# Run with PM2
pm2 start backend/venv/bin/uvicorn --name aegis-backend -- app.main:app --host 0.0.0.0 --port 8000
pm2 start npm --name aegis-frontend -- run start
```

## Post-Deployment Tasks

1. Test Telegram bot: `/start` command
2. Add your first source via API or frontend
3. Connect exchange API keys (Binance, Bybit, etc.)
4. Set up Solana wallet (Phantom/Solflare)
5. Enable paper trading and verify
6. Gradually enable live trading

## Quick Test Commands

```bash
# Health
curl https://your-backend.onrender.com/health

# Auth (get initData from Telegram)
curl -X POST https://your-backend.onrender.com/api/auth/init \
  -H "Content-Type: application/json" \
  -d '{"init_data": "your_telegram_init_data"}'

# Sources
curl https://your-backend.onrender.com/api/sources/combined

# Solana price
curl https://your-backend.onrender.com/api/solana/price/SOL

# Solana quote
curl -X POST https://your-backend.onrender.com/api/solana/quote \
  -H "Content-Type: application/json" \
  -d '{"token_symbol": "BONK", "amount_usd": 10}'
```
