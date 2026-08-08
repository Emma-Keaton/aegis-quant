"""Kronos AI Forecasting Worker — standalone Render service."""

import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add finance-repos to path for Kronos imports
finance_repos_path = Path(__file__).parent.parent / "finance-repos" / "Kronos"
if finance_repos_path.exists():
    sys.path.insert(0, str(finance_repos_path))
else:
    # Try from project root
    sys.path.insert(0, "/Projects/finance-repos/Kronos")

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Kronos Forecasting Service", version="1.0.0")


class ForecastRequest(BaseModel):
    closes: List[float]
    horizon: int = 30
    samples: int = 10


class ForecastResponse(BaseModel):
    trajectories: List[List[float]]
    mean_path: List[float]
    confidence_90: List[List[float]]
    confidence: int
    metadata: Dict[str, Any]


# Global model instances
_model = None
_tokenizer = None
_predictor = None
_model_loaded = False


def load_kronos_model():
    """Load Kronos model from Hugging Face."""
    global _model, _tokenizer, _predictor, _model_loaded
    
    try:
        # Import Kronos model classes
        from model import Kronos, KronosTokenizer, KronosPredictor
        
        # Try mini first (smallest, fits on free tier)
        logger.info("Loading Kronos-mini (4.1M params)...")
        _tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-2k")
        _model = Kronos.from_pretrained("NeoQuasar/Kronos-mini")
        _predictor = KronosPredictor(_model, _tokenizer, max_context=2048)
        _model_loaded = True
        logger.info("Kronos-mini loaded successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to load Kronos-mini: {e}")
        
        # Try small model
        try:
            logger.info("Trying Kronos-small (24.7M params)...")
            from model import Kronos, KronosTokenizer, KronosPredictor
            _tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
            _model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
            _predictor = KronosPredictor(_model, _tokenizer, max_context=512)
            _model_loaded = True
            logger.info("Kronos-small loaded successfully")
            return True
        except Exception as e2:
            logger.error(f"Failed to load Kronos-small: {e2}")
            return False
    
    return False


@app.on_event("startup")
async def startup():
    """Load model on service startup."""
    logger.info("Starting Kronos worker service...")
    load_kronos_model()


@app.post("/forecast", response_model=ForecastResponse)
async def forecast(request: ForecastRequest):
    """Run Kronos forecast."""
    if not _model_loaded or _predictor is None:
        # Return placeholder if model not loaded
        return ForecastResponse(
            trajectories=[[request.closes[-1]] * request.horizon for _ in range(request.samples)],
            mean_path=[request.closes[-1]] * request.horizon,
            confidence_90=[],
            confidence=50,
            metadata={"source": "placeholder", "reason": "model not loaded"}
        )
    
    try:
        import pandas as pd
        import torch
        
        # Prepare data as DataFrame
        df = pd.DataFrame({
            'open': request.closes,
            'high': [c * (1 + abs(i) * 0.001) for i, c in enumerate(request.closes)],
            'low': [c * (1 - abs(i) * 0.001) for i, c in enumerate(request.closes)],
            'close': request.closes,
            'volume': [1000 + i * 10 for i in range(len(request.closes))],
        })
        
        # Run prediction
        pred_df = _predictor.predict(
            df=df,
            pred_len=request.horizon,
            T=1.0,
            top_p=0.9,
            sample_count=request.samples,
            verbose=False
        )
        
        # Extract results
        if len(pred_df) > 0:
            mean_path = pred_df['close'].tolist()[:request.horizon]
            trajectories = [mean_path.copy() for _ in range(min(request.samples, len(pred_df)))]
        else:
            mean_path = [request.closes[-1]] * request.horizon
            trajectories = [mean_path.copy() for _ in range(request.samples)]
        
        return ForecastResponse(
            trajectories=trajectories,
            mean_path=mean_path,
            confidence_90=[],
            confidence=85,
            metadata={
                "model": "kronos-mini",
                "source": "worker",
                "horizon": request.horizon,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Forecast failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model_loaded": _model_loaded,
        "service": "kronos-worker",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
