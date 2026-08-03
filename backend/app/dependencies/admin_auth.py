"""Dependency to verify that a request originates from the Telegram admin user.

The Mini App sends the full `window.Telegram.WebApp.initData` string in the
`X‑Telegram‑Init‑Data` header. This function validates the HMAC‑SHA256 signature
using the bot token, extracts the user id, and ensures it matches the
`TELEGRAM_ADMIN_CHAT_ID` environment variable.
"""

import hmac
import hashlib
from urllib.parse import parse_qsl
from fastapi import Header, HTTPException, Depends
from app.config import get_settings
import json

def _verify_init_data(init_data: str, bot_token: str) -> dict:
    """Validate Telegram init data and return the parsed dictionary.

    Args:
        init_data: The raw initData query string from the Mini App.
        bot_token: Bot token used to compute the secret key.
    Raises:
        HTTPException: If the signature is missing or invalid.
    """
    # Parse the init data into a dict
    data = dict(parse_qsl(init_data))
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing hash in init data")

    # Recreate the data check string (sorted by key)
    data_check_string = "\n".join([f"{k}={v}" for k, v in sorted(data.items())])

    # Compute the secret key as Telegram does
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise HTTPException(status_code=403, detail="Invalid init data signature")
    return data


def verify_telegram_admin(x_telegram_init_data: str = Header(None)):
    """FastAPI dependency that ensures the caller is the configured admin.

    The dependency extracts the `user.id` from the validated init data and
    compares it against the `TELEGRAM_ADMIN_CHAT_ID` setting. If the check
    fails, a 403 response is returned.
    """
    settings = get_settings()
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Missing X‑Telegram‑Init‑Data header")

    init_dict = _verify_init_data(x_telegram_init_data, settings.TELEGRAM_BOT_TOKEN)
    # The init data contains a JSON string under the 'user' key
    try:
        user_info = json.loads(init_dict.get("user", "{}"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Malformed user data in init data")
    user_id = user_info.get("id")
    if str(user_id) != str(settings.TELEGRAM_ADMIN_CHAT_ID):
        raise HTTPException(status_code=403, detail="Unauthorized: not admin user")
    return user_id
