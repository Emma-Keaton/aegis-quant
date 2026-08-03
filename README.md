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

### Secure Trading
- **AES-256-GCM Encryption**: API keys encrypted at rest
- **Session-based Auth**: Telegram initData HMAC verification
- **Risk Circuit Breakers**: Kelly sizing, max allocation, drawdown limits
- **Paper/Live Isolation**: Complete separation with audit trail

### Admin & Management
- **Admin Dashboard**: Secure shutdown, market refresh, execution logs
- **Source Management**: Full CRUD for monitoring sources
- **User Control**: Custom watchlists, risk settings, paper balance

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- Supabase PostgreSQL database
- Telegram Bot Token (from @BotFather)

### Backend Setup
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials (see Environment Variables below)

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup
```bash
# Install dependencies
npm install --legacy-peer-deps

# Build for production
npm run build

# Serve the built files
npm start
```

### Deploy to Render

**Backend Service:**
- Connect repo: `Emma-Keaton/aegis-quant`
- Root Directory: `backend`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Env vars: See Configuration section

**Frontend Service:**
- Connect same repo
- Build: `npm install --legacy-peer-deps && npm run build`
- Publish Dir: `dist`

---

## 📁 Project Structure

```
aegis-quant/
├── backend/                          # FastAPI backend
│   ├── app/
│   │   ├── api/v1/                  # API routes (18 modules)
│   │   │   ├── admin.py            # Admin endpoints
│   │   │   ├── auth.py             # Telegram auth
│   │   │   ├── solana.py           # Jupiter/DexScreener
│   │   │   ├── sources.py          # Source management
│   │   │   └── ...
│   │   ├── engines/                 # Trading engines
│   │   │   ├── aegis_engine.py     # Main AI engine
│   │   │   ├── engine_b.py         # Social scrapers
│   │   │   └── gemini_client.py    # Gemini Flash
│   │   ├── services/                # Business logic
│   │   │   ├── jupiter_client.py   # Jupiter API
│   │   │   ├── dexscreener_client.py # Token data
│   │   │   ├── market_service.py   # CCXT integration
│   │   │   └── kronos_service.py   # HF forecasting
│   │   └── models/                  # SQLAlchemy models
│   ├── alembic/                     # Database migrations
│   └── requirements.txt
├── src/                             # React frontend
│   ├── components/                  # UI components
│   │   ├── Wallet.tsx              # Multi-chain wallet
│   │   ├── Intel.tsx               # Market signals
│   │   └── AdminDashboard.tsx      # Admin panel
│   ├── crypto/                      # Wallet connectors
│   │   ├── evmConnector.ts         # Wagmi/EVM
│   │   └── solanaConnector.ts      # Phantom/Solflare
│   └── db/                          # Supabase client
├── dist/                            # Built frontend
├── render.yaml                      # Render deployment config
├── docker-compose.yml               # Local development
└── README.md
```

---

## 🔧 Configuration

### Required Environment Variables
```bash
# Database (Supabase)
DATABASE_URL="postgresql://postgres.[REF]:[PASS]@db.[REF].supabase.co:5432/postgres"
SUPABASE_URL="https://[REF].supabase.co"
SUPABASE_ANON_KEY="eyJ..."
SUPABASE_SERVICE_ROLE_KEY="eyJ..."

# Telegram
TELEGRAM_BOT_TOKEN="123456:ABC..."
ADMIN_CHAT_ID=123456789

# Security
ENCRYPTION_KEY="your_32_byte_base64_key"
SESSION_SECRET="random_string"

# AI Services
GEMINI_API_KEY_1="AIza..."
GEMINI_API_KEY_2=""
GEMINI_API_KEY_3=""

# WalletConnect (for EVM wallets)
WALLET_CONNECT_PROJECT_ID="your_project_id"

# Solana (optional - defaults to public RPC)
SOLANA_RPC_URL="https://api.mainnet-beta.solana.com"
```

### Generate Required Keys
```bash
# Encryption key (32 bytes base64)
openssl rand -base64 32

# Session secret
openssl rand -hex 32
```

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 19, TypeScript, Tailwind CSS 4, Vite 6 |
| **Wallet** | Wagmi v2, RainbowKit, @solana/web3.js |
| **Backend** | FastAPI, Python 3.11+, SQLAlchemy, asyncpg |
| **Database** | PostgreSQL (Supabase) |
| **AI/ML** | Gemini Flash (LLM), VectorBT (backtesting) |
| **Trading** | CCXT (CEX), Jupiter API (Solana DEX), DexScreener |
| **Infrastructure** | Render, Docker, GitHub Actions |

---

## 📊 API Endpoints (65+ routes)

### Authentication
```
POST /api/auth/init        # Login with Telegram initData
POST /api/auth/refresh     # Refresh session token
POST /api/auth/logout      # Logout
GET  /api/auth/me          # Get current user
```

### Trading (CEX)
```
GET    /api/state              # Get dashboard state
POST   /api/toggle-agent       # Enable/disable bot
POST   /api/toggle-mode        # Paper/Live mode
POST   /api/panic              # Emergency close all
POST   /api/execute            # Execute trade
GET    /api/logs               # Trade history
```

### Solana DEX Trading (Jupiter)
```
GET    /api/solana/price/{symbol}      # Get token price
GET    /api/solana/market/{symbol}     # Market data
POST   /api/solana/quote               # Get swap quote
POST   /api/solana/swap                # Get swap transaction
GET    /api/solana/trending            # Top gaining tokens
GET    /api/solana/search/{query}      # Token search
```

### Source Management (Engine B)
```
GET    /api/sources/my           # User's custom sources
POST   /api/sources/my           # Add source
GET    /api/sources/admin        # All baseline sources (admin)
POST   /api/sources/admin        # Add baseline (admin only)
GET    /api/sources/combined     # All sources for scanning
```

### Admin
```
POST   /api/admin/shutdown      # Graceful shutdown
GET    /api/admin/status        # System status
POST   /api/admin/refresh       # Refresh market data
GET    /api/admin/executions    # View executions
```

### Backtesting
```
POST /backtest              # Run backtest (VectorBT)
```

---

## 🚨 Deployment Checklist

- [ ] Create Supabase project at https://supabase.com/dashboard
- [ ] Get database connection string (pooler recommended)
- [ ] Create Telegram bot via @BotFather
- [ ] Get Telegram chat ID via @userinfobot
- [ ] Generate encryption key: `openssl rand -base64 32`
- [ ] Get Gemini API key from https://aistudio.google.com/apikey
- [ ] Get WalletConnect project ID from https://cloud.walletconnect.com
- [ ] Set all environment variables in Render dashboard
- [ ] Run `alembic upgrade head` after deploy
- [ ] Test `/api/health` endpoint
- [ ] Test `/api/auth/init` with Telegram initData
- [ ] Test `/api/solana/price/SOL` endpoint

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| `DEPLOYMENT.md` | Full deployment guide |
| `SUPABASE_SETUP.md` | Supabase configuration |
| `SOLANA_INTEGRATION.md` | Solana/Jupiter integration |
| `ADDING_SOURCES.md` | How to add monitoring sources |
| `PRE_DEPLOYMENT_CHECKLIST.md` | Pre-deployment verification |

---

## 📜 License

MIT License - see LICENSE for details.

---

**Built for the crypto trading community** 🚀
