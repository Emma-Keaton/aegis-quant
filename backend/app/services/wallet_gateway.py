import os
import json
from typing import Dict

import ccxt
from solana.rpc.api import Client as SolanaClient
from solana.keypair import Keypair
from base58 import b58decode

# ---------- CCXT ----------

def load_ccxt_credentials() -> Dict[str, Dict[str, str]]:
    """Read exchange credentials from the ``EXCHANGE_API_KEYS`` env var.
    Expected format is a JSON string, e.g.:
    {"binance": {"apiKey": "...", "secret": "..."}, "gemini": {"apiKey": "...", "secret": "..."}}
    """
    raw = os.getenv("EXCHANGE_API_KEYS", "{}")
    try:
        return json.loads(raw)
    except Exception:
        return {}

def get_ccxt_exchange(name: str) -> ccxt.Exchange:
    """Return a ready‑to‑use CCXT exchange instance.
    ``name`` should match the class name in the ccxt package (e.g. ``binance``, ``gemini``).
    """
    creds = load_ccxt_credentials().get(name.lower(), {})
    exchange_cls = getattr(ccxt, name.lower())
    return exchange_cls({
        "apiKey": creds.get("apiKey", ""),
        "secret": creds.get("secret", ""),
        "enableRateLimit": True,
    })

# ---------- Solana ----------

def get_solana_client() -> SolanaClient:
    rpc = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    return SolanaClient(rpc)

def load_solana_keypair() -> Keypair:
    secret = os.getenv("SOLANA_PRIVATE_KEY")
    if not secret:
        raise RuntimeError("SOLANA_PRIVATE_KEY not set in environment")
    try:
        # Try hex first
        return Keypair.from_secret_key(bytes.fromhex(secret))
    except ValueError:
        # Fall back to base58 encoding used by most wallets
        return Keypair.from_secret_key(b58decode(secret))
