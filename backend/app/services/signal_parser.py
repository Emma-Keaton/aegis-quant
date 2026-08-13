"""Signal parser — turns a raw channel message into a structured trade signal.

Uses the Groq LLM (the "parser model" — Llama 3.3 70B Versatile) to decode
watched-channel messages into `{symbol, side, size, confidence, reason}`.
If Groq is unavailable it falls back to a deterministic heuristic so the
copy-trade pipeline never hard-fails.
"""

import logging
import re
from typing import Optional, Dict

from app.services.groq_client import get_groq_client

logger = logging.getLogger(__name__)

_SKIP = {
    "BUY", "SELL", "LONG", "SHORT", "CALL", "PUT", "USD", "USDT", "SOON",
    "CRYPTO", "TOKEN", "COIN", "NOW", "TODAY", "TOKENS", "OF", "WE", "ARE",
    "THE", "THIS", "THAT", "AND", "AT", "FOR", "WITH", "POSITION", "POSITIONS",
    "PUMP", "DUMP", "BUYING", "SELLING", "ACCUMULATE", "EXIT", "GOING", "OUR",
    "HERE", "WILL", "JUST", "NEXT", "TARGET", "TARGETS", "LEVEL", "LEVELS",
    "ENTRY", "HOLD", "HELD", "COIN", "ALPHA", "ALL", "US", "IN", "ON", "TO",
}
_SYMBOL_RE = re.compile(r"\b[A-Z0-9]{2,10}\b")


def _heuristic_parse(text: str) -> Optional[Dict]:
    """Deterministic fallback parser (used when the Groq parser is unavailable)."""
    upper = text.upper()
    purely_buy = any(w in upper for w in ("BUY", "LONG", "ACCUMULATE", "PUMP"))
    purely_sell = any(w in upper for w in ("SELL", "SHORT", "DUMP", "EXIT"))
    if purely_buy and purely_sell:
        side = None
    elif purely_buy:
        side = "buy"
    elif purely_sell:
        side = "sell"
    else:
        side = None

    # Natural-language: "buy $500 of SOL" -> prefer the last plausible coin token.
    candidates = [
        tok for tok in _SYMBOL_RE.findall(upper)
        if tok not in _SKIP and tok.isalpha() and 2 <= len(tok) <= 8
    ]
    symbol = candidates[-1] if candidates else None

    if not symbol or not side:
        return None

    m = re.search(r"\$?\s*([\d,]+(?:\.\d+)?)\s*(?:of\s+)?", text)
    try:
        size = float(m.group(1).replace(",", "")) if m else None
    except Exception:
        size = None

    return {
        "symbol": symbol,
        "side": side,
        "size": size,
        "confidence": 70,
        "reason": text[:120],
    }


async def parse_signal_text(text: str, max_len: int = 600) -> Optional[Dict]:
    """Parse a raw message into a structured signal, or None if it isn't one."""
    if not text or not text.strip():
        return None
    client = get_groq_client()
    if client is not None:
        try:
            parsed = await client.extract_signal(text, max_len)
            # Normalize
            side = str(parsed.get("action", "") or "").lower()
            side = side if side in ("buy", "sell") else None
            symbol = str(parsed.get("ticker", "") or "").strip().upper().lstrip("$")
            if symbol and side:
                return {
                    "symbol": symbol,
                    "side": side,
                    "size": parsed.get("size"),
                    "confidence": int(parsed.get("confidence") or 0),
                    "sentiment": float(parsed.get("sentiment") or 0.0),
                    "reason": str(parsed.get("reason") or text[:120]),
                }
        except Exception as e:
            logger.warning("Groq parser failed, falling back to heuristic: %s", e)
    return _heuristic_parse(text)