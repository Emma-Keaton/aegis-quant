# Aegis Quant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![Telegram Mini App](https://img.shields.io/badge/Telegram-Mini_App-26A5E4.svg)](https://core.telegram.org/bots/webapps)

**Aegis Quant** is a production-grade quantitative trading platform delivered as a Telegram Mini App. It combines institutional-grade market analysis, AI-powered forecasting, and secure multi-venue execution — all controlled via a native Telegram interface.

---

## 🏗 Architecture: Dual-Engine Design

```
┌─────────────────────────────────────────────────────────────────┐
│                        AEGIS QUANT STACK                         │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────────────────────────────┐   │
│  │   FRONTEND   │◄───►│           BACKEND (FastAPI)           │   │
│  │  React 19 +  │     │  ┌─────────────┐ ┌─────────────┐     │   │
│  │  Tailwind 4  │     │  │  ENGINE A   │ │  ENGINE B   │     │   │
│  │  Telegram    │     │  │ Technical   │ │  Social     │     │   │
│  │  Mini App    │     │  │  Core       │ │  Scout      │     │   │
│  └──────────────┘     │  │ (Blue-Chip) │ │ (Momentum)  │     │   │
│                       │  └──────┬──────┘ └──────┬──────┘     │   │
│                       │         │               │             │   │
│                       │         └───────┬───────┘             │   │
│                       │                 ▼                     │   │
│                       │    ┌───────────────────────┐          │   │
│                       │    │     KRONOS AI          │          │   │
│                       │    │  (Render, CPU-only)    │          │   │
│                       │    │  OHLCV → 30 Monte Carlo │          │   │
│                       │    │  trajectories + CI     │          │   │
│                       │    └───────────┬────────────┘          │   │
│                       │                 │                      │   │
│                       │    ┌───────────────────────┐          │   │
│                       │    │  GEMINI FLASH-LITE     │          │   │
│                       │    │  (3-key rotation)      │          │   │
│                       │    │  Execution formatting  │          │   │
│                       │    │  Telegram chat bot     │          │   │
│                       │    └───────────┬────────────┘          │   │
│                       │                 │                      │   │
│                       │    ┌───────────────────────┐          │   │
│                       │    │  EXECUTION GATEWAY     │          │   │
│                       │    │  CCXT (Bybit/OKX)      │          │   │
│                       │    │  Web3.py (EVM)         │          │   │
│                       │    │  Solana-py (Jupiter)   │          │   │
│                       │    │  TON Connect (Ston.fi) │          │   │
│                       │    └───────────────────────┘          │   │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Engine A: Technical Core (Blue-Chip Autopilot)
- **Assets**: User-defined whitelist (BTC, ETH, SOL, TON, etc.) — **CRUD from frontend**
- **Data**: CCXT Pro WebSocket (ticker, orderbook, trades, funding) + REST fallback
- **Triggers**: Price >2%/1m, Volume >3x avg, Spread <10bps, Funding flip
- **Forecast**: Kronos AI (128 candles → 30 Monte Carlo trajectories, 90% CI)
- **Risk**: Kelly sizing + allocation caps, SL/TP, max concurrent trades
- **Cycle**: Event-driven (<5s reaction) + 5-min scheduled fallback scan

## 📡 Engine B: Social Scout (Momentum Discovery)
- **Sources**: Twitter (twscrape multi-account), Reddit (URS), Telegram (Telethon), RSS (Scrapy)
- **Parsing**: Groq Llama3-70B for ticker extraction from unstructured text
- **Sentiment**: FinBERT + volume spike detection (3x baseline)
- **Liquidity**: Jupiter (Solana) + Ston.fi (TON) pool depth audit (>$50k, <5% impact)
- **Cycle**: 30-minute scans → Kronos validation → execution

---

## 🔐 Security & Key Management
| Component | Implementation |
|-----------|----------------|
| **Auth** | Telegram `initData` HMAC-SHA256 verification → `chat_id` as primary key |
| **CeFi Keys** | AES-256-GCM encrypted at rest, per-user, per-exchange (Bybit/OKX/Binance) |
| **User Input** | Keys entered via Wallet page → never in `.env`, never in logs |
| **Paper/Live** | Complete isolation — separate execution paths, audit trail |

---

## 🤖 AI Integration
| Model | Purpose | Free Tier |
|-------|---------|-----------|
| **Kronos** | OHLCV trajectory forecasting (30 Monte Carlo paths) | Render CPU-only |
| **Gemini 2.5 Flash-Lite** | Trade execution formatting, Telegram chat bot, risk explanations | 3 keys × 1,500 req/day, 30 RPM |
| **Groq Llama3-70B** | Social media ticker/entity extraction | 14,400 req/day |

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 19, TypeScript, Tailwind CSS 4, Vite 6, `@twa.js/telegram-web-app` |
| **Backend** | FastAPI 0.115, Python 3.11+, SQLAlchemy 2.0, asyncpg, Redis |
| **Database** | Supabase (PostgreSQL 16 + TimescaleDB + pgvector) |
| **Cache/Queue** | Upstash Redis (Pub/Sub, Celery broker, rate limiting) |
| **Scheduling** | APScheduler AsyncIO (Engine A/B loops) |
| **Task Queue** | Celery + Redis (scraping, backtests) |
| **Exchanges** | CCXT Pro (WS), ccxt (REST) — Bybit, OKX, Binance |
| **DeFi** | web3.py (EVM), solana-py (Jupiter), TON Connect v2 (Ston.fi) |
| **AI** | google-generativeai (Gemini), Groq, Kronos (PyTorch CPU) |
| **Telegram Bot** | python-telegram-bot v21 (webhook mode) |
| **Monitoring** | Prometheus `/metrics`, structured JSON logs |

---

## 📊 Database Schema (Supabase + TimescaleDB)

| Table | Purpose | RLS |
|-------|---------|-----|
| `profiles` | One per Telegram user (wallet, settings, engine config) | ✅ |
| `user_credentials` | Encrypted CeFi API keys (Bybit/OKX/Binance) | ✅ |
| `user_whitelist` | **Engine A symbols — CRUD from frontend** | ✅ |
| `risk_settings` | SL/TP, allocation, drawdown, concurrent limits | ✅ |
| `paper_balances` | Paper trading balances per asset | ✅ |
| `positions` | Open positions (SL/TP/trailing, PnL) | ✅ |
| `trade_logs` | Unified execution history (paper + live) | ✅ |
| `signals` | Engine A (Kronos) + Engine B (Social) with forecast data | ✅ |
| `alert_rules` | User-defined alerts with trigger tracking | ✅ |
| `execution_audit` | Immutable audit trail (trigger type, confidence, status) | ✅ |
| `market_ticks` | Raw trades (TimescaleDB hypertable, 7-day retention) | — |
| `market_candles` | OHLCV (TimescaleDB hypertable, 1-year retention) | — |
| `social_signals` | Sentiment data (TimescaleDB hypertable, 30-day retention) | — |

---

## 🚀 Deployment

| Service | Platform | Config |
|---------|----------|--------|
| **Frontend** | Vercel | `VITE_API_URL`, `VITE_WS_URL` |
| **Backend** | Render Web Service | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **Kronos AI** | Render Web Service | `render.yaml` (CPU-only PyTorch, 512MB, auto-sleep) |
| **Database** | Supabase | PostgreSQL + TimescaleDB + pgvector |
| **Cache** | Upstash Redis | Serverless, free tier |
| **Telegram** | BotFather | Webhook → `/api/v1/telegram/webhook` |

---

## 🔧 Local Development

```bash
# 1. Clone & install
git clone https://github.com/yourusername/aegis-quant.git
cd aegis-quant

# 2. Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Fill in your keys

# 3. Database (Supabase or local Docker)
docker-compose up -d postgres redis

# 4. Run migrations (Supabase SQL Editor)
# Copy-paste supabase/migrations/0001_initial_schema.sql
# Copy-paste supabase/migrations/0002_seed_data.sql

# 5. Start backend
uvicorn app.main:app --reload --port 8000

# 6. Frontend (separate terminal)
cd ../
npm install && npm run dev
# Open http://localhost:3000
```

---

## 🔑 Required Environment Variables

```env
# Database
DATABASE_URL=postgresql://postgres:xxx@db.xxx.supabase.co:5432/postgres
REDIS_URL=rediss://default:xxx@xxx.upstash.io:6379

# Encryption (32-byte base64)
ENCRYPTION_KEY=<generate: python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())">

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_BOT_USERNAME=aegisquantbot
APP_URL=https://your-app.vercel.app
TELEGRAM_WEBHOOK_SECRET=<openssl rand -hex 32>

# Kronos AI (after Render deploy)
KRONOS_API_URL=https://kronos-ai.onrender.com
KRONOS_API_KEY=<from Render>

# AI Keys
GEMINI_API_KEY_1=<aistudio.google.com/apikey>
GEMINI_API_KEY_2=<aistudio.google.com/apikey>
GEMINI_API_KEY_3=<aistudio.google.com/apikey>
GROQ_API_KEY=<console.groq.com/keys>

# Engine A Thresholds
ENGINE_A_PRICE_CHANGE_THRESHOLD=0.02
ENGINE_A_VOLUME_SPIKE_THRESHOLD=3.0
ENGINE_A_SPREAD_BPS_THRESHOLD=10
ENGINE_A_FUNDING_FLIP_ENABLED=true
ENGINE_A_MIN_CONFIDENCE=0.70
```

---

## 📁 Project Structure

```
aegis-quant/
├── backend/                    # FastAPI Backend
│   ├── app/
│   │   ├── api/v1/            # REST endpoints (state, signals, execute, chat, risk, wallet, whitelist, logs, rules, telegram)
│   │   ├── core/              # encryption, telegram_auth, exceptions, math_helpers
│   │   ├── engines/           # engine_a (WS triggers), engine_b (social), kronos_client, risk_validator, execution_router, gemini_client
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── api/websocket.py   # Real-time updates
│   │   └── main.py            # FastAPI entrypoint
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── ai-service/                 # Kronos AI Service (Render)
│   ├── app/
│   │   ├── main.py            # /forecast, /health
│   │   └── model/             # Kronos wrapper (placeholder for shiyu-coder/Kronos)
│   ├── render.yaml            # Render Blueprint
│   └── Dockerfile
│
├── src/                        # React Frontend
│   ├── components/            # Dashboard, Intel, Strategy, Wallet, Logs, PnLChart
│   ├── services/              # api.ts, websocket.ts, telegram.ts
│   └── hooks/
│
├── supabase/
│   ├── migrations/
│   │   ├── 0001_initial_schema.sql  # All 13 tables + RLS + TimescaleDB
│   │   └── 0002_seed_data.sql       # Test user + sample signals
│   └── README.md
│
├── docker-compose.yml          # Local dev stack
├── PLAN.md                     # Full implementation plan
└── README.md
```

---

## 🧪 Testing Checklist

- [ ] Health: `GET /health`
- [ ] Auth: `GET /api/v1/me` with `X-Telegram-Init-Data`
- [ ] State: `GET /api/v1/state` → dashboard data
- [ ] Whitelist CRUD: `GET/POST/DELETE /api/v1/whitelist`
- [ ] CeFi Keys: `POST/GET/DELETE /api/v1/wallet/cefi-keys` + test connection
- [ ] Signals: `GET /api/v1/signals?engine=A` / `?engine=B`
- [ ] Execute: `POST /api/v1/execute` (paper mode)
- [ ] Chat: `POST /api/v1/chat` → Gemini responses
- [ ] WebSocket: `ws://localhost:8000/ws/updates?initData=...`
- [ ] Risk: `GET/PATCH /api/v1/risk` + presets
- [ ] Backtest: `POST /api/v1/backtest`
- [ ] Telegram Bot: `/portfolio`, `/signals`, `/risk`, `/panic`, `/help`

---

## 📈 Roadmap

- [ ] **Engine A**: Full CCXT Pro WS integration (Bybit/OKX)
- [ ] **Engine B**: twscrape + Telethon + URS scrapers
- [ ] **Kronos**: Load shiyu-coder/Kronos weights, quantize + JIT compile
- [ ] **DeFi Execution**: web3.py (1inch), solana-py (Jupiter), TON Connect
- [ ] **Backtesting**: Qlib Alpha158 + FreqAI + FinRL integration
- [ ] **Mobile**: Native Telegram WebApp features (haptics, theme sync, biometric)
- [ ] **Analytics**: Grafana dashboards, Prometheus alerts

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## ⚠️ Disclaimer

**This software is for research and educational purposes only.** Not financial advice. Trading cryptocurrencies carries substantial risk of loss. The authors are not responsible for any financial losses incurred through use of this software. Always test thoroughly in paper mode before live trading.

---

## 🙏 Acknowledgments

- [shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos) — Autoregressive candlestick forecasting
- [AI4Finance-Foundation/FinRL](https://github.com/AI4Finance-Foundation/FinRL) — DRL trading frameworks
- [microsoft/qlib](https://github.com/microsoft/qlib) — Quantitative investment platform
- [freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) — FreqAI ML pipelines
- [vladcalin/twscrape](https://github.com/vladcalin/twscrape) — Twitter scraping
- [Telethon/Telethon](https://github.com/Telethon/Telethon) — Telegram MTProto
- [ccxt/ccxt](https://github.com/ccxt/ccxt) — Unified exchange API
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) — Telegram Bot API

---

**Built with ❤️ for the quant trading community**