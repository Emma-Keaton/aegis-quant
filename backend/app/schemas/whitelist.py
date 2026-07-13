from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class WhitelistAdd(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20, description="Trading symbol (e.g., BTC, SOL)")
    exchange: str = Field(default="bybit", description="Exchange to trade on")
    timeframe: str = Field(default="1m", description="Timeframe for analysis")


class WhitelistResponse(BaseModel):
    symbol: str
    exchange: str
    timeframe: str
    active: bool
    added_at: datetime
    
    class Config:
        from_attributes = True


class WhitelistBulkAdd(BaseModel):
    symbols: List[str] = Field(..., min_length=1, max_length=50)
    exchange: str = Field(default="bybit")
    timeframe: str = Field(default="1m")