# Aegis Quant — AI-Powered Crypto Trading Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![Telegram Mini App](https://img.shields.io/badge/Telegram-Mini_App-26A5E4.svg)](https://core.telegram.org/bots/webapps)

**Aegis Quant** is a production-grade quantitative trading platform delivered as a Telegram Mini App. It combines institutional-grade market analysis, AI-powered forecasting, and secure multi-venue execution — all controlled via a native Telegram interface.

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
│  └──────────────┘     │  │  │ Analyst │  Analyst  │Anlyst││     │   │
│                       │  │  └────┬────┴────┬──────┴────┘ │     │   │
│                       │  │       └─────────┼─────────────┘ │     │   │
│                       │  │                 ▼               │     │   │
│                       │  │        ┌──────────────┐         │     │   │
│                       │  │        │  Portfolio   │         │     │   │
│                       │  │        │   Manager    │         │     │   │
│                       │  │        └──────┬───────┘         │     │   │
│                       │  └───────────────┼─────────────────┘     │   │
│                       │                 │                        │   │
│                       │    ┌────────────▼────────────┐           │   │
│                       │    │     DATA LAYER          │           │   │
│                       │    │  ┌───────────────────┐  │           │   │
│                       │    │  │  Kronos (HF Model) │  │           │   │
│                       │    │  │  Gemini Flash (LLM)│  │           │   │
│                       │    │  │  CCXT (100+ Exch)  │  │           │   │
│                       │    │  │  VectorBT (Backtest)│  │           │   │
│                       │    │  └───────────────────┘  │           │   │
│                       │    └─────────────────────────┘           │   │
│                       └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## ✨ Features

### AI-Powered Trading Engine
- **Multi-Agent Analysis**: Technical, Sentiment, and Risk analysts using Gemini Flash
- **Kronos Forecasting**: Local foundation model from Hugging Face for price predictions
- **Consensus Voting**: Ensemble decision-making with weighted confidence
- **Real-time Execution**: CCXT integration with 100+ exchanges

### Social Intelligence (Engine B)
- **Twitter/X**: Twikit-based sentiment analysis
- **RSS Feeds**: CoinTelegraph, Bitcoin Magazine, Decrypt
- **Telegram**: Channel monitoring via Telethon
- **On-Chain**: Whale movements via CoinGecko

### Secure Trading
- **AES-256-GCM Encryption**: API keys encrypted at rest
- **Session-based Auth**: Telegram initData verification
- **Risk Circuit Breakers**: Kelly sizing, max allocation, drawdown limits
- **Paper/Live Isolation**: Complete separation of test and production

### Admin & Management
- **Admin Dashboard**: Secure shutdown, market refresh, execution logs
- **Source Management**: Add/remove data sources via API
- **User Control**: Custom watchlists, risk settings, paper balance

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL/Supabase database
- Telegram Bot Token (from @BotFather)

### Backend Setup
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials:
#   TELEGRAM_BOT_TOKEN=xxx
#   ADMIN_CHAT_ID=your_chat_id
#   DATABASE_URL=postgresql://...
#   ENCRYPTION_KEY=your_32_byte_key

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup
```bash
# Install dependencies (may take 5-10 minutes)
npm install --legacy-peer-deps

# Build for production
npm run build

# Serve dist/ (or use Vite dev server)
npm run dev
```

### Deploy to Render
1. **Backend**: Connect repo, set env vars, deploy
2. **Kronos Service**: Deploy separately (requires GPU/CPU with torch)
3. **Frontend**: Connect same repo, build command `npm run build`, publish dir `dist`

---

## 📁 Project Structure

```
aegis-quant/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/v1/            # API routes
│   │   │   ├── admin.py       # Admin endpoints
│   │   │   ├── sources.py     # Source management
│   │   │   ├── state.py       # User state
│   │   │   └── ...
│   │   ├── engines/
│   │   │   ├── aegis_engine.py # Main AI engine
│   │   │   ├── engine_b.py    # Social scrapers
│   │   │   ├── gemini_client.py # Gemini LLM
│   │   │   └── ...
│   │   ├── services/
│   │   │   ├── market_service.py # CCXT/CoinGecko
│   │   │   ├── kronos_service.py # HF model
│   │   │   └── source_registry.py
│   │   └── ...
│   ├── alembic/               # Database migrations
│   └── requirements.txt
├── src/                       # React frontend
│   ├── components/
│   │   ├── AdminDashboard.tsx
│   │   ├── Dashboard.tsx
│   │   ├── Logs.tsx
│   │   └── ...
│   ├── crypto/
│   │   ├── evmConnector.ts    # WalletConnect
│   │   └── solanaConnector.ts # Phantom/Solflare
│   └── ...
├── dist/                      # Built frontend
├── package.json
├── docker-compose.yml
└── README.md
```

---

## 🔧 Configuration

### Required Environment Variables
```bash
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
ADMIN_CHAT_ID=your_telegram_chat_id

# Database
DATABASE_URL=postgresql://user:pass@host:5432/aegis_quant

# Security
ENCRYPTION_KEY=your_32_byte_base64_key

# AI Services
GEMINI_API_KEY_1=your_gemini_key_1
GEMINI_API_KEY_2=
GEMINI_API_KEY_3=
```

### Optional Configuration
```bash
# Kronos (optional - uses Hugging Face by default)
KRONOS_SERVICE_URL=https://your-kronos-service.onrender.com

# Exchange API Keys (stored encrypted in DB)
# Set via frontend Wallet page
```

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 19, TypeScript, Tailwind CSS 4, Vite 6 |
| **Backend** | FastAPI, Python 3.11+, SQLAlchemy, asyncpg |
| **Database** | PostgreSQL (Supabase) |
| **AI/ML** | Gemini Flash, Kronos (Hugging Face), VectorBT |
| **Trading** | CCXT (100+ exchanges), Telegram Bot API |
| **Infrastructure** | Docker, Render, GitHub Actions |

---

## 📊 APIs

### Authentication
```
POST /api/auth/init        # Login with Telegram initData
POST /api/auth/refresh     # Refresh session token
POST /api/auth/logout      # Logout
GET  /api/auth/me          # Get current user
```

### Trading
```
GET    /api/state              # Get dashboard state
POST   /api/toggle-agent       # Enable/disable bot
POST   /api/toggle-mode        # Paper/Live mode
POST   /api/panic              # Emergency close all
POST   /api/execute-trade      # Execute trade
GET    /api/engine/analysis    # Run AI analysis
```

### Sources (Engine B)
```
GET    /api/sources/my          # User's custom sources
POST   /api/sources/my          # Add source
GET    /api/sources/admin       # All baseline sources
POST   /api/sources/admin       # Add baseline (admin only)
GET    /api/sources/combined    # All sources for scanning
```

### Backtesting
```
POST   /api/backtest/run        # Run backtest
```

### Admin
```
POST   /api/admin/shutdown      # Graceful shutdown
GET    /api/admin/status        # System status
POST   /api/admin/refresh       # Refresh market data
GET    /api/admin/executions    # View executions
```

---

## 🚨 Deployment Checklist

- [ ] Set `TELEGRAM_BOT_TOKEN` in Render
- [ ] Set `ADMIN_CHAT_ID` to your Telegram chat ID
- [ ] Set `DATABASE_URL` to Supabase Postgres
- [ ] Generate `ENCRYPTION_KEY` with `openssl rand -base64 32`
- [ ] Add `GEMINI_API_KEY_1` (required for analysis)
- [ ] Run `alembic upgrade head` after deploy
- [ ] Test `/api/auth/init` with valid Telegram initData
- [ ] Configure CORS origins for your domain
- [ ] Set up HTTPS (required for Telegram Mini App)

---

## 📜 License

MIT License - see LICENSE for details.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `cd backend && pytest`
5. Submit a pull request

---

**Built with ❤️ for the crypto trading community**
