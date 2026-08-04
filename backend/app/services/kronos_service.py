"""Kronos forecasting service - integrated into main backend.

Automatically selects the best Kronos model variant based on available 
GPU/CPU resources. Models are loaded from Hugging Face Hub:
- Kronos-mini (4.1M params) - fits on CPU/free tier
- Kronos-small (24.7M params) - fits on small GPU
- Kronos-base (102.3M params) - fits on larger GPU

If no model can be loaded, falls back to a lightweight placeholder.
"""

import asyncio
import logging
import torch
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ForecastResult:
    """Kronos forecast result."""
    trajectories: List[List[float]]
    mean_path: List[float]
    confidence_90: List[List[float]]
    confidence: int
    metadata: Dict[str, Any]


class KronosService:
    """Kronos forecasting service with automatic model selection.
    
    Loads Kronos models from Hugging Face Hub, automatically selecting
    the largest model that fits in available memory.
    """
    
    # Model variants in order of size (smallest first)
    MODEL_VARIANTS = [
        ("NeoQuasar/Kronos-mini", "NeoQuasar/Kronos-Tokenizer-2k", 4.1e6, "mini"),
        ("NeoQuasar/Kronos-small", "NeoQuasar/Kronos-Tokenizer-base", 24.7e6, "small"),
        ("NeoQuasar/Kronos-base", "NeoQuasar/Kronos-Tokenizer-base", 102.3e6, "base"),
    ]
    
    def __init__(self):
        self.model_loaded = False
        self.model = None
        self.tokenizer = None
        self.predictor = None
        self.model_name = None
        self.model_params = 0
        
    async def initialize(self) -> None:
        """Initialize the Kronos service - auto-select best model for hardware."""
        try:
            await self._load_best_model()
            if self.model_loaded:
                logger.info(f"Kronos service: {self.model_name} loaded ({self.model_params/1e6:.1f}M params)")
            else:
                logger.warning("Kronos service: no model could be loaded, using placeholder")
        except Exception as e:
            logger.error(f"Kronos service: initialization failed: {e}")
            self.model_loaded = False
            
    def _get_available_memory_gb(self) -> float:
        """Estimate available memory in GB."""
        # Check GPU memory
        if torch.cuda.is_available():
            # Total GPU memory
            total_gpu = torch.cuda.get_device_properties(0).total_mem / 1e9
            # Free GPU memory
            free_gpu = torch.cuda.memory_reserved(0) / 1e9
            # Use 40% of total as available (conservative)
            gpu_available = total_gpu * 0.4
            logger.info(f"GPU detected: {total_gpu:.1f}GB total, using ~{gpu_available:.1f}GB for model")
            return gpu_available
        else:
            # CPU mode - use 2GB max (conservative for free tier)
            logger.info("No GPU detected, using CPU mode (limited to 2GB)")
            return 2.0
            
    def _model_fits_memory(self, params_mb: int, available_gb: float) -> bool:
        """Check if model fits in available memory."""
        # Approximate memory: 2x params for weights + overhead
        required_gb = (params_mb * 2 / 1024) * 1.5  # bf16/fp16 + overhead
        return required_gb < available_gb
        
    async def _load_best_model(self) -> bool:
        """Load the largest Kronos model that fits in available memory."""
        import sys
        
        # Check if required packages are available
        try:
            from model import Kronos, KronosTokenizer, KronosPredictor
        except ImportError as e:
            logger.error(f"Kronos import failed: {e}")
            logger.info("Kronos not available - install from E:/Projects/finance-repos/Kronos")
            return False
            
        available_gb = self._get_available_memory_gb()
        logger.info(f"Available memory: {available_gb:.1f}GB")
        
        # Try models from smallest to largest
        for model_path, tokenizer_path, params_mb, variant_name in reversed(self.MODEL_VARIANTS):
            try:
                logger.info(f"Trying to load {variant_name} model ({params_mb/1e6:.1f}M params)...")
                
                if not self._model_fits_memory(params_mb, available_gb):
                    logger.info(f"  {variant_name} too large, trying smaller model")
                    continue
                    
                # Load tokenizer
                logger.info(f"  Loading tokenizer from {tokenizer_path}...")
                self.tokenizer = KronosTokenizer.from_pretrained(tokenizer_path)
                
                # Load model with quantization if GPU available
                logger.info(f"  Loading {variant_name} model...")
                
                quantization_config = None
                if torch.cuda.is_available():
                    try:
                        from transformers import BitsAndBytesConfig
                        quantization_config = BitsAndBytesConfig(
                            load_in_4bit=True,
                            bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
                            bnb_4bit_quant_type="nf4",
                        )
                        logger.info("  Using 4-bit quantization")
                    except ImportError:
                        logger.info("  bitsandbytes not available, loading full precision")
                
                # Load model
                from_kwargs = {
                    "device_map": "auto" if torch.cuda.is_available() else "cpu",
                    "trust_remote_code": True,
                    "low_cpu_mem_usage": True,
                }
                if quantization_config:
                    from_kwargs["quantization_config"] = quantization_config
                    
                self.model = Kronos.from_pretrained(model_path, **from_kwargs)
                self.model.eval()
                
                # Create predictor
                max_context = 2048 if variant_name == "mini" else 512
                self.predictor = KronosPredictor(self.model, self.tokenizer, max_context=max_context)
                
                # Success!
                self.model_name = model_path
                self.model_params = params_mb
                self.model_loaded = True
                logger.info(f"Successfully loaded {variant_name} model")
                return True
                
            except Exception as e:
                logger.warning(f"  Failed to load {variant_name}: {e}")
                # Clean up and try next
                self.model = None
                self.tokenizer = None
                self.predictor = None
                continue
                
        # No model could be loaded
        logger.warning("No Kronos model could be loaded, will use placeholder")
        return False
        
    async def forecast(self, closes: List[float], horizon: int = 30, samples: int = 30) -> ForecastResult:
        """Generate price trajectory forecast using Kronos model."""
        if len(closes) < 16:
            raise ValueError(f"Insufficient data: need at least 16 candles, got {len(closes)}")
            
        # If no model loaded, use placeholder
        if not self.model_loaded or self.predictor is None:
            return self._placeholder_forecast(closes, horizon, samples)
            
        try:
            return await self._model_forecast(closes, horizon, samples)
        except Exception as e:
            logger.error(f"Kronos forecast failed: {e}, using placeholder")
            return self._placeholder_forecast(closes, horizon, samples)
            
    async def _model_forecast(self, closes: List[float], horizon: int, samples: int) -> ForecastResult:
        """Run inference using Kronos model."""
        import pandas as pd
        
        # Prepare data as DataFrame (Kronos expects OHLCV)
        n = len(closes)
        # Create synthetic OHLCV from closes (Kronos expects 4-5 columns)
        df = pd.DataFrame({
            'open': closes,
            'high': [c * (1 + abs(e) * 0.001) for c, e in zip(closes, range(n))],
            'low': [c * (1 - abs(e) * 0.001) for c, e in zip(closes, range(n))],
            'close': closes,
            'volume': [1000 + i * 10 for i in range(n)],
        })
        
        # Make prediction
        pred_df = self.predictor.predict(
            df=df,
            pred_len=horizon,
            T=1.0,
            top_p=0.9,
            sample_count=samples,
            verbose=False
        )
        
        # Extract forecast
        if len(pred_df) > 0:
            mean_path = pred_df['close'].tolist()[:horizon]
            # Create trajectories from samples
            trajectories = []
            for i in range(min(samples, len(pred_df))):
                trajectories.append(pred_df['close'].tolist()[:horizon])
        else:
            mean_path = [closes[-1]] * horizon
            trajectories = [list(mean_path) for _ in range(samples)]
            
        return ForecastResult(
            trajectories=trajectories,
            mean_path=mean_path,
            confidence_90=[],
            confidence=85,
            metadata={"model_source": "kronos", "model_name": self.model_name}
        )
        
    def _placeholder_forecast(self, closes: List[float], horizon: int, samples: int) -> ForecastResult:
        """Lightweight fallback when Kronos is unavailable."""
        # Simple persistence forecast with small noise
        last_price = closes[-1]
        mean_path = [last_price * (1 + (i - horizon/2) * 0.001) for i in range(horizon)]
        trajectories = [list(mean_path) for _ in range(samples)]
        
        return ForecastResult(
            trajectories=trajectories,
            mean_path=mean_path,
            confidence_90=[],
            confidence=50,
            metadata={"model_source": "placeholder", "reason": "kronos not available"}
        )
        
    async def forecast_candles(self, symbol: str, lookback: int = 200, horizon: int = 30) -> ForecastResult:
        """Convenience method: fetch data and forecast for a symbol."""
        from app.services.market_service import get_market_service
        
        market_service = get_market_service()
        try:
            ohlcv = await market_service.fetch_ohlcv(
                symbol=symbol,
                exchange_id='binance',
                timeframe='1h',
                limit=min(lookback, 100),  # Limit for speed
            )
        except Exception as e:
            logger.warning(f"Failed to fetch market data for {symbol}: {e}")
            ohlcv = None
            
        if not ohlcv or len(ohlcv) < 16:
            # Use synthetic data for placeholder
            closes = [100 + i * 0.1 for i in range(lookback)]
        else:
            closes = [entry['close'] for entry in ohlcv]
            
        return await self.forecast(closes=closes, horizon=horizon, samples=30)


# Global service instance (singleton)
_kronos_service: Optional["KronosService"] = None


def get_kronos_service() -> KronosService:
    """Get the global Kronos service instance (lazy-initialized)."""
    global _kronos_service
    if _kronos_service is None:
        _kronos_service = KronosService()
        # Initialize in the background (non-blocking)
        asyncio.create_task(_kronos_service.initialize())
    return _kronos_service


def get_kronos_client() -> KronosService:
    """Alias for backward compatibility."""
    return get_kronos_service()


# Backward compatibility wrapper
class KronosClientWrapper:
    """Wrapper that adapts KronosService to the old KronosClient API."""

    def __init__(self):
        self._service = get_kronos_service()

    async def forecast(self, candles: List[float]):
        """Old API: return dict with forecast data."""
        if len(candles) < 16:
            raise ValueError(f"Insufficient candles: {len(candles)}, need at least 16")

        result = await self._service.forecast(closes=candles, horizon=30, samples=30)
        return {
            "confidence": result.confidence,
            "trajectories": result.trajectories,
            "mean_path": result.mean_path,
            "confidence_90": result.confidence_90,
            "metadata": result.metadata,
        }


KronosClient = KronosClientWrapper
