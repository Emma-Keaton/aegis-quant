# Aegis Quant — Deployment Checklist

## Prerequisites

- [ ] Python 3.11+ installed
- [ ] Node.js 20+ installed
- [ ] PostgreSQL database (Supabase or self-hosted)
- [ ] Telegram Bot Token (from @BotFather)
- [ ] Gemini API Keys (from Google AI Studio)

---

## Environment Variables

Create `.env` in backend root:

```bash
# Telegram Bot (REQUIRED)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_BOT_USERNAME=your_bot_username

# Admin Access (REQUIRED)
ADMIN_CHAT_ID=your_telegram_chat_id
TELEGRAM_ADMIN_CHAT_ID=your_chat_id

# Database (REQUIRED)
DATABASE_URL=postgresql://user:pass@host:5432/aegis_quant

# Encryption (REQUIRED - 32 bytes base64)
ENCRYPTION_KEY=your_32_byte_key_here

# Gemini AI (REQUIRED for analysis)
GEMINI_API_KEY_1=your_gemini_key_1
GEMINI_API_KEY_2=
GEMINI_API_KEY_3=

# Optional: Kronos Model
KRONOS_SERVICE_URL=https://your-kronos-service.onrender.com

# Optional: WalletConnect Project ID
WALLET_CONNECT_PROJECT_ID=your_wc_project_id

# Optional: Exchange API Keys (stored encrypted in DB)
# Set via frontend Wallet page, not in .env
```

### Generate Encryption Key
```bash
openssl rand -base64 32
```

### Get Telegram Chat ID
1. Message @userinfobot on Telegram
2. Copy your numeric ID

---

## Backend Deployment

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Run Migrations
```bash
alembic upgrade head
```

### 3. Test Backend
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Verify Endpoints
```bash
# Test auth endpoint
curl http://localhost:8000/api/auth/me

# Check routes
curl http://localhost:8000/docs
```

---

## Frontend Deployment

### 1. Install Dependencies
```bash
npm install --legacy-peer-deps
```

### 2. Build
```bash
npm run build
```

### 3. Verify Build
```bash
ls dist/
# Should see: index.html, assets/
```

### 4. Test Production Build
```bash
npm start
# Server starts on port 3000
```

---

## Render Deployment

### Backend Service
1. Connect GitHub repo
2. Set env vars (see above)
3. Build command: `cd backend && pip install -r requirements.txt`
4. Start command: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Deploy

### Frontend Service
1. Connect same repo
2. Build command: `npm install --legacy-peer-deps && npm run build`
3. Serve: Static Site, publish directory `dist`
4. Deploy

### Kronos Service (Optional - AI Forecasting)
1. Deploy to Render with GPU or large CPU
2. Copy `E:/Projects/finance-repos/Kronos/` to service
3. Build: `pip install -r requirements.txt`
4. Start: `python main.py`

---

## Telegram Mini App Setup

1. Go to @BotFather
2. Create new bot: `/newbot`
3. Get bot token from bot settings
4. Create Web App: `/newapp`
5. Link to your deployed frontend URL
6. Set bot commands:
```
/start - Start trading bot
/profile - View profile
/mode - Toggle paper/live
/toggle_bot - Enable/disable agent
```

---

## Post-Deployment Verification

- [ ] Backend responds at `/docs`
- [ ] Frontend loads at root URL
- [ ] Telegram bot responds to `/start`
- [ ] Auth endpoint works (`/api/auth/init`)
- [ ] Admin dashboard accessible (with correct ADMIN_CHAT_ID)
- [ ] Source management endpoints work (`/api/sources/*`)
- [ ] Backtest endpoint works (`/api/backtest/run`)
- [ ] Engine analysis runs (`/api/engine/analyze`)

---

## Monitoring & Maintenance

### Check Logs
```bash
# Backend logs
docker logs aegis-backend

# Render logs
# View in Render dashboard
```

### Database Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

### Backup Strategy
```bash
# Dump PostgreSQL
pg_dump aegis_quant > backup_$(date +%Y%m%d).sql
```

---

## Security Checklist

- [ ] Change default ADMIN_CHAT_ID
- [ ] Rotate GEMINI_API_KEY if exposed in logs
- [ ] Set secure ENCRYPTION_KEY (32 bytes, random)
- [ ] Enable HTTPS for Telegram Mini App
- [ ] Review CORS settings in production
- [ ] Set up rate limiting (already in middleware)

---

## Troubleshooting

### npm install fails
```bash
rm -rf node_modules package-lock.json
npm install --legacy-peer-deps
```

### Build fails - rollup error
```bash
npm install @rollup/rollup-win32-x64-msvc --save-optional
npm run build
```

### Database connection error
```bash
# Check DATABASE_URL format
postgresql://user:pass@host:5432/dbname
```

### Telegram auth fails
```bash
# Verify bot token in .env
# Check APP_URL matches your domain
```

---

## Next Steps After Deploy

1. Test with small position sizes
2. Monitor logs for errors
3. Add your exchange API keys (Binance, Bybit, etc.)
4. Configure risk settings
5. Start with PAPER trading mode
6. Gradually enable LIVE trading
