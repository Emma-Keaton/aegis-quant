# Aegis Quant — AI-Powered Crypto Trading Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![Telegram Mini App](https://img.shields.io/badge/Telegram-Mini_App-26A5E4.svg)](https://core.telegram.org/bots/webapps)

**Aegis Quant** is a production-grade quantitative trading platform delivered as a Telegram Mini App. It combines multi-agent AI analysis, real-time social sentiment, and secure multi-venue execution — CEX via CCXT and Solana DEX via Jupiter — all controlled via a native Telegram interface.

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    AEGIS QUANT PLATFORM                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────────────────────────────┐   │
│  │   FRONTEND   │◄───►│           BACKEND (FastAPI)           │   │
│  │  React 19 +  │     │  ┌─────────────────────────────┐     │   │
│  │  Tailwind 4  │     │  │    AEGIS ENGINE (AI)        │     │   │
│  │  Telegram    │     │  │  ┌─────────┬─────────┬────┐ │     │   │
│  │  Mini App    │     │  │  │Technical│ Sentiment │ Risk│ │     │   │
│  │  + Wagmi     │     │  │  │ Analyst │  Analyst  │Anlyst││     │   │
│  │  + Rainbow   │     │  │  └────┬────┴────┬──────┴────┘ │     │   │
│  └──────────────┘     │  │       └─────────┼─────────────┘ │     │   │
│                       │  │                 ▼               │     │   │
│                       │  │        ┌──────────────┐         │     │   │
│                       │  │        │  Portfolio    │         │     │   │
│                       │  │        │  Manager      │         │     │   │
│                       │  │        └──────┬───────┘         │     │   │
│                       │  └───────────────┼─────────────────┘     │   │
│                       │                 │                        │   │
│                       │    ┌────────────▼────────────┐           │   │
│                       │    │     DATA LAYER          │           │   │
│                       │    │  ┌───────────────────┐  │           │   │
│                       │    │  │  Gemini Flash     │  │           │   │
│                       │    │  │  (Multi-Agent LLM)│  │           │   │
│                       │    │  │  CCXT (100+ Exch) │  │           │   │
│                       │    │  │  Jupiter API      │  │           │   │
│                       │    │  │  DexScreener      │  │           │   │
│                       │    │  │  VectorBT         │  │           │   │
│                       │    │  └───────────────────┘  │           │   │
│                       │    └─────────────────────────┘           │   │
│                       └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## ✨ Features

### AI-Powered Trading Engine
- **Multi-Agent Analysis**: Gemini Flash-powered Technical, Sentiment, and Risk analysts
- **Consensus Voting**: Ensemble decision-making with weighted confidence scoring
- **Hybrid Execution**: CCXT for CEXs + Jupiter API for Solana DEX
- **Real-time Monitoring**: Engine A (technical) + Engine B (social sentiment)

### Multi-Venue Trading
| Venue | Technology | Supported Tokens |
|-------|------------|------------------|
| **CEX** | CCXT (100+ exchanges) | BTC, ETH, SOL, XRP, AVAX, etc. |
| **Solana DEX** | Jupiter API + DexScreener | BONK, WIF, PEPE, DOGE, POPCAT, etc. |
| **EVM Chains** | Wagmi + RainbowKit | Ethereum, BSC, Polygon |

### Social Intelligence (Engine B)
- **Twitter/X**: Twikit-based sentiment analysis
- **RSS Feeds**: CoinTelegraph, Bitcoin Magazine, Decrypt, CoinDesk
- **Telegram**: Channel monitoring via Telethon
- **Reddit**: Subreddit scanning
- **Custom Sources**: Add any RSS feed, Twitter handle, or Telegram channel

### Monitoring & Observability
- **Prometheus**: Metrics collection at `/metrics` endpoint
- **Grafana Cloud**: Dashboards, alerts, and visualization
- **Admin Dashboard**: Real-time metrics in Telegram Mini App
- **Error Tracking**: Automated error counting and alerting

### Secure Trading
- **AES-256-GCM Encryption**: API keys encrypted at rest
- **Session-based Auth**: Telegram initData HMAC verification
- **Risk Circuit Breakers**: Kelly sizing, max allocation, drawdown limits
- **Paper/Live Isolation**: Complete separation with audit trail

### Admin & Management
- **Admin Dashboard**: Secure shutdown, market refresh, execution logs
- **Source Management**: Full CRUD for monitoring sources
- **User Control**: Custom watchlists, risk settings, paper balance
- **Monitoring Tab**: Real-time trading metrics and system health

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- Supabase PostgreSQL database
- Telegram Bot Token (from @BotFather)
- WalletConnect Cloud project ID (for EVM wallet connect)

### Backend Setup
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Apply schema (via Supabase — see Deployment below), then start API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup
```bash
# Install dependencies
npm install

# Copy frontend env
cp .env.example .env.local
# Set VITE_API_URL=http://localhost:8000 and VITE_WALLET_CONNECT_PROJECT_ID

# Development server
npm run dev

# Production build
npm run build
```

---

## ☁️ Deployment

### 1. Supabase (Postgres)
1. Create a project at [supabase.com](https://supabase.com).
2. Install the Supabase CLI and link it: `supabase link --project-ref <REF>`.
3. Apply the schema migration: `supabase db push`.
   - The canonical schema lives in `supabase/migrations/20260806120000_aegis_init.sql`
     (15 tables, 5 enums, triggers, seed data).
4. From **Project Settings → Database**, copy the connection string (direct or pooler)
   for `DATABASE_URL`, plus `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY`.

### 2. Render — Backend API (`aegis-quant-api`, type `web`)
- Root directory: `backend`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`
- `AEGIS_ROLE=web` — on boot it registers the Telegram webhook + bot commands.
- Set all required secrets from `backend/.env.example` (DATABASE_URL, SUPABASE_URL,
  SUPABASE_SERVICE_ROLE_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, ENCRYPTION_KEY, ...).
- `API_PUBLIC_URL` is set automatically from `RENDER_EXTERNAL_URL` (see `render.yaml`).

### 3. Render — Worker (`aegis-quant-worker`, type `worker`)
- Root directory: `backend`
- Build: `pip install -r requirements.txt`
- Start: `python worker.py`
- `AEGIS_ROLE=worker` — starts the trading engines (A/B), Telethon channel polling,
  and market feed; only the web service handles webhooks.

### 4. Vercel — Frontend
- Framework: Vite. Build: `npm run build`, output `dist/`.
- Set env vars: `VITE_API_URL=https://<your-api>.onrender.com`,
  `VITE_WALLET_CONNECT_PROJECT_ID=...`.
- `vercel.json` provides the SPA rewrite so Telegram Mini App routes work.

### 5. Telegram
- Create the bot with @BotFather; set the bot username in `TELEGRAM_BOT_USERNAME`.
- Webhook registration is automatic: the API calls `setWebhook` to
  `{API_PUBLIC_URL}/api/telegram/webhook` with a `secret_token` on startup.
- Open the bot and press **Start** — the `/start` command launches the Mini App
  (`APP_URL`) via a WebApp button.

### Auth & Security
- The Mini App authenticates via Telegram `initData` (HMAC-verified server-side);
  a server-side session token is then issued (`/api/auth/init`).
- All `/api/*` requests send `X-Telegram-Init-Data` + `Authorization: Bearer <session>`.
- Secrets are validated at startup when `ENVIRONMENT=production` — the process fails
  fast if any required key is missing.

---

## 📁 Project Structure

```
aegis-quant/
├── backend/                          # FastAPI backend
│   ├── app/
│   │   ├── api/v1/                  # API routes
│   │   │   ├── admin.py            # Admin endpoints
│   │   │   ├── auth.py             # Telegram auth / init
│   │   │   ├── solana.py           # Jupiter/DexScreener
│   │   │   ├── telegram.py         # Webhook handler
│   │   │   └── ...
│   │   ├── engines/                 # Trading engines
│   │   │   ├── engine_a.py         # Technical + Kronos
│   │   │   ├── engine_b.py         # Social sentiment
│   │   │   └── engine_scheduler.py # Loop scheduler
│   │   ├── core/                    # Auth, security, config
│   │   ├── models/                  # SQLAlchemy models
│   │   ├── services/                # Business logic
│   │   ├── telegram/                # Bot handlers + webhook registration
│   │   └── strategies/              # Freqtrade adapter
│   ├── worker.py                    # Worker entrypoint (engines/telethon)
│   └── requirements.txt
├── supabase/migrations/             # Canonical Postgres schema (SQL)
├── src/                             # React frontend
│   ├── components/                  # UI components
│   │   ├── AdminDashboard.tsx
│   │   ├── StrategyPlaybook.tsx     # YAML strategy library
│   │   ├── Wallet.tsx               # Multi-chain wallet
│   │   └── Intel.tsx                # Market signals
│   ├── strategies/                  # YAML trading strategy playbooks
│   │   ├── index.ts                 # Strategy loader
│   │   ├── trader.ts                # Strategy-driven trader
│   │   └── *.yaml                   # Playbooks (bull_trend, etc.)
│   ├── crypto/                      # Wallet connectors
│   │   ├── evmConnector.ts         # Wagmi/EVM
│   │   └── solanaConnector.ts      # Phantom/Solflare
│   └── api/client.ts                # API client (initData + session auth)
├── public/                          # Static assets
├── render.yaml                      # Render API + worker config
├── vercel.json                      # Vercel SPA rewrite
└── backend/.env.example             # Backend env template
