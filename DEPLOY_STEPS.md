# Deployment Steps — Aegis Quant on Render

## Step 1: Deploy Backend (Web Service)

1. Go to https://render.com → New + → **Web Service**
2. Connect GitHub repo: `Emma-Keaton/aegis-quant`
3. Configure:

| Field | Value |
|-------|-------|
| Name | `aegis-quant-api` |
| Region | Oregon |
| Environment | Python |
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Starter (free) |

4. Add Environment Variables:

```
DATABASE_URL=postgresql://postgres.[YOUR_REF]:[PASSWORD]@db.[YOUR_REF].supabase.co:5432/postgres
SUPABASE_URL=https://[YOUR_REF].supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
TELEGRAM_BOT_TOKEN=123456:ABC...
ADMIN_CHAT_ID=123456789
ENCRYPTION_KEY=[openssl rand -base64 32]
SESSION_SECRET=[openssl rand -hex 32]
GEMINI_API_KEY_1=AIza...
GEMINI_API_KEY_2=
GEMINI_API_KEY_3=
WALLET_CONNECT_PROJECT_ID=your_wc_id
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
CORS_ORIGINS=*
```

5. Click **Create Web Service**
6. Wait for deploy (~3 minutes)
7. Note the URL: `https://aegis-quant-api.onrender.com`

---

## Step 2: Deploy Frontend (Static Site)

1. Go to https://render.com → New + → **Static Site**
2. Connect same GitHub repo
3. Configure:

| Field | Value |
|-------|-------|
| Name | `aegis-quant-frontend` |
| Region | Oregon |
| Build Command | `npm install --legacy-peer-deps && npm run build` |
| Publish Directory | `dist` |

4. No environment variables needed
5. Click **Create Static Site**
6. Wait for deploy (~2 minutes)
7. Note the URL: `https://aegis-quant-frontend.onrender.com`

---

## Step 3: Deploy Kronos (Optional — real model forecasting)

The main backend/worker do **not** run the Kronos model locally. To enable real Kronos
predictions, deploy the dedicated service in `kronos/` and set `KRONOS_SERVICE_URL` on
the backend. Without it, the backend uses a lightweight replacement forecaster
(deterministic) — it still returns prediction + confidence.

1. Go to https://render.com → New + → **Web Service**
2. Connect same GitHub repo
3. Configure:

| Field | Value |
|-------|-------|
| Name | `aegis-quant-kronos` |
| Region | Oregon |
| Environment | Python |
| Root Directory | `kronos` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Basic (2 vCPU, 1GB RAM) — NOT starter |

4. To run **real inference**, install the Kronos lib + torch in `kronos/requirements.txt`
   and set `KRONOS_LOAD_MODEL=1`. While `KRONOS_LOAD_MODEL=0`, this service returns a
   placeholder (fine for smoke-testing the integration).
5. Click **Create Web Service**
6. After deploy, get the URL: `https://aegis-quant-kronos.onrender.com`

### Update Backend to Use Kronos

Go to Backend (and Worker) service → Environment → Add:

```
KRONOS_SERVICE_URL=https://aegis-quant-kronos.onrender.com
```

Re-deploy. The backend proxies forecasts to it and falls back to the replacement
forecaster on any failure.

---

## Step 4: Database Migrations

After backend deploys, run migrations:

1. Go to Render dashboard → Backend service
2. Click **Shell** tab
3. Run:

```bash
cd backend
alembic upgrade head
```

---

## Step 5: Telegram Bot Setup

1. Open Telegram, message @BotFather
2. /newbot → create bot → copy token
3. /setmenubutton → select your bot → enter frontend URL
4. Bot is ready!

---

## Step 6: Verify Deployment

Test endpoints:

```bash
# Health check
curl https://aegis-quant-api.onrender.com/health

# Auth test (get initData from Telegram)
curl -X POST https://aegis-quant-api.onrender.com/api/auth/init \
  -H "Content-Type: application/json" \
  -d '{"init_data": "your_telegram_init_data"}'

# Solana price
curl https://aegis-quant-api.onrender.com/api/solana/price/SOL

# Metrics
curl https://aegis-quant-api.onrender.com/metrics
```

---

## Current Costs

| Service | Plan | Cost |
|---------|------|------|
| Backend API | Starter | Free |
| Frontend | Static | Free |
| Kronos (optional) | Basic | ~$7/mo |
| Supabase | Free | Free (500MB DB) |

**Total: Free** (Kronos optional)
