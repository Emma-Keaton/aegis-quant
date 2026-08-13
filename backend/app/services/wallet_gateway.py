import os
import json
from typing import Dict

import ccxt
try:
    from solders.keypair import Keypair
    from solana.rpc.async_api import AsyncClient as SolanaClient
    import base58 as _base58
    _SOLANA_AVAILABLE = True
except ImportError:
    # The `solana`/`solders`/`base58` packages are optional (not installed on
    # some hosts). Keep the module importable so the app and market feed start;
    # Solana features raise a clear error only when actually used.
    SolanaClient = None
    Keypair = None
    _base58 = None
    _SOLANA_AVAILABLE = False

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
    if not _SOLANA_AVAILABLE:
        raise RuntimeError("Solana support unavailable: install 'solders' + 'solana' to enable it")
    rpc = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
    return SolanaClient(rpc)

def load_solana_keypair() -> Keypair:
    if not _SOLANA_AVAILABLE:
        raise RuntimeError("Solana support unavailable: install 'solders' + 'solana' to enable it")
    secret = os.getenv("SOLANA_PRIVATE_KEY")
    if not secret:
        raise RuntimeError("SOLANA_PRIVATE_KEY not set in environment")
    # Preferred: base58-encoded 64-byte secret key (as exported by most wallets).
    try:
        return Keypair.from_base58_string(secret.strip())
    except Exception:
        pass
    # Fallback: hex-encoded 32-byte secret key.
    hexed = secret.strip()
    if hexed.startswith(("0x", "0X")):
        hexed = hexed[2:]
    return Keypair.from_bytes(bytes.fromhex(hexed))
