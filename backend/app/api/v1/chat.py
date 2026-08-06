"""Chat endpoint — lightweight keyword-based routing (Gemini optional)."""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.telegram_auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


CHAT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "response": {"type": "STRING"},
        "intent": {"type": "STRING", "enum": ["TRADE", "INFO", "SETTINGS", "STATUS", "HELP", "UNKNOWN"]},
        "tradeParams": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "enum": ["BUY", "SELL", "SWAP"]},
                "pair": {"type": "STRING"},
                "size": {"type": "NUMBER"},
                "confidence": {"type": "NUMBER"},
            }
        }
    },
    "required": ["response", "intent"],
}


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    context: Optional[dict] = None


class ChatResponse(BaseModel):
    status: str
    response: str
    intent: str
    trade_params: Optional[dict] = None


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: dict = Depends(get_current_user),
):
    telegram_id = user["id"]
    
    system_prompt = f"""You are Aegis Quant, an AI trading assistant.
User context: telegram_id={telegram_id}

Capabilities:
- Execute paper trades
- Manage risk settings
- Toggle trading agent
- Check positions, PnL, portfolio
- Switch currency (USD/NGN)
- Panic close all positions

Respond naturally and concisely."""
    
    # Keyword-based fallback (Gemini would go here)
    msg = req.message.lower()
    
    if any(w in msg for w in ["buy", "sell", "trade", "swap", "long", "short"]):
        intent = "TRADE"
        response = "I can help you execute a trade. Please specify the symbol, side (buy/sell), and size. For example: 'Buy $500 worth of SOL'"
        trade_params = {"action": "ASK_PARAMS"}
    elif any(w in msg for w in ["portfolio", "balance", "holdings", "positions", "pnl", "profit", "loss"]):
        intent = "STATUS"
        response = "Checking your current portfolio status..."
        trade_params = None
    elif any(w in msg for w in ["risk", "stop loss", "take profit", "allocation", "leverage"]):
        intent = "SETTINGS"
        response = "Risk settings can be adjusted in the Strategy tab."
        trade_params = None
    elif any(w in msg for w in ["signal", "opportunity", "watchlist", "scan"]):
        intent = "INFO"
        response = "Checking latest market signals..."
        trade_params = None
    elif any(w in msg for w in ["help", "how", "what", "commands"]):
        intent = "HELP"
        response = """I can help you with:
• Trade execution: 'Buy $200 SOL'
• Portfolio status: 'Show my positions'
• Risk settings: 'Set stop loss to 2%'
• Signals: 'What are the top signals?'
• Bot control: 'Enable bot' / 'Disable bot'"""
        trade_params = None
    else:
        intent = "UNKNOWN"
        response = "I didn't understand that. Try asking about trades, portfolio, risk settings, or signals."
        trade_params = None
    
    return ChatResponse(
        status="success",
        response=response,
        intent=intent,
        trade_params=trade_params if trade_params != "ASK_PARAMS" else None,
    )
