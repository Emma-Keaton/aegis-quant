# Solana DEX Integration — Aegis Quant

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    AEGIS QUANT TRADING ENGINE                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────┐         ┌─────────────────┐                │
│  │   CEX TRADING   │         │  SOLANA DEX     │                │
│  │                 │         │  TRADING        │                │
│  │  CCXT Library   │         │  Jupiter API    │                │
│  │  ├─ Binance     │         │  ├─ Quote API   │                │
│  │  ├─ Bybit       │         │  ├─ Swap API    │                │
│  │  ├─ OKX         │         │  ├─ Price API   │                │
│  │  └─ 100+ Exch   │         │  └─ Limits API  │                │
│  └────────┬────────┘         └────────┬────────┘                │
│           │                           │                          │
│           └───────────┬───────────────┘                          │
│                       │                                          │
│              ┌────────▼────────┐                                │
│              │  Gemini Flash   │                                │
│              │  Analysis       │                                │
│              │  (Multi-Agent)  │                                │
│              └────────┬────────┘                                │
│                       │                                          │
│           ┌───────────┼───────────┐                             │
│           ▼           ▼           ▼                             │
│    ┌──────────┐ ┌──────────┐ ┌──────────┐                       │
│    │ Technical│ │ Sentiment│ │   Risk   │                       │
│    │ Analyst  │ │ Analyst  │ │ Analyst  │                       │
│    └──────────┘ └──────────┘ └──────────┘                       │
│                       │                                          │
│              ┌────────▼────────┐                                │
│              │  Portfolio      │                                │
│              │  Manager        │                                │
│              │  (Consensus)    │                                │
│              └─────────────────┘                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## API Endpoints

### CEX Trading (CCXT)
```
POST   /api/execute          # Execute trade on CEX
GET    /api/execute/positions # Get open positions
DELETE /api/execute/positions/{id}  # Close position
```

### Solana DEX Trading (Jupiter)
```
GET    /api/solana/price/{symbol}      # Get token price
GET    /api/solana/market/{symbol}     # Get market data
POST   /api/solana/quote               # Get swap quote
POST   /api/solana/swap                # Get swap tx for signing
GET    /api/solana/trending            # Trending tokens
GET    /api/solana/search/{query}      # Search tokens
```

---

## How It Works

### 1. Token Discovery
```python
# Backend discovers Solana tokens via:
- DexScreener API (free, no key)
- Jupiter API (verified tokens)
- Engine B scrapers (Reddit r/solana, Twitter)
```

### 2. Price Fetching
```python
# Primary: Jupiter Price API
https://price.jup.ag/v4/price?ids=SOL

# Fallback: DexScreener
https://api.dexscreener.com/latest/dex/pairs/solana/{token_address}
```

### 3. Swap Execution Flow
```
User triggers trade → Backend gets quote from Jupiter
    ↓
Quote returned (input/output amounts, slippage, route)
    ↓
Backend returns swap transaction (base64 encoded)
    ↓
Frontend signs transaction with wallet (Phantom/Solflare)
    ↓
Frontend submits to Solana RPC
    ↓
Trade confirmed → logged to database
```

---

## Configuration

### Required Environment Variables
```bash
# Solana RPC (use Helius/QuickNode for production)
SOLANA_RPC_URL="https://api.mainnet-beta.solana.com"

# Optional: WalletConnect Project ID (for mobile wallets)
WALLET_CONNECT_PROJECT_ID="your_project_id"
```

### Solana Token Addresses
```python
# Core tokens
SOL_MINT = "So11111111111111111111111111111111111111112"
USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT_MINT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
```

---

## Frontend Integration

### Wallet Connection (Solana)
```typescript
// src/crypto/solanaConnector.ts
import { Connection, PublicKey } from '@solana/web3.js';

export async function connectSolana() {
  const solana = (window as any).solana;
  await solana.connect();
  return {
    address: solana.publicKey.toString(),
    network: 'Solana Mainnet'
  };
}
```

### Trade Execution
```typescript
// src/components/Wallet.tsx
const executeSolanaSwap = async (token: string, amount: number) => {
  // 1. Get quote from backend
  const quote = await fetch('/api/solana/quote', {
    method: 'POST',
    body: JSON.stringify({ token_symbol: token, amount_usd: amount })
  });
  
  // 2. Get swap transaction
  const swap = await fetch('/api/solana/swap', {
    method: 'POST',
    body: JSON.stringify({
      token_symbol: token,
      amount_usd: amount,
      wallet_address: walletAddress
    })
  });
  
  // 3. Sign and submit via wallet
  const signature = await window.solana.signAndSendTransaction(swap.swap_transaction);
  
  // 4. Confirm on-chain
  await connection.confirmTransaction(signature);
};
```

---

## Engine B Integration

Solana signals are already being scraped:

```python
# app/engines/engine_b.py
SUBREDDITS = ['cryptocurrency', 'solana', 'Bitcoin', 'ethereum']
TELEGRAM_CHANNELS = ['@solanawhales', '@solannetwork']
```

These feed into the Intel dashboard and can trigger Solana trades.

---

## Security Notes

1. **Never store private keys in backend** — use wallet connection
2. **Rate limits**: Jupiter API has 100 req/min free tier
3. **Slippage**: Set higher (200-500 bps) for memecoins
4. **MEV protection**: Jupiter includes MEV protection by default

---

## Testing

```bash
# Test price fetch
curl http://localhost:8000/api/solana/price/SOL

# Test quote
curl -X POST http://localhost:8000/api/solana/quote \
  -H "Content-Type: application/json" \
  -d '{"token_symbol": "BONK", "amount_usd": 10}'

# Test trending tokens
curl http://localhost:8000/api/solana/trending
```

