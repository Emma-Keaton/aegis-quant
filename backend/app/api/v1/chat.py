from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Literal

from app.core.telegram_auth import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    context: Optional[dict] = None


class ChatResponse(BaseModel):
    response: str
    intent: Literal["TRADE", "INFO", "SETTINGS", "STATUS", "HELP", "UNKNOWN"]
    trade_params: Optional[dict] = None


class QuickActionRequest(BaseModel):
    action: Literal["portfolio", "signals", "risk", "help", "positions", "pnl"]
    params: Optional[dict] = None


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: dict = Depends(get_current_user)
):
    """
    Chat with Aegis Quant AI (Gemini Flash-Lite)
    Handles natural language commands and queries
    """
    # TODO: Integrate with Gemini client
    # For now, return contextual responses based on keywords
    
    message = request.message.lower()
    telegram_id = user["id"]
    
    # Simple intent detection
    if any(w in message for w in ["buy", "sell", "trade", "swap", "long", "short"]):
        intent = "TRADE"
        response = "I can help you execute a trade. Please specify the symbol, side (buy/sell), and size. For example: 'Buy $500 worth of SOL'"
        trade_params = {"action": "ASK_PARAMS"}
    
    elif any(w in message for w in ["portfolio", "balance", "holdings", "positions", "pnl", "profit", "loss"]):
        intent = "STATUS"
        response = "Fetching your current portfolio status... (WebSocket will update in real-time)"
        trade_params = None
    
    elif any(w in message for w in ["risk", "stop loss", "take profit", "allocation", "leverage"]):
        intent = "SETTINGS"
        response = "Risk settings can be adjusted in the Strategy tab. Current defaults: 3% SL, 6% TP, 10% max allocation"
        trade_params = None
    
    elif any(w in message for w in ["signal", "opportunity", "watchlist", "scan"]):
        intent = "INFO"
        response = "Checking latest Engine A/B signals... (see Intel tab for real-time updates)"
        trade_params = None
    
    elif any(w in message for w in ["help", "how", "what", "commands"]):
        intent = "HELP"
        response = (
            "I can help you with:\n"
            "• Trade execution: 'Buy $200 SOL'\n"
            "• Portfolio status: 'Show my positions'\n"
            "• Risk settings: 'Set stop loss to 2%'\n"
            "• Signals: 'What are the top signals?'\n"
            "• Bot control: 'Enable bot' / 'Disable bot'"
        )
        trade_params = None
    
    else:
        intent = "UNKNOWN"
        response = "I didn't understand that. Try asking about trades, portfolio, risk settings, or signals."
        trade_params = None
    
    return ChatResponse(
        response=response,
        intent=intent,
        trade_params=trade_params
    )


@router.post("/quick-action", response_model=ChatResponse)
async def quick_action(
    request: QuickActionRequest,
    user: dict = Depends(get_current_user)
):
    """Handle quick action buttons from Telegram bot"""
    action = request.action
    
    responses = {
        "portfolio": "Fetching portfolio... (check Dashboard tab)",
        "signals": "Latest signals available in Intel tab",
        "risk": "Risk settings in Strategy tab",
        "help": "Type /help for available commands",
        "positions": "Current positions shown in Dashboard",
        "pnl": "PnL updates in real-time on Dashboard"
    }
    
    return ChatResponse(
        response=responses.get(action, "Unknown action"),
        intent="INFO",
        trade_params=None
    )