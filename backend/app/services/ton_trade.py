"""Per-user TON trading via Ton Connect (option A: per-trade user approval).

Flow:
  1. Backend builds an unsigned TON transfer request for the user's *own*
     connected wallet (no server key involved).
  2. The Mini App passes it to `tonConnectUI.sendTransaction(...)`, which opens
     the user's wallet app (Tonkeeper/Tonhub/...) for approval.
  3. The wallet returns a signed `boc`; the app POSTs it back here.
  4. We broadcast the signed boc through TonCenter REST and persist the trade.

Deliberately avoids a server-side TON wallet for *user* trades — tokens stay in
the user's own wallet and only leave it after their explicit on-device approval.
"""

import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TONCENTER_BASE = "https://toncenter.com/api/v2"


def build_transfer_messages(
    recipient: str,
    amount_ton: float,
    comment: str = "",
) -> dict:
    """Return a TonConnect `sendTransaction`-compatible payload.

    amount is in TON; TonConnect expects nanoTON (10^9) as a string.
    """
    import time

    nano = int(round(float(amount_ton) * 1_000_000_000))
    if nano <= 0:
        raise ValueError("amount_ton must be > 0")

    message = {"address": recipient, "amount": str(nano)}

    if comment:
        # Text comment is packed as base64 url-safe utf-8 payload by the wallet.
        import base64

        message["payload"] = base64.urlsafe_b64encode(comment.encode("utf-8")).decode("utf-8")

    return {
        "validUntil": int(time.time()) + 300,  # 5-minute approval window
        "messages": [message],
    }


async def broadcast_boc(boc_b64: str) -> str:
    """Broadcast a signed TON message (.boc, base64) via TonCenter REST.

    Returns the message hash on success.
    """
    import base64

    # TonCenter /sendBoc expects url-safe base64 (b64url) for the boc.
    try:
        raw = base64.urlsafe_b64decode(boc_b64 + "==")
    except Exception:
        raw = base64.urlsafe_b64decode(boc_b64)
    boc_urlsafe = base64.urlsafe_b64encode(raw).decode("utf-8")

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{TONCENTER_BASE}/sendBoc",
            params={"boc": boc_urlsafe},
        )
    data = r.json()
    result = data.get("result", "")
    if not result:
        logger.warning("TON sendBoc rejected: %s", data)
        raise RuntimeError(f"TON broadcast rejected: {data.get('error', 'unknown')}")
    return str(result)


def autonomous_transfer_boc(recipient: str, amount_ton: float, comment: str = "", mnemonic: Optional[str] = None) -> str:
    """Sign + return a TON transfer .boc using a TON wallet mnemonic.

    ``mnemonic`` should be the *user's own* TON wallet seed (multi-tenancy). When
    omitted it falls back to the server ``TON_MNEMONIC`` env key. Uses `tonsdk`
    (guarded import). Raises a clear error if the SDK or key is missing.
    """
    import os
    from app.core.exceptions import ExchangeError

    if not mnemonic:
        mnemonic = os.getenv("TON_MNEMONIC")
    if not mnemonic:
        raise ExchangeError("TON autonomous trading requires a TON wallet mnemonic (user or TON_MNEMONIC)", "TON")

    try:
        from tonsdk.contract.wallet import Wallets
    except ImportError as e:
        raise ExchangeError("TON SDK not installed — add 'tonsdk' to install autonomous TON", "TON")

    nano = int(round(float(amount_ton) * 1_000_000_000))
    if nano <= 0:
        raise ExchangeError("amount_ton must be > 0", "TON")

    try:
        words = mnemonic.strip().split()
        W = Wallets.from_words(words, version="v4")
        owner = W.default.submit_transfer(
            destination=recipient,
            amount=amount_ton,
            message=comment,
        )
        return owner.to_boc()
    except Exception as e:
        raise ExchangeError(f"TON autonomous sign failed: {e}", "TON")


def load_profile_mnemonic(profile) -> Optional[str]:
    """Return the profile's own TON mnemonic (decrypted), else None.

    Multi-tenancy: each user's autonomous TON trades use their own wallet seed,
    so funds stay in their wallet. Falls back to the server TON_MNEMONIC env only
    at the call site when no per-user key exists.
    """
    enc = getattr(profile, "ton_mnemonic_enc", None) if profile is not None else None
    if not enc:
        return None
    try:
        from app.core.encryption import encryption_manager
        return encryption_manager.decrypt(enc)
    except Exception:
        return None
