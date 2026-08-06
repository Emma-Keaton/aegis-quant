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
- Grafana Cloud account (free tier)

### Backend Setup
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

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
- Env vars: See Configuration section below

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
│   │   │   ├── metrics.py          # Admin metrics API
│   │   │   └── ...
│   │   ├── engines/                 # Trading engines
│   │   │   ├── aegis_engine.py     # Main AI engine
│   │   │   ├── engine_b.py         # Social scrapers
│   │   │   └── gemini_client.py    # Gemini Flash
│   │   ├── metrics/                 # Prometheus metrics
│   │   │   ├── __init__.py         # Registry + /metrics
│   │   │   └── trading.py          # Trade metrics
│   │   ├── services/                # Business logic
│   │   │   ├── jupiter_client.py   # Jupiter API
│   │   │   ├── dexscreener_client.py # Token data
│   │   │   └── market_service.py   # CCXT integration
│   │   ├── agents/                  # Trading agents
│   │   │   └── trading_agents.py   # Multi-agent framework
│   │   └── strategies/              # Trading strategies
│   │       └── freqtrade_adapter.py # 4 strategies
│   ├── alembic/                     # Database migrations
│   └── requirements.txt
├── src/                             # React frontend
│   ├── components/                  # UI components
│   │   ├── AdminDashboard.tsx      # Admin panel + monitoring
│   │   ├── Wallet.tsx              # Multi-chain wallet
│   │   └── Intel.tsx               # Market signals
│   ├── crypto/                      # Wallet connectors
│   │   ├── evmConnector.ts         # Wagmi/EVM
│   │   └── solanaConnector.ts      # Phantom/Solflare
│   └── db/                          # Supabase client
├── public/                          # Static assets
│   ├── icons/                       # App icons
│   ├── favicon.ico                  # Favicon
│   └── manifest.json                # PWA manifest
├── dist/                            # Built frontend
├── render.yaml 
