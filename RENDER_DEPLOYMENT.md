# Aegis Quant — Render Deployment Guide

Complete guide for deploying Aegis Quant as separate Render web services with shared environment variables.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      RENDER DEPLOYMENT                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────┐    ┌─────────────────────┐             │
│  │  FRONTEND SERVICE   │    │   BACKEND SERVICE   │             │
│  │  (Static Site)      │───►│  (FastAPI)          │             │
│  │                     │    │                     │             │
│  │  - React 19 + TS    │    │  - 76 API routes    │             │
│  │  - Vite build       │    │  - Trading engines  │             │
│  │  - Wagmi + Rainbow  │    │  - Gemini Flash     │             │
│  │  - Solana wallets   │    │  - CCXT + Jupiter   │             │
│  └─────────────────────┘    └──────────┬──────────┘             │
│                                         │                        │
│                    ┌────────────────────┼────────────────────┐   │
│                    │                    │                    │   │
│                    ▼                    ▼                    ▼   │
│           ┌──────────────┐   ┌──────────────┐   ┌──────────┐   │
│           │  SUPABASE    │   │  KRONOS      │   │ TELEGRAM │   │
│           │  (Database)  │   │  (Optional)  │   │  Bot     │   │
│           │              │   │              │   │          │   │
│           │  - PostgreSQL│   │  - HF Model  │   │  - Bot   │   │
│           │  - Timescale │   │  - Forecasts │   │  - Webhook│   │
│           │  - pgvector  │   │              │   │          │   │
│           └──────────────┘   └──────────────┘   └──────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Services Overview

| Service | Type | Port | Purpose |
|---------|------|------|---------|
| **aegis-quant-backend** | Python (FastAPI) | 8000 | Main trading engine, API, Telegram bot |
| **aegis-quant-frontend** | Static (Vite) | - | React UI, wallet connections |
| **aegis-quant-kronos** | Python (Optional) | 8001 | AI forecasting (separate for GPU) |

---

## Prerequisites

### 1. Create Supabase Project
```
https://supabase.com/dashboard → New Project
```
- Save database password
- Note project reference (e.g., `xxxxx`)
- Get connection string: Settings → Database

### 2. Create Telegram Bot
```
@BotFather → /newbot → follow prompts
```
- Save bot token
- Get chat ID: Message @userinfobot

### 3. Get API Keys
- **Gemini**: https://aistudio.google.com/apikey
- **WalletConnect**: https://cloud.walletconnect.com (free)
- **Groq** (optional): https://console.groq.com/keys

### 4. Generate Secrets
```bash
# Encryption key (32 bytes base64)
openssl rand -base64 32

# Session secret
openssl rand -hex 32
```

---

## Service 1: Backend (Main API)

### Render Setup

1. Go to https://render.com → New + → Web Service
2. Connect GitHub repo: `Emma-Keaton/aegis-quant`
3. Configure:

| Field | Value |
|-------|-------|
| Name | `aegis-quant-backend` |
| Region | Oregon |
| Environment | Python |
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Starter (free) or Standard |

### Environment Variables

```bash
# ── Database (Supabase) ──────────────────────────────────────
DATABASE_URL=postgresql://postgres.[REF]:[PASS]@db.[REF].supabase.co:5432/postgres
SUPABASE_URL=https://[REF].supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# ── Telegram ─────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_BOT_USERNAME=aegisquantbot
ADMIN_CHAT_ID=123456789

# ── Security ─────────────────────────────────────────────────
ENCRYPTION_KEY=your_32_byte_base64_key
SESSION_SECRET=your_random_hex_secret

# ── AI Services ──────────────────────────────────────────────
GEMINI_API_KEY_1=AIza...
GEMINI_API_KEY_2=
GEMINI_API_KEY_3=
GROQ_API_KEY=

# ── WalletConnect ────────────────────────────────────────────
WALLET_CONNECT_PROJECT_ID=your_wc_project_id

# ── Solana ───────────────────────────────────────────────────
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com

# ── App URL (auto-set by Render) ─────────────────────────────
APP_URL=https://aegis-quant-backend.onrender.com
```

### Post-Deploy Steps

```bash
# Run migrations (via Render Dashboard → Shell)
cd backend
alembic upgrade head
```

### Test Endpoints
```
GET  https://aegis-quant-backend.onrender.com/health
GET  https://aegis-quant-backend.onrender.com/docs
POST https://aegis-quant-backend.onrender.com/api/solana/price/SOL
```

---

## Service 2: Frontend (Static Site)

### Render Setup

1. Go to https://render.com → New + → Static Site
2. Connect same GitHub repo
3. Configure:

| Field | Value |
|-------|-------|
| Name | `aegis-quant-frontend` |
| Region | Oregon |
| Build Command | `npm install --legacy-peer-deps && npm run build` |
| Publish Directory | `dist` |

### Environment Variables

```bash
# None required for static frontend
# Backend URL is hardcoded in src/api/client.ts or passed via build
```

### Auto-Detect Backend URL

The frontend auto-detects the backend URL. If needed, set in `src/api/client.ts`:
```typescript
const API_BASE = import.meta.env.VITE_API_URL || 'https://aegis-quant-backend.onrender.com';
```

### Test
```
https://aegis-quant-frontend.onrender.com
```

---

## Service 3: Kronos (Optional - AI Forecasting)

Deploy separately if you want dedicated AI forecasting with GPU.

### Render Setup

1. New + → Web Service
2. Configure:

| Field | Value |
|-------|-------|
| Name | `aegis-quant-kronos` |
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python -m app.services.kronos_service` |
| Instance Type | **Standard** (requires GPU for model) |

### Environment Variables

```bash
# Same as backend
DATABASE_URL=postgresql://postgres.[REF]:[PASS]@db.[REF].supabase.co:5432/postgres
SUPABASE_URL=https://[REF].supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# Kronos-specific
KRONOS_MODEL_NAME=Kronos-Large
KRONOS_MAX_SEQUENCE_LENGTH=128
```

### Update Backend to Use Kronos Service

Add to backend env vars:
```bash
KRONOS_SERVICE_URL=https://aegis-quant-kronos.onrender.com
KRONOS_API_KEY=your_secure_key
```

---

## Connecting Services

### Backend → Frontend
The frontend calls backend API directly. No special config needed.

### Backend → Kronos (Optional)
Set `KRONOS_SERVICE_URL` in backend env vars to point to Kronos service.

### Telegram Mini App
1. Go to @BotFather
2. /setmenubutton → select your bot
3. Enter frontend URL: `https://aegis-quant-frontend.onrender.com`

---

## Deployment Checklist

### Before Deploying
- [ ] Supabase project created
- [ ] Database connection string copied
- [ ] Telegram bot created, token saved
- [ ] Admin chat ID obtained
- [ ] Gemini API key obtained
- [ ] WalletConnect project ID obtained
- [ ] Encryption key generated
- [ ] Session secret generated

### Backend Deployment
- [ ] Service created on Render
- [ ] All env vars set
- [ ] Migrations run: `alembic upgrade head`
- [ ] Health endpoint responds: `/health`
- [ ] Auth endpoint works: `/api/auth/init`
- [ ] Solana price endpoint works: `/api/solana/price/SOL`

### Frontend Deployment
- [ ] Service created on Render
- [ ] Build succeeds
- [ ] Site loads: `https://aegis-quant-frontend.onrender.com`
- [ ] Telegram Mini App configured

### Integration Tests
- [ ] Frontend connects to backend
- [ ] Telegram bot responds to /start
- [ ] Wallet connect works (MetaMask, Phantom)
- [ ] Source management works
- [ ] Admin dashboard accessible

---

## Troubleshooting

### Backend won't start
```bash
# Check logs in Render dashboard
# Common issues:
# 1. Missing DATABASE_URL
# 2. Missing ENCRYPTION_KEY
# 3. Database connection failed
```

### Frontend can't reach backend
- Check `APP_URL` env var
- Verify CORS is configured (allowed by default)
- Check frontend API base URL

### Telegram bot not responding
- Verify `TELEGRAM_BOT_TOKEN` is correct
- Check webhook is set: `/api/telegram/set-webhook`
- Bot URL should be: `https://aegis-quant-backend.onrender.com/telegram/webhook`

### Database migration fails
```bash
# Run manually via Render Shell
alembic upgrade head

# Check migration status
alembic current
```

### Kronos service not loading
- Requires GPU instance (starter plans won't work)
- Or use placeholder mode (no model loading)
- Check `KRONOS_SERVICE_URL` is set correctly

---

## Cost Estimate (Render Free Tier)

| Service | Plan | Cost |
|---------|------|------|
| Backend | Starter | Free |
| Frontend | Static | Free |
| Kronos | Standard (GPU) | ~$25/mo |
| Supabase | Free | Free (500MB DB) |

**Total:** Free for basic deployment, ~$25/mo for Kronos AI.

---

## Security Notes

1. **Never commit `.env` files** — already in `.gitignore`
2. **Use Render's encrypted env vars** — not plaintext in code
3. **Rotate API keys** regularly
4. **Enable Render's HTTPS** — automatic for all services
5. **Set CORS origins** to your frontend URL in production

---

## Quick Deploy Commands

```bash
# Clone and setup
git clone https://github.com/Emma-Keaton/aegis-quant.git
cd aegis-quant

# Test locally (optional)
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys
uvicorn app.main:app --reload

# Build frontend
cd ..
npm install --legacy-peer-deps
npm run build

# Push to GitHub
git add .
git commit -m "Ready for deployment"
git push origin main
```

Then deploy to Render as described above.

---

## Support

- **Issues:** https://github.com/Emma-Keaton/aegis-quant/issues
- **Docs:** README.md, PRE_DEPLOYMENT_CHECKLIST.md
