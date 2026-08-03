# Supabase Setup Guide for Aegis Quant

## Step 1: Create Supabase Project

1. Go to https://supabase.com/dashboard
2. Click "New Project"
3. Fill in:
   - Organization: (your org)
   - Name: `aegis-quant`
   - Database Password: (strong password - save this!)
   - Region: (closest to you)
4. Click "Create new project"
5. Wait 2-3 minutes for setup

## Step 2: Get Connection String

1. Go to **Project Settings** → **Database**
2. Scroll to "Connection string"
3. Choose **URI** format
4. Copy the connection string

### Direct Connection (Development)
```
postgresql://postgres.[YOUR_REF]:[PASSWORD]@db.[YOUR_REF].supabase.co:5432/postgres
```

### Pooler Connection (Production/Render)
```
postgresql://postgres.[YOUR_REF]:[PASSWORD]@aws-0-[REGION]-pooler.postgres.vercel-storage.com:6543/postgres
```

## Step 3: Get API Keys

1. Go to **Project Settings** → **API**
2. Copy:
   - **Project URL**: `https://xxxxx.supabase.co`
   - **anon/public key**: `eyJhbGciOiJIUzI1NiIs...`
   - **service_role key**: `eyJhbGciOiJIUzI1NiIs...` (keep secret!)

## Step 4: Configure .env

Copy `.env.example` to `.env` and fill in:

```bash
# Supabase
SUPABASE_URL="https://xxxxx.supabase.co"
SUPABASE_ANON_KEY="eyJhbGciOiJIUzI1NiIs..."
SUPABASE_SERVICE_ROLE_KEY="eyJhbGciOiJIUzI1NiIs..."

# Database (use pooler for production)
DATABASE_POOL_URL="postgresql://postgres.[YOUR_REF]:[PASSWORD]@aws-0-xx-pooler.postgres.vercel-storage.com:6543/postgres"

# Telegram
TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
ADMIN_CHAT_ID=123456789

# Security
ENCRYPTION_KEY=$(openssl rand -base64 32)
```

## Step 5: Run Migrations

```bash
cd backend
alembic upgrade head
```

## Step 6: Verify Connection

```bash
python -c "
from app.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text('SELECT 1'))
    print('Connected to Supabase:', result.scalar())
"
```

## Step 7: Enable TimescaleDB (Optional - for time-series)

```sql
-- Run in Supabase SQL Editor
CREATE EXTENSION IF NOT EXISTS timescaledb;
```

## Migration Notes

| From | To | Command |
|------|-----|---------|
| SQLite (dev) | Supabase | `DATABASE_URL` set |
| Direct | Pooler | Use `DATABASE_POOL_URL` |
| Local | Production | Set `ENVIRONMENT=production` |

## Troubleshooting

### Connection refused
- Check SSL mode is `require`
- Verify password in connection string
- Ensure IP is whitelisted (Supabase allows all by default)

### Pool exhausted
- Increase `DATABASE_POOL_SIZE` in config
- Use pooler connection for production

### Migration fails
```bash
# Check current version
alembic history

# Reset if needed
alembic downgrade base
alembic upgrade head
```
