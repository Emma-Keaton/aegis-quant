# Aegis Quant - Full Stack Production Integration Plan

## Executive Summary

This plan merges the **Aegis Quant** frontend (React/TypeScript/Telegram Mini App) with a **production-grade Python backend** built from the best components of 20+ open-source quant frameworks. The architecture follows the dual-engine design from `backend.md`: **Engine A (Technical Core)** for blue-chip autopilot + **Engine B (Social Scout)** for momentum discovery, both feeding into **Kronos AI** for forecasting and **Gemini Flash-Lite** for execution formatting + Telegram chat.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AEGIS QUANT PRODUCTION STACK                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────────────────────────────────────────┐  │
│  │   FRONTEND   │     │                    BACKEND                        │  │
│  │  (Current)   │◄───►│  ┌────────────────────────────────────────────┐   │  │
│  │  React 19 +  │     │  │          FASTAPI ORCHESTRATOR              │   │  │
│  │  Tailwind 4  │     │  │  (APScheduler + Redis + WebSocket)         │   │  │
│  │  Telegram    │     │  └────────────────────┬────────────────────────┘   │  │
│  │  Mini App    │     │                       │                            │  │
│  └──────────────┘     │       ┌───────────────┼───────────────┐            │  │
│                       │       ▼               ▼               ▼            │  │
│  ┌──────────────┐     │  ┌─────────┐    ┌──────────┐    ┌──────────┐     │  │
│  │   EXISTING   │     │  │ ENGINE A│    │ ENGINE B │    │  KRONOS  │     │  │
│  │   APIs       │     │  │ Technical│   │  Social  │    │   AI     │     │  │
│  │  /api/*      │     │  │  Core   │   │  Scout   │    │ (Render) │     │  │
│  └──────────────┘     │  │ (CCXT   │   │ (twscrape│    │          │     │  │
│                       │  │  WS +    │   │  + Tele- │    │  OHLCV   │     │  │
│                       │  │  REST)   │   │  gram +  │    │  Token-  │     │  │
│                       │  └────┬─────┘   │   RSS)   │    │  izer    │     │  │
│                       │       │         └────┬─────┘    └────┬─────┘     │  │
│                       │       │              │             │             │  │
│                       │       └──────────────┼─────────────┘             │  │
│                       │                      ▼                           │  │
│                       │           ┌─────────────────────┐                │  │
│                       │           │  AI DECISION ENGINE │                │  │
│                       │           │  (Gemini Flash-Lite │                │  │
│                       │           │   + Risk Validator) │                │  │
│                       │           └──────────┬──────────┘                │  │
│                       │                      │                            │  │
│                       │                      ▼                            │  │
│                       │           ┌─────────────────────┐                │  │
│                       │           │  EXECUTION GATEWAY  │                │  │
│                       │           │  CCXT (CEX) +       │                │  │
│                       │           │  Web3.py/Solana-py  │                │  │
│                       │           │  (DEX) + TON Connect│                │  │
│                       │           └─────────────────────┘                │  │
│                       └────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Repository Integration Map

| Category | Source Repo | Key Components to Extract | Integration Target |
|----------|-------------|---------------------------|-------------------|
| **Forecasting** | `shiyu-coder/Kronos` | OHLCV tokenizer, autoregressive model, Monte Carlo sampler | `ai-service/kronos/` (deployed on Render) |
| **RL/Strategy** | `AI4Finance-Foundation/FinRL` | DRL agents (PPO, SAC, A2C), env wrappers | `backend/engines/rl_strategies.py` |
| **Quant Platform** | `microsoft/qlib` | Alpha158/Alpha360 factors, backtest engine, workflow | `backend/quant/qlib_adapter.py` |
| **FreqAI/ML** | `freqtrade/freqtrade` | Feature engineering, model training pipeline, hyperopt | `backend/ml/freqai_pipeline.py` |
| **Twitter Scraping** | `vladcalin/twscrape` | Multi-account rotation, rate-limit handling | `backend/scrapers/twitter_scraper.py` |
| **Twitter Alt** | `peter-sun/twikit` | No-API-key scraping fallback | `backend/scrapers/twikit_fallback.py` |
| **Telegram** | `Telethon/Telethon` | MTProto channel streaming, message parsing | `backend/scrapers/telegram_stream.py` |
| **Reddit** | `skandabhairava/Universal-Reddit-Scraper` | Subreddit monitoring, comment sentiment | `backend/scrapers/reddit_scraper.py` |
| **RSS/News** | `scrapy/scrapy` | Financial feed crawling, article extraction | `backend/scrapers/rss_crawler.py` |
| **Anti-bot** | `apify/crawlee-python` | Browser automation for gated content | `backend/scrapers/crawlee_browser.py` |
| **CEX Execution** | `ccxt/ccxt` | 100+ exchange unified API, WS orderbook | `backend/execution/ccxt_gateway.py` |
| **EVM/DeFi** | `web3py/web3.py` | Uniswap v3, contract interaction, gas estimation | `backend/execution/evm_gateway.py` |
| **Solana** | `solana-labs/solana-py` | Jupiter/Raydium routing, SPL token ops | `backend/execution/solana_gateway.py` |
| **TON** | `ton-connect/demo-dapp-with-wallet` | Tonkeeper handshake, transaction signing | `backend/execution/ton_gateway.py` |
| **Telegram Bot** | `python-telegram-bot/python-telegram-bot` | Webhook handler, command router, inline keyboards | `backend/telegram/bot_handler.py` |
| **Agent Framework** | `langchain-ai/langgraph` | Stateful multi-agent graphs, checkpointing | `backend/agents/langgraph_orchestrator.py` |
| **RAG/Assistant** | `phidatahq/phidata` | Vector DB, knowledge base, agent memory | `backend/agents/rag_assistant.py` |
| **Scheduling** | `agronholm/apscheduler` | Async job scheduler, cron/interval triggers | `backend/scheduler/engine_scheduler.py` |
| **Task Queue** | `celery/celery` | Distributed scraping workers, retry/backoff | `backend/workers/celery_app.py` |
| **Time-series DB** | `timescale/timescaledb` | Hypertable for ticks, candles, sentiment | `backend/db/timescale_models.py` |

---

## 3. Backend Directory Structure

```
E:\Projects\aegis-quant\
├── backend/                          # NEW: Python FastAPI Backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI entrypoint
│   │   ├── config.py                 # Pydantic settings (env-driven)
│   │   ├── database.py               # Supabase/PostgreSQL + TimescaleDB
│   │   ├── redis_client.py           # Redis connection pool
│   │   ├── middleware/
│   │   │   ├── auth.py               # Telegram initData verification
│   │   │   ├── rate_limit.py         # Per-user rate limiting
│   │   │   └── audit.py              # Request/response logging
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py               # Profile, risk settings, credentials
│   │   │   ├── trade.py              # Positions, orders, history
│   │   │   ├── signal.py             # Kronos forecasts, social signals
│   │   │   └── market.py             # OHLCV, orderbook, funding rates
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── telegram.py           # InitData, User, WebAppData
│   │   │   ├── trading.py            # OrderRequest, Position, RiskParams
│   │   │   ├── signals.py            # SignalResponse, ForecastData
│   │   │   └── whitelist.py          # Whitelist CRUD schemas
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── state.py          # GET /api/state (dashboard)
│   │   │   │   ├── signals.py        # GET /api/signals (Kronos + Social)
│   │   │   │   ├── execute.py        # POST /api/execute-trade
│   │   │   │   ├── chat.py           # POST /api/chat (Gemini bot)
│   │   │   │   ├── risk.py           # GET/POST /api/risk-profile
│   │   │   │   ├── wallet.py         # Wallet connect, CeFi keys
│   │   │   │   ├── backtest.py       # POST /api/backtest
│   │   │   │   ├── rules.py          # Alert rules CRUD
│   │   │   │   ├── logs.py           # Trade/activity logs
│   │   │   │   ├── telegram.py       # Webhook endpoint
│   │   │   │   └── whitelist.py      # Whitelist CRUD endpoints
│   │   │   └── websocket.py          # Real-time updates
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── encryption.py         # AES-256-GCM for API keys
│   │   │   ├── telegram_auth.py      # initData verification
│   │   │   └── exceptions.py         # Custom exceptions
│   │   ├── engines/
│   │   │   ├── __init__.py
│   │   │   ├── engine_a.py           # Technical Core (Blue-chip) - EVENT DRIVEN
│   │   │   ├── engine_b.py           # Social Scout (Momentum)
│   │   │   ├── kronos_client.py      # Render HTTP client
│   │   │   ├── risk_validator.py     # SL/TP, Kelly, position sizing
│   │   │   └── execution_router.py   # CEX/DEX order routing
│   │   ├── scrapers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # Abstract scraper interface
│   │   │   ├── twitter_scraper.py    # twscrape multi-account
│   │   │   ├── twikit_fallback.py    # twikit no-API scraping
│   │   │   ├── telegram_stream.py    # Telethon channel listener
│   │   │   ├── reddit_scraper.py     # URS/JSON subreddit monitor
│   │   │   ├── rss_crawler.py        # Scrapy financial feeds
│   │   │   ├── crawlee_browser.py    # Browser for gated sites
│   │   │   ├── ticker_parser.py      # LLM (Groq Llama3) entity extraction
│   │   │   ├── sentiment.py          # FinBERT + volume spike detection
│   │   │   └── liquidity_audit.py    # Jupiter/Ston.fi pool checks
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── langgraph_orchestrator.py  # Multi-agent graph
│   │   │   ├── analyst_agents.py    # Fundamental, Technical, Sentiment, News
│   │   │   ├── researcher_agents.py # Bull/Bear debate
│   │   │   ├── trader_agent.py      # Execution decision
│   │   │   ├── risk_agents.py       # Risk Mgmt + Portfolio Manager
│   │   │   └── rag_assistant.py     # Phidata vector search
│   │   ├── ml/
│   │   │   ├── __init__.py
│   │   │   ├── freqai_pipeline.py  # Feature eng, training, inference
│   │   │   ├── qlib_adapter.py     # Alpha factor pipeline
│   │   │   └── rl_strategies.py    # FinRL PPO/SAC agents
│   │   ├── execution/
│   │   │   ├── __init__.py
│   │   │   ├── ccxt_gateway.py     # Bybit, OKX, Binance...
│   │   │   ├── evm_gateway.py      # Uniswap v3, 1inch
│   │   │   ├── solana_gateway.py   # Jupiter, Raydium
│   │   │   └── ton_gateway.py      # Ston.fi, TON Connect
│   │   ├── scheduler/
│   │   │   ├── __init__.py
│   │   │   ├── engine_scheduler.py # APScheduler dual-engine loops
│   │   │   └── jobs.py             # Cron definitions
│   │   ├── workers/
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py       # Celery + Redis broker
│   │   │   ├── scrape_tasks.py     # Distributed scraping
│   │   │   └── backtest_tasks.py   # Heavy backtest offload
│   │   ├── telegram/
│   │   │   ├── __init__.py
│   │   │   ├── bot_handler.py      # PTB application setup
│   │   │   ├── commands.py         # /watch, /risk, /panic, /portfolio
│   │   │   ├── rag_handler.py      # Conversational Q&A
│   │   │   └── formatter.py        # Signal formatting for TG
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── timeframes.py       # TF normalization
│   │       ├── math_helpers.py     # Kelly, Sharpe, MDD calc
│   │       └── validators.py       # Input validation
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── fixtures/
│   ├── requirements.txt
│   ├── requirements-cpu.txt        # PyTorch CPU for Render
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── .env.example
│   └── alembic/                    # DB migrations
│
├── ai-service/                     # Kronos AI Service (Render Deployment)
│   ├── app/
│   │   ├── main.py                 # FastAPI server
│   │   ├── model/
│   │   │   ├── kronos.py           # Model wrapper
│   │   │   ├── tokenizer.py        # OHLCV dual-token encoding
│   │   │   └── sampler.py          # Monte Carlo trajectory gen
│   │   ├── api/
│   │   │   ├── forecast.py         # POST /forecast
│   │   │   └── health.py           # GET /health
│   │   └── config.py
│   ├── requirements.txt            # torch CPU, transformers, fastapi
│   ├── Dockerfile
│   └── render.yaml                 # Render.com blueprint
│
├── src/                            # EXISTING: React Frontend
│   ├── components/
│   ├── hooks/
│   ├── services/
│   │   ├── api.ts                  # UPDATED: Point to new backend
│   │   ├── websocket.ts            # NEW: Real-time connection
│   │   └── telegram.ts             # TWA integration
│   └── ...
│
├── server.ts                       # EXISTING: Dev proxy (DEPRECATE)
├── PLAN.md                         # THIS FILE
└── README.md
```

---

## 4. Phase-by-Phase Implementation Plan

### Phase 0: Foundation & Environment (Week 1)
- [ ] Create `backend/` directory with FastAPI project structure
- [ ] Set up Python 3.11+ venv, install core deps (fastapi, uvicorn, pydantic, sqlalchemy, asyncpg, redis, python-telegram-bot, ccxt, apscheduler, celery)
- [ ] Configure Supabase PostgreSQL + TimescaleDB extension (run SQL from backend.md Section IV + additions below)
- [ ] Set up Redis (local + Render/Upstash for prod)
- [ ] Implement AES-256-GCM encryption for CeFi keys (backend.md Section III.2)
- [ ] Implement Telegram `initData` verification middleware (backend.md Section III.1) - extracts `user.id` (chat_id) as primary auth
- [ ] Create `.env.example` with all required keys
- [ ] Write Dockerfile + docker-compose.yml for local dev

### Phase 1: Engine A - Technical Core (Week 2) - **EVENT-DRIVEN HYBRID**
- [ ] Build `CCXTGateway`: unified REST + WebSocket for Bybit (primary), OKX, Binance
- [ ] Implement `CCXTWebSocketManager`: persistent WS connections for ticker, orderbook, trades, funding
- [ ] Create trigger engine: price >2%/1m, volume >3x avg, spread <10bps, funding flip
- [ ] On trigger: fetch latest 128 candles (REST, cached) → call Kronos → risk validate → execute
- [ ] Fallback: 5-min scheduled full scan of all whitelisted symbols (catches missed triggers)
- [ ] Create `KronosClient`: HTTP client to Render-deployed Kronos service (async, queued)
- [ ] Implement OHLCV tokenizer (dual-token format: time + value tokens)
- [ ] Build Monte Carlo sampler: N=30 trajectories, confidence intervals
- [ ] Create `RiskValidator`: Kelly sizing, SL/TP, max allocation, concurrent trade limits
- [ ] Add paper/live mode toggle per user (Redis flag + DB persist)
- [ ] **Whitelist CRUD endpoints**: GET/POST/DELETE `/api/whitelist` (frontend controlled)

### Phase 2: Engine B - Social Scout (Week 3)
- [ ] Implement `TwitterScraper` using twscrape: multi-account pool, rotation, rate-limit handling
- [ ] Add `TwikitFallback` for no-API-key scraping
- [ ] Build `TelegramStream` with Telethon: join signal channels, real-time message parsing
- [ ] Implement `RedditScraper`: r/CryptoCurrency, r/Solana, r/TON, etc.
- [ ] Create `RSSCrawler` with Scrapy: CoinDesk, The Block, Decrypt, CoinTelegraph
- [ ] Add `CrawleeBrowser` for gated forums (Alpha groups, Discord via web)
- [ ] Build `TickerParser`: Groq Llama3-70B for entity extraction from raw text
- [ ] Implement `SentimentAnalyzer`: FinBERT + volume spike detection (3x baseline)
- [ ] Create `LiquidityAuditor`: Jupiter (Solana) + Ston.fi (TON) pool depth checks
- [ ] Wire Engine B loop: scrape → parse → sentiment → liquidity → Kronos → execute (30-min interval)

### Phase 3: Kronos AI Service Deployment (Week 3-4, Parallel)
- [ ] Create `ai-service/` with FastAPI wrapper around Kronos model
- [ ] Configure `requirements-cpu.txt`: `--index-url https://download.pytorch.org/whl/cpu torch transformers`
- [ ] Implement `/forecast` endpoint: accepts OHLCV array, returns N trajectories + stats
- [ ] Add `/health` endpoint for Render monitoring
- [ ] Quantize model: `torch.quantization.dynamic_quantize` for 512MB RAM
- [ ] JIT compile: `torch.jit.trace` for 3-5x speedup
- [ ] Write `render.yaml` for Blueprint deploy (free tier: 512MB RAM, CPU-only)
- [ ] Set up keep-alive ping (cron-job.org every 10min) to prevent cold starts
- [ ] Deploy to Render, verify latency < 2s for 128-candle input
- [ ] Update `backend/engines/kronos_client.py` with production URL + API key auth

### Phase 4: AI Decision Engine + Gemini Integration (Week 4)
- [ ] Build `ExecutionRouter`: CEX (CCXT) vs DEX (EVM/Solana/TON) routing
- [ ] Implement `GeminiClient` with 3-key rotation (free tier: 1,500 req/day/key, 30 RPM Flash-Lite)
- [ ] Create structured output schemas for:
  - Trade execution formatting (JSON → order params)
  - Telegram chat responses (intent classification + params)
  - Risk explanation (why trade rejected/approved)
- [ ] Build `LangGraphOrchestrator`: Analyst → Researcher → Trader → Risk → Portfolio Manager
- [ ] Implement agent nodes:
  - `FundamentalsAnalyst`: On-chain metrics, tokenomics
  - `TechnicalAnalyst`: RSI, MACD, EMAs, Kronos forecast
  - `SentimentAnalyst`: Social volume, sentiment score, spike alerts
  - `NewsAnalyst`: RSS headlines, macro events
  - `BullResearcher` / `BearResearcher`: Structured debate
  - `TraderAgent`: Entry, size, SL, TP, route
  - `RiskManagementAgent`: Portfolio heat, correlation, drawdown
  - `PortfolioManagerAgent`: Final approve/reject
- [ ] Add `RAGAssistant` (Phidata): Vector store of trade logs, scrape cache, user Q&A

### Phase 5: Telegram Bot & Two-Way Interface (Week 5)
- [ ] Set up `python-telegram-bot` v21+ with webhook mode
- [ ] Implement command handlers (auth via `initData` → `chat_id`):
  - `/watch <token>` - Add to whitelist
  - `/risk <conservative|medium|aggressive>` - Set risk profile
  - `/panic` - Flatten all positions
  - `/portfolio` - Current holdings + PnL
  - `/signals` - Latest Engine A/B signals
  - `/settings` - Toggle paper/live, notifications
- [ ] Implement RAG conversational handler: "Why did you buy SOL at 12:40?"
- [ ] Build `SignalFormatter`: Rich Telegram messages with inline keyboards (Approve/Reject)
- [ ] Add webhook endpoint: `POST /api/telegram/webhook`
- [ ] Implement user authentication via `initData` on every command

### Phase 6: Frontend Integration (Week 5-6)
- [ ] Update `src/services/api.ts`: Point all calls to new FastAPI backend
- [ ] Add WebSocket service (`src/services/websocket.ts`): Real-time PnL, positions, signals
- [ ] Replace mock `/api/signals` with real Kronos + Social data
- [ ] Connect `Intel.tsx` to Engine B social signals (Twitter/Reddit/Telegram cards)
- [ ] Connect `Strategy.tsx` to risk settings API + agent config + **whitelist manager UI**
- [ ] Connect `Wallet.tsx` to CeFi key encryption + TON Connect flow
- [ ] Connect `Dashboard.tsx` to real-time WebSocket state
- [ ] Add Telegram Mini App `initData` forwarding to all API calls (header: `X-Telegram-Init-Data`)
- [ ] Implement haptic feedback + theme sync via `@twa.js/telegram-web-app`

### Phase 7: Backtesting & Validation (Week 6)
- [ ] Integrate Qlib backtest engine: Alpha158 factors, walk-forward validation
- [ ] Add FreqAI pipeline: Feature engineering → XGBoost/LightGBM → hyperopt
- [ ] Implement FinRL backtest: PPO/SAC agents on historical data
- [ ] Create `/api/backtest` endpoint: Accept strategy config, return equity curve, Sharpe, MDD, trade log
- [ ] Add Monte Carlo validation: 1000 resamples of trade sequence
- [ ] Build backtest result visualization data for `PnLChart.tsx`

### Phase 8: Security, Monitoring & Production Hardening (Week 7)
- [ ] Audit all encryption: AES-256-GCM for keys, Fernet for PII
- [ ] Implement rate limiting: 100 req/min per user, 1000 req/min per IP
- [ ] Add structured logging (JSON) + correlation IDs
- [ ] Set up Prometheus metrics: `/metrics` endpoint (request latency, engine loops, trade count)
- [ ] Configure Grafana dashboards: Engine health, PnL, API latency, error rates
- [ ] Add Sentry/Logtail for error tracking
- [ ] Write integration tests: Engine A/B loops, execution paths, Telegram commands
- [ ] Load test: 100 concurrent users, 1000 req/min
- [ ] Create deployment scripts: Render (backend), Vercel (frontend), Render (Kronos AI)

### Phase 9: Documentation & Launch (Week 8)
- [ ] Write API docs (OpenAPI/Swagger at `/docs`)
- [ ] Create user guide: Telegram bot commands, risk settings, paper vs live
- [ ] Document architecture for future contributors
- [ ] Record demo video
- [ ] Production deploy + smoke test
- [ ] Monitor first 48h for issues

---

## 5. Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Backend Framework** | FastAPI | Async native, auto OpenAPI, type-safe, high performance |
| **Database** | Supabase (PostgreSQL) + TimescaleDB | Managed, auth built-in, time-series optimized |
| **Cache/Queue** | Redis (Upstash/Render) | Pub/sub for WebSocket, Celery broker, rate limiting |
| **Scheduler** | APScheduler AsyncIO | Single-process, runs both engines safely |
| **Task Queue** | Celery + Redis | Offload scraping/backtest to workers |
| **Kronos Hosting** | Render.com (CPU-only PyTorch) | Free tier supports 512MB, auto-sleep, HTTPS |
| **Kronos Optimization** | Quantized + JIT compiled | 512MB RAM limit, 3-5x speedup |
| **Kronos Keep-Alive** | cron-job.org ping every 10min | Prevent 30s+ cold starts |
| **Gemini Model** | `gemini-2.5-flash-lite` (3 keys rotated) | 30 RPM, 1.5K RPD free; 3 keys = 4.5K/day |
| **Social LLM** | Groq Llama3-70B (free tier) | Fast inference for ticker parsing |
| **Sentiment** | FinBERT (local) + volume spike | No API cost, runs in scraper worker |
| **TON Wallet** | TON Connect v2 + Tonkeeper | Native mobile deep links |
| **EVM/DeFi** | web3.py + 1inch/Jupiter aggregation | Best price routing |
| **Real-time** | WebSocket (FastAPI native) | Sub-second PnL/position updates |
| **Telegram Bot** | python-telegram-bot v21 (webhook) | Async, typed, maintained |
| **Agent Framework** | LangGraph | Stateful, checkpointable, multi-agent |
| **Vector Store** | Supabase pgvector | Built-in, no extra infra |
| **Engine A Architecture** | **Event-driven hybrid (WS triggers + 5m fallback)** | Sub-5s reaction, 80% fewer Kronos calls |
| **Auth** | **Telegram `chat_id` via `initData`** | Zero-friction for Mini App users |
| **Whitelist** | **CRUDable via frontend** | User controls their universe |

---

## 6. Environment Variables (Complete)

```env
# ===== BACKEND =====
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require
REDIS_URL=redis://localhost:6379/0
ENCRYPTION_KEY=32-char-base64-key-for-aes-256-gcm
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_BOT_USERNAME=aegisquantbot
APP_URL=https://your-domain.com
KRONOS_API_URL=https://kronos-ai.onrender.com
KRONOS_API_KEY=render-service-api-key
GEMINI_API_KEY_1=AIza...
GEMINI_API_KEY_2=AIza...
GEMINI_API_KEY_3=AIza...
GROQ_API_KEY=gsk_...  # For ticker parsing
OPENAI_API_KEY=sk-... # Optional: for embeddings/RAG

# CEX Credentials (encrypted at rest)
BYBIT_API_KEY=...
BYBIT_API_SECRET=...
OKX_API_KEY=...
OKX_API_SECRET=...
OKX_PASSPHRASE=...
BINANCE_API_KEY=...
BINANCE_API_SECRET=...

# Scraper Accounts (Twitter)
TWITTER_ACCOUNTS_JSON=[{"username":"...","password":"...","email":"..."},...]
TELEGRAM_API_ID=12345
TELEGRAM_API_HASH=abcdef...
TELEGRAM_PHONE=+1234567890
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...

# Engine A Trigger Thresholds (user configurable)
ENGINE_A_PRICE_CHANGE_THRESHOLD=0.02
ENGINE_A_VOLUME_SPIKE_THRESHOLD=3.0
ENGINE_A_SPREAD_BPS_THRESHOLD=10
ENGINE_A_FUNDING_FLIP_ENABLED=true
ENGINE_A_MIN_CONFIDENCE=0.7

# ===== AI SERVICE (RENDER) =====
PYTORCH_CPU_ONLY=1
KRONOS_MODEL_PATH=/app/models/kronos-base
LOG_LEVEL=INFO

# ===== FRONTEND =====
VITE_API_URL=https://api.your-domain.com
VITE_WS_URL=wss://api.your-domain.com
VITE_TELEGRAM_BOT_USERNAME=aegisquantbot
```

---

## 7. API Contract (Frontend ↔ Backend)

### GET `/api/state` → Dashboard Data
```typescript
interface DashboardState {
  walletConnected: boolean;
  walletAddress: string;
  network: 'TON' | 'EVM';
  balance: number;
  portfolioValue: number;
  dailyPnL: number;
  pnlPercentage: number;
  agentActive: boolean;
  agentTarget: string;
  riskLimit: number;
  tradeMode: 'PAPER' | 'LIVE';
  currency: 'USD' | 'NGN';
  nairaRate: number;
  positions: Position[];
  connectedCeFi: { bybit: CeFiStatus; okx: CeFiStatus };
}
```

### GET `/api/signals` → Engine A + B Combined
```typescript
interface Signal {
  ticker: string;           // "$WIF"
  category: string;         // "Solana Memecoin"
  badge: string;            // "HIGH VOLATILITY"
  source: string;           // "r/solana" | "Twitter" | "Kronos"
  metric: string;           // "42/hr mentions"
  analysis: string;         // "Kronos: 82% Bullish"
  confidence: number;       // 0-100
  actionLabel: string;      // "ACTIVATE AGENT FOR $WIF"
  engine: 'A' | 'B';        // Source engine
  kronosForecast?: {        // Engine A only
    trajectories: number[][];
    meanPath: number[];
    confidence90: [number, number][];
  };
}
```

### Whitelist CRUD (`/api/whitelist`)
```typescript
// GET → string[]
// POST → { symbols: string[] } → { added: string[] }
// DELETE /:symbol → { removed: string }
```

### POST `/api/execute-trade` → Gemini-formatted Execution
```typescript
interface ExecuteRequest {
  signal: Signal;
  userState: DashboardState;
  riskSettings: RiskSettings;
  autoApprove: boolean;
}

interface ExecuteResponse {
  executed: boolean;
  trade?: {
    action: 'BUY' | 'SELL' | 'SWAP';
    pair: string;
    size: number;
    price: number;
    stopLoss: number;
    takeProfit: number;
    route: 'CEX' | 'DEX_EVM' | 'DEX_SOLANA' | 'DEX_TON';
    txHash?: string;
  };
  reason?: string;
}
```

### POST `/api/chat` → Telegram Bot Interface
```typescript
interface ChatRequest {
  message: string;
  context: DashboardState;
}

interface ChatResponse {
  response: string;
  intent: 'TRADE' | 'INFO' | 'SETTINGS' | 'STATUS' | 'HELP';
  tradeParams?: {
    action: 'BUY' | 'SELL' | 'SWAP';
    pair: string;
    size: number;
    confidence: number;
  };
}
```

### WebSocket `/ws/updates` → Real-time
```typescript
type WSMessage = 
  | { type: 'POSITION_UPDATE'; data: Position }
  | { type: 'PNL_TICK'; data: { portfolioValue: number; dailyPnL: number } }
  | { type: 'NEW_SIGNAL'; data: Signal }
  | { type: 'TRADE_FILLED'; data: TradeLog }
  | { type: 'AGENT_STATUS'; data: { active: boolean; target: string } }
  | { type: 'RISK_ALERT'; data: { rule: string; triggered: boolean } }
  | { type: 'WHITELIST_CHANGED'; data: { added: string[]; removed: string[] } };
```

---

## 8. Risk Management Rules (Enforced in `RiskValidator`)

| Parameter | Conservative | Medium | Aggressive |
|-----------|--------------|--------|------------|
| Max Allocation/Trade | 5% | 10% | 15% |
| Max Concurrent Trades | 2 | 3 | 5 |
| Stop Loss | 1.5% | 3% | 5% |
| Take Profit | 3% | 6% | 10% |
| Trailing Stop | 0.5% | 1% | 2% |
| Min Kronos Confidence | 75% | 70% | 65% |
| Min Social Sentiment | +0.3 | +0.1 | -0.1 |
| Max Daily Drawdown | 3% | 5% | 8% |

**Whitelist (Engine A)**: User-controlled via frontend (default: BTC, ETH, SOL, TON)
**Engine B**: Dynamic - any token passing liquidity audit (>$50k pool, <5% price impact)

---

## 9. Database Schema Additions (Beyond backend.md Section IV)

```sql
-- User whitelist (CRUD from frontend)
CREATE TABLE user_whitelist (
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(20) DEFAULT 'bybit',
    timeframe VARCHAR(10) DEFAULT '1m',
    active BOOLEAN DEFAULT true,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, symbol, exchange)
);

-- Engine A trigger configs (per user)
CREATE TABLE engine_a_config (
    user_id UUID PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
    price_change_threshold NUMERIC DEFAULT 0.02,
    volume_spike_threshold NUMERIC DEFAULT 3.0,
    spread_bps_threshold INT DEFAULT 10,
    funding_flip_enabled BOOLEAN DEFAULT true,
    min_confidence NUMERIC DEFAULT 0.7,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trade execution audit (immutable)
CREATE TABLE execution_audit (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES profiles(id),
    mode VARCHAR(10) NOT NULL CHECK (mode IN ('paper', 'live')),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(4) NOT NULL CHECK (side IN ('buy', 'sell')),
    size NUMERIC NOT NULL,
    price NUMERIC NOT NULL,
    sl NUMERIC,
    tp NUMERIC,
    kronos_confidence NUMERIC,
    trigger_type VARCHAR(30),  -- 'ws_price', 'ws_volume', 'scheduled'
    status VARCHAR(20) NOT NULL,
    tx_hash TEXT,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- TimescaleDB hypertables for market data
CREATE TABLE market_ticks (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    exchange VARCHAR(20) NOT NULL,
    price NUMERIC NOT NULL,
    volume NUMERIC NOT NULL,
    side VARCHAR(4)
);
SELECT create_hypertable('market_ticks', 'time', chunk_time_interval => INTERVAL '1 day');

CREATE TABLE market_cron_job_org/');
CREATE INDEX idx_market_ticks_symbol_time ON market_ticks (symbol, time DESC);
```

---

## 10. Deployment Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                        PRODUCTION                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │   VERCEL    │    │   RENDER    │    │      RENDER         │  │
│  │  (Frontend) │    │  (Backend)  │    │   (Kronos AI)       │  │
│  │             │    │             │    │                     │  │
│  │ React 19    │◄───►│ FastAPI     │◄───►│ FastAPI + PyTorch  │  │
│  │ Tailwind 4  │     │ + APScheduler│   │ CPU-only           │  │
│  │ Telegram    │     │ + Celery    │    │ /forecast endpoint │  │
│  │ Mini App    │     │ + WebSocket │    │ 512MB RAM          │  │
│  └─────────────┘    └──────┬──────┘    └─────────────────────┘  │
│                           │                                       │
│                    ┌──────┴──────┐                                │
│                    │  SUPABASE   │                                │
│                    │ PostgreSQL  │                                │
│                    │ + Timescale │                                │
│                    │ + pgvector  │                                │
│                    │ + Auth      │                                │
│                    └──────┬──────┘                                │
│                           │                                       │
│                    ┌──────┴──────┐                                │
│                    │   REDIS     │                                │
│                    │  (Upstash)  │                                │
│                    │  Cache +    │                                │
│                    │  Celery     │                                │
│                    └─────────────┘                                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 11. Success Criteria (Definition of Done)

- [ ] **Engine A** event-driven: WS triggers → Kronos → execute in <5s; 5-min fallback scan catches all
- [ ] **Engine B** runs 30-min cycles: scrapes 10+ sources → extracts 20+ tickers → filters to 3-5 liquid opportunities → executes
- [ ] **Kronos AI** responds <2s p95 for 128-candle forecast (30 Monte Carlo paths)
- [ ] **Gemini Flash-Lite** handles 100% of execution formatting + Telegram chat with <500ms latency
- [ ] **Telegram Bot** responds to all commands <1s, RAG answers grounded in trade logs
- [ ] **Frontend** receives real-time updates via WebSocket (PnL, positions, signals, whitelist changes)
- [ ] **Whitelist CRUD** works end-to-end: frontend → API → DB → Engine A picks up instantly
- [ ] **Paper trading** runs 7 days with zero critical bugs, audit trail complete
- [ ] **Live trading** (optional) passes $100 test with full encryption, rollback capability
- [ ] **Monitoring** alerts on: engine stall >10min, Kronos latency >5s, error rate >1%
- [ ] **Documentation** complete: API docs, deployment guide, architecture diagram

---

## 12. Estimated Effort

| Phase | Duration | Complexity |
|-------|----------|------------|
| 0: Foundation | 1 week | Medium |
| 1: Engine A (Event-Driven) | 1 week | High |
| 2: Engine B | 1 week | High |
| 3: Kronos Deploy | 1 week (parallel) | Medium |
| 4: AI Decision + Gemini | 1 week | High |
| 5: Telegram Bot | 1 week | Medium |
| 6: Frontend Integration | 1-2 weeks | Medium |
| 7: Backtesting | 1 week | Medium |
| 8: Hardening | 1 week | High |
| 9: Launch | 1 week | Low |
| **Total** | **8-9 weeks** | **High** |

---

## 13. Immediate Next Steps (Start Today)

1. **Create backend scaffold**:
   ```bash
   cd E:\Projects\aegis-quant
   mkdir -p backend/app/{api,core,engines,scrapers,agents,ml,execution,scheduler,workers,telegram,models,schemas,utils}
   mkdir -p backend/app/api/v1
   mkdir -p backend/app/middleware
   mkdir -p backend/tests/{unit,integration,fixtures}
   mkdir -p backend/alembic
   ```

2. **Initialize Python project**:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # or .\venv\Scripts\Activate.ps1
   pip install fastapi uvicorn pydantic pydantic-settings sqlalchemy asyncpg redis python-telegram-bot ccxt apscheduler celery python-dotenv cryptography httpx
   pip install torch transformers --index-url https://download.pytorch.org/whl/cpu  # for Kronos client
   ```

3. **Create `backend/app/main.py`** with FastAPI app + Telegram auth middleware

4. **Create `backend/app/config.py`** with all env vars (Pydantic Settings)

5. **Run Supabase migration** (profiles + user_whitelist + engine_a_config + execution_audit + hypertables)

6. **Deploy Kronos stub** to Render (health check + `/forecast` skeleton)

7. **Begin Engine A implementation** with CCXT WS manager + trigger engine

---

## Appendix: Key Files to Reference During Implementation

| File | Purpose |
|------|---------|
| `backend.md` | Master architecture spec (Sections I-VI) |
| `E:\Projects\finance-repos\tradingagents\README.md` | Multi-agent LangGraph patterns |
| `E:\Projects\finance-repos\Vibe-Trading\README.md` | Skills, swarms, backtest engines, connectors |
| `E:\Projects\finance-repos\quantdinger\README.md` | CCXT gateway, broker accounts, agent gateway |
| `E:\Projects\finance-repos\AI-Trader\README.md` | Agent-native platform patterns |
| `E:\Projects\finance-repos\daily_stock_analysis\README.md` | Scheduled analysis, multi-channel notifications |
| `E:\Projects\finance-repos\FinceptTerminal\README.md` | Native performance, QuantLib, 16 broker integrations |

---

*This plan is a living document. Update as implementation reveals new constraints or opportunities.*