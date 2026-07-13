from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID


class SignalBase(BaseModel):
    engine: str = Field(..., description="'A' for Technical Core, 'B' for Social Scout")
    ticker: str
    category: Optional[str] = None
    badge: Optional[str] = None
    source: str
    metric: Optional[str] = None
    analysis: Optional[str] = None
    confidence: int = Field(..., ge=0, le=100)
    action_label: Optional[str] = None


class SignalResponse(SignalBase):
    id: UUID
    kronos_trajectories: Optional[List[List[float]]] = None
    kronos_mean_path: Optional[List[float]] = None
    kronos_confidence_90: Optional[List[List[float]]] = None
    sentiment_score: Optional[float] = None
    mentions_per_hour: Optional[int] = None
    liquidity_usd: Optional[float] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class SignalListResponse(BaseModel):
    signals: List[SignalResponse]
    count: int


class SignalCreate(BaseModel):
    engine: str
    ticker: str
    category: Optional[str] = None
    badge: Optional[str] = None
    source: str
    metric: Optional[str] = None
    analysis: Optional[str] = None
    confidence: int = Field(..., ge=0, le=100)
    action_label: Optional[str] = None
    # Engine A specific
    kronos_trajectories: Optional[List[List[float]]] = None
    kronos_mean_path: Optional[List[float]] = None
    kronos_confidence_90: Optional[List[List[float]]] = None
    # Engine B specific
    sentiment_score: Optional[float] = None
    mentions_per_hour: Optional[int] = None
    liquidity_usd: Optional[float] = None