### I. Executive System Overview & Dual-Engine Strategy

The system relies on a decoupled, asynchronous backend pipeline that separates low-latency market data collection from compute-heavy artificial intelligence inference. The orchestrator operates two parallel engines:

```
                               ┌──────────────────────────────────┐
                               │     Core Backend Orchestrator    │
                               │        (FastAPI Engine)          │
                               └────────────────┬─────────────────┘
                                                │
                ┌───────────────────────────────┴───────────────────────────────┐
                ▼                                                               ▼
   ┌──────────────────────────┐                                    ┌──────────────────────────┐
   │ ENGINE A: TECHNICAL CORE │                                    │ ENGINE B: SOCIAL SCOUT   │
   │   (Blue-Chip Autopilot)  │                                    │   (Momentum Discovery)   │
   └────────────┬─────────────┘                                    └────────────┬─────────────┘
                │                                                               │
                ▼ (Continuous WS Poll)                                          ▼ (Async Cron Scrape)
   ┌──────────────────────────┐                                    ┌──────────────────────────┐
   │    CCXT API / Web3 RPC   │                                    │  Multi-Channel Scrapers  │
   │  (Whitelisted Portfolio) │                                    │  (Twitter, Reddit, RSS)  │
   └────────────┬─────────────┘                                    └────────────┬─────────────┘
                │                                                               │
                │                                                               ▼ (Ticker Parsing)
                │                                                  ┌──────────────────────────┐
                │                                                  │   LLM Filtering Agent    │
                │                                                  │   (Symbol Verification)  │
                │                                                  └────────────┬─────────────┘
                │                                                               │
                │                                                               ▼ (Liquidity Audit)
                │                                                  ┌──────────────────────────┐
                │                                                  │  On-Chain DEX Liquidity  │
                │                                                  │    (Jupiter / Raydium)   │
                │                                                  └────────────┬─────────────┘
                │                                                               │
                └───────────────────────────────┬───────────────────────────────┘
                                                ▼
                                   ┌──────────────────────────┐
                                   │   Kronos AI Predictor    │
                                   │  (Autoregressive Model)  │
                                   └────────────┬─────────────┘
                                                │
                                                ▼
                                   ┌──────────────────────────┐
                                   │     Execution Engine     │
                                   │  (CCXT / Web3 Delegate)  │
                                   └──────────────────────────┘
```

#### 1. Engine A: Technical Core (Market autopilot)
*   **Target Assets:** Whitelisted blue-chip assets (BTC, ETH, SOL, TON).
*   **Pipeline:** Pulls real-time K-line (OHLCV) intervals via CCXT WebSockets [1.2.3, 1.2.6].
*   **AI Inference:** Passes clean temporal arrays of the last 64–128 candles to **Kronos AI** on Render to generate next-candle trajectory predictions.
*   **Risk Profile:** Executes orders under strict parameters (e.g., Conservative: 1.5% SL / 3% TP).

#### 2. Engine B: Social Scout (Momentum & Hype Discovery)
*   **Target Assets:** Micro-cap ecosystem tokens, newly minted DEX pools, and trending social tokens.
*   **Pipeline:** Scrapes Reddit, RSS news feeds, Telegram signal channels, and X (Twitter) using asynchronous worker rotations.
*   **Ticker Parsing:** Uses an LLM (Llama3 via Groq) to parse clean ticker symbols from unstructured text and query DEX routers (Jupiter, Ston.fi) for pool liquidity.
*   **Inference & Execution:** Fetches token candles, runs them through Kronos, and executes trades with high-volatility parameters (e.g., Aggressive: Trailing Stop-Loss).

---

### II. Comprehensive Backend Architecture Breakdown

```
                   ┌──────────────────────────────────────────┐
                   │            TELEGRAM USER BOT             │
                   │  (2-Way Interface: Commands & Signals)   │
                   └────────────────────┬─────────────────────┘
                                        │
                                        ▼
                   ┌──────────────────────────────────────────┐
                   │             FASTAPI / REDIS              │
                   │               EVENT BUS                  │
                   └──────┬─────────────────┬───────────┬─────┘
                          │                 │           │
                          ▼                 ▼           ▼
┌───────────────────────────┐ ┌───────────────┐ ┌───────────────────────────┐
│  SOCIAL & NEWS INGESTION  │ │ MARKET DATA   │ │ KRONOS TS FORECASTING     │
│  - Twitter (twscrape)     │ │ ENGINE        │ │ - OHLCV Tokenizer         │
│  - Telegram (Telethon)    │ │ - 5-10s Poll  │ │ - Monte Carlo Simulation  │
│  - Reddit (URS / JSON)    │ │ - WebSockets  │ │ - Risk/Trend Validation   │
│  - RSS / News Articles    │ │ - CCXT        │ │                           │
└─────────────┬─────────────┘ └───────┬───────┘ └─────────────┬─────────────┘
              │                       │                       │
              └───────────────────┐   │   ┌───────────────────┘
                                  ▼   ▼   ▼
                   ┌──────────────────────────────────────────┐
                   │        AI DECISION & RISK ENGINE         │
                   │  - Sentiment + Volume Spike Filter       │
                   │  - LLM Strategist (RAG Context)          │
                   │  - Execution Router (CCXT / Web3)        │
                   └──────────────────────────────────────────┘
```

#### Module 1: Two-Way Telegram Bot Interface
*   **Signal Dispatcher:** Formats and broadcasts trade alerts containing token tickers, sentiment polarity, entry bounds, stop-losses, take-profits, and Kronos probability outcomes. It also handles execution receipts (fills, partial takes, and trailing stop triggers).
*   **Command & RAG Assistant:**
    *   *Commands:* `/watch <token>`, `/risk <level>`, `/panic`, `/portfolio`.
    *   *RAG Assistant:* Conversational NLP requests (e.g., *"Why did you swap TON for USDT at 12:40?"*) are routed to an LLM running over a vector store containing recent scrape tables and trade logs.

#### Module 2: Market Intelligence & Social Media Ingestion
*   **Scraper Matrix:** Pulls from Twitter/X using multi-account credential pools to bypass rate limits [1.1.3], streams telegram channels via MTProto, pulls from subreddits via JSON, and scrapes RSS financial feeds.
*   **Sentiment Processor:** Normalizes extracted targets, scores sentiment using financial NLP models, and calculates velocity spike alerts when social volume surges beyond 3x baseline limits.

#### Module 3: High-Frequency Market Data Engine
*   **Streamer:** Gathers orderbook depth, tick feeds, and volume profiles via CCXT or DexScreener WebSockets.
*   **Redis Cache:** Caches token pricing, short-term moving averages, and orderbook spreads to minimize latency during high-frequency scans.

#### Module 4: Quantitative Validation Engine (Cross-Checking with Kronos)
*   **OHLCV Tokenization:** Encodes the latest 360 intervals of K-line data into Kronos's dual-token format.
*   **Autoregressive Forecasts:** Generates $N=30$ Monte Carlo trajectory simulations to map probability bounds.
*   **Risk Validation Gate:** Restricts trade execution unless social momentum aligns with Kronos's projected downside volatility constraints.

#### Module 5: Decision, Risk & Execution Engine
*   **LLM Strategist:** Combines sentiment weight, volume velocity, technical trends (RSI, EMAs), and Kronos trajectories to generate entry prices, risk sizing (Kelly Criterion), dynamic SL, and TP targets.
*   **Execution Gateway:** Places orders via CCXT (for CEXs) [1.2.3] or Web3 clients (web3.py, Solana-py) for DEXs. It handles trailing stop loops and transaction slippage parameters.

---

### III. Security, Encryption & Handshake Protocols

#### 1. TMA Cryptographic Handshake (`initData` Verification)
Every request from the Next.js client must pass the cryptographic handshake. This validates that the request originated from a legitimate Telegram user session and is verified by your Bot Token.

```python
import hmac
import hashlib
from urllib.parse import parse_qsl
from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader

telegram_init_header = APIKeyHeader(name="X-Telegram-Init-Data", auto_error=True)

def verify_telegram_data(init_data: str, bot_token: str) -> dict:
    try:
        parsed_data = dict(parse_qsl(init_data))
        hash_to_verify = parsed_data.pop("hash")
        
        # Sort remaining keys alphabetically
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        
        # Calculate secure signature keys
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if calculated_hash != hash_to_verify:
            raise HTTPException(status_code=403, detail="Invalid signature")
            
        return parsed_data # Contains verified user ID, username, and query dates
    except Exception:
        raise HTTPException(status_code=403, detail="Signature authentication failed")
```

#### 2. AES-256 Fernet Encryption for CEX API Credentials
To secure stored exchange API keys, encrypt them before saving them to your database:

```python
import os
from cryptography.fernet import Fernet

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

def encrypt_credentials(api_key: str, api_secret: str) -> tuple[str, str]:
    enc_key = cipher_suite.encrypt(api_key.encode()).decode()
    enc_secret = cipher_suite.encrypt(api_secret.encode()).decode()
    return enc_key, enc_secret

def decrypt_credentials(enc_key: str, enc_secret: str) -> tuple[str, str]:
    dec_key = cipher_suite.decrypt(enc_key.encode()).decode()
    dec_secret = cipher_suite.decrypt(enc_secret.encode()).decode()
    return dec_key, dec_secret
```

---

### IV. Database Schema & Data Models (Supabase/PostgreSQL)

To support secure multi-tenant execution, live credentials, local paper simulation, and background worker queues, execute these SQL instructions in your Supabase Editor:

```sql
-- Create custom UUID extension if not exists
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Profiles Table (Main User Configuration)
CREATE TABLE profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT UNIQUE NOT NULL,
    risk_level VARCHAR(20) DEFAULT 'medium' CHECK (risk_level IN ('conservative', 'medium', 'aggressive')),
    max_allocation_pct NUMERIC DEFAULT 10.0 CHECK (max_allocation_pct >= 1.0 AND max_allocation_pct <= 100.0),
    max_concurrent_trades INT DEFAULT 3,
    trading_mode VARCHAR(10) DEFAULT 'paper' CHECK (trading_mode IN ('paper', 'live')),
    bot_enabled BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- 2. User Credentials (Encrypted CEX API Keys)
CREATE TABLE user_credentials (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    exchange_name VARCHAR(50) NOT NULL CHECK (exchange_name IN ('bybit', 'okx', 'binance')),
    encrypted_api_key TEXT NOT NULL,
    encrypted_api_secret TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- 3. Paper Trading Balances (Mock Assets)
CREATE TABLE paper_balances (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    asset_name VARCHAR(10) NOT NULL DEFAULT 'USDT',
    balance NUMERIC NOT NULL DEFAULT 10000.00,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()),
    UNIQUE(user_id, asset_name)
);

-- 4. Unified Trade Execution Logs (Live & Paper combined)
CREATE TABLE trade_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('buy', 'sell')),
    execution_type VARCHAR(10) NOT NULL CHECK (execution_type IN ('paper', 'live')),
    amount NUMERIC NOT NULL,
    price NUMERIC NOT NULL,
    total_value_usd NUMERIC NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('filled', 'pending', 'confirmed', 'failed')),
    slippage NUMERIC DEFAULT 0.00,
    tx_hash TEXT,
    id_reference VARCHAR(50), -- CEX Order ID or local unique code
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);

-- 5. Social Trends Cache
CREATE TABLE social_trends (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) UNIQUE NOT NULL,
    sentiment_score NUMERIC NOT NULL,
    mentions_per_hour INT DEFAULT 0,
    source VARCHAR(50) NOT NULL,
    last_scraped_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW())
);
```

---

### V. Step-by-Step Implementation & Deployment Protocol

#### 1. Setup Local Environment
Clone your template repository, setup your environment variables, and verify Python dependencies:
```bash
# Create local project layout
mkdir -p aegis-quant/{backend,ai-service}
cd aegis-quant/backend

# Initialize and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn cryptography requests ccxt apscheduler praw telethon psycopg2-binary
```

#### 2. Configure PyTorch-CPU on Render (Avoid OOM Crashes)
When deploying your **Kronos AI** model on Render's free tier, standard PyTorch libraries will exceed the 512MB RAM ceiling and crash the server. You must compile using a PyTorch build targeting only CPU.

Add these instructions to your `ai-service/requirements.txt`:
```text
fastapi
uvicorn
# Force Python to load the official CPU-compiled binaries
--index-url https://download.pytorch.org/whl/cpu
torch
transformers
numpy
```

#### 3. Integrate Dual-Engine Loops (APScheduler Async Scheduler)
Run both Engine A (Standard Chart Analysis) and Engine B (Social Scouting & Extraction) concurrently inside your main FastAPI thread:

```python
import asyncio
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

app = FastAPI()
scheduler = AsyncIOScheduler()

async def run_engine_a_market_check():
    """Engine A: Fetch OHLCV, analyze structures via Kronos, trigger trades."""
    print("📈 [Engine A] Checking whitelisted market technicals...")
    # CCXT logic and Kronos request payloads go here

async def run_engine_b_social_scrape():
    """Engine B: Scrape Reddit/RSS, filter via LLM, execute momentum trades."""
    print("📡 [Engine B] Scraping news & sentiment pipelines...")
    # twscrape/praw logic, LLM entity classification, and DEX liquidity audits go here

@app.on_event("startup")
async def start_trading_engines():
    # Configure scheduler with AsyncIOScheduler to run on single thread
    scheduler.add_job(run_engine_a_market_check, 'interval', minutes=5, max_instances=1)
    scheduler.add_job(run_engine_b_social_scrape, 'interval', minutes=30, max_instances=1)
    scheduler.start()
    print("🤖 [Aegis Orchestrator] Dual-Engine loops initialized successfully.")
```

---

### VI. Master Repository Reference Guide (The Top 20 Repositories to Pull From)

#### A. Time-Series Forecasting & Quantitative Modeling
1. **[shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos)** – Auto-regressive candlestick model for trajectory forecasts and Monte Carlo scenario generations.
2. **[AI4Finance-Foundation/FinRL](https://github.com/AI4Finance-Foundation/FinRL)** – Deep Reinforcement Learning (DRL) frameworks optimized for active crypto trading environments.
3. **[microsoft/qlib](https://github.com/microsoft/qlib)** – AI-oriented quantitative investment platform for backtesting model-based strategies.
4. **[freqtrade/freqtrade](https://github.com/freqtrade/freqtrade)** (specifically **FreqAI**) – Real-time machine learning pipelines (XGBoost, custom PyTorch models) running on top of automated exchange loops.

#### B. Social Media, Scraping & Sentiment Pipelines
5. **[vladcalin/twscrape](https://github.com/vladcalin/twscrape)** – Async Twitter/X scraper supporting anti-rate-limit multi-account rotation [1.1.3].
6. **[peter-sun/twikit](https://github.com/peter-sun/twikit)** – Python web API library for interacting with Twitter without official developer portal keys.
7. **[Telethon/Telethon](https://github.com/Telethon/Telethon)** – Python 3 MTProto Telegram library for streaming message feeds from public crypto signal channels.
8. **[skandabhairava/Universal-Reddit-Scraper](https://github.com/skandabhairava/Universal-Reddit-Scraper)** – Automated Reddit scraping client targeting subreddits like `r/CryptoCurrency` [1.1.3].
9. **[scrapy/scrapy](https://github.com/scrapy/scrapy)** – High-performance scraping framework used to build real-time RSS financial news readers.
10. **[apify/crawlee-python](https://github.com/apify/crawlee-python)** – Anti-bot bypass browser scraper, essential for parsing locked financial forums.

#### C. Exchange Connectivity, Web3 & Execution Gateway
11. **[ccxt/ccxt](https://github.com/ccxt/ccxt)** – The industry-standard Python/JS library wrapping over 100 centralized crypto exchanges [1.2.3].
12. **[web3py/web3.py](https://github.com/ethereum/web3.py)** – Python Web3 libraries to interact directly with EVM smart contracts (Uniswap v3 pools) [1.2.3].
13. **[solana-labs/solana-py](https://github.com/michaelhly/solana-py)** – Python SDK to build transactions on Solana DEXs (Raydium, Orca).
14. **[ton-connect/demo-dapp-with-wallet](https://github.com/ton-connect/demo-dapp-with-wallet)** – Handshake flow patterns linking Tonkeeper and other mobile TON wallets [1.2.5].

#### D. Telegram Interface & Multi-Agent Frameworks
15. **[python-telegram-bot/python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)** – Asynchronous client handling incoming user bot commands and webhook alerts [1.2.4].
16. **[langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)** – Stateful multi-actor AI agent loops, useful to model conversational user interactions.
17. **[phidatahq/phidata](https://github.com/phidatahq/phidata)** – Autonomous AI assistant toolkit with native knowledge bases and vector support (RAG).

#### E. Task Orchestration & Storage Infrastructure
18. **[agronholm/apscheduler](https://github.com/agronholm/apscheduler)** – Async execution schedules, critical for managing Engine A and Engine B tasks safely on standard CPU configurations.
19. **[celery/celery](https://github.com/celery/celery)** – Distributed asynchronous task queues for offloading resource-intensive scraping routines.
20. **[timescale/timescaledb](https://github.com/timescale/timescaledb)** – Time-series extension built on PostgreSQL, optimized for logging financial market ticks and high-frequency sentiment historical models.